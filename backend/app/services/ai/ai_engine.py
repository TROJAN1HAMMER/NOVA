"""
NOVA — AI Service Layer

The high-level, business-facing AI functions used by the rest of NOVA:
  - explain_vulnerability / explain_vulnerabilities_batch — plain-language
    explanation + business impact
  - suggest_remediation     — focused remediation steps for one finding
  - generate_executive_summary — scan-level summary for non-technical stakeholders
  - generate_risk_explanation  — why a finding's Banking Risk Score is what it is

These are the *only* things AI is used for in NOVA — deduplication,
severity normalization, CWE/OWASP/MITRE mapping, BRS scoring, and
compliance evaluation are all deterministic (see `services/aggregation/`,
`services/risk/`, `services/compliance/`) and never touch a provider.

Nothing here calls a provider or even the gateway directly. Every request
goes through two layers:
  1. `sanitizer.sanitize_finding()` — converts a `RawFinding` into a
     `SanitizedFinding` that never contains raw scanner-produced text,
     file paths, or line numbers (see sanitizer.py for exactly what's
     dropped and why).
  2. `middleware.get_middleware().dispatch()` — policy allow-list, token
     budget guard, semantic cache, duplicate-request detection, and
     provider dispatch with fallback (ending in local Ollama/vLLM before
     giving up).

Every function degrades to a deterministic template (`templates.py`) when
no provider is configured or every configured provider fails — NOVA's
core findings/scoring/compliance output is never blocked on AI
availability.
"""

import json
from collections import Counter
from dataclasses import dataclass
from typing import Iterator, Optional

import structlog

from app.config import get_settings
from app.schemas.finding import RawFinding
from app.services.ai import semantic_cache
from app.services.ai.chunking import chunk_by_tokens
from app.services.ai.middleware import get_middleware
from app.services.ai.request_lock import try_acquire, release, wait_for_result
from app.services.ai.sanitizer import SanitizedFinding, sanitize_finding
from app.services.ai.templates import get_template
from app.services.compliance.compliance_mapper import ComplianceMappingData

logger = structlog.get_logger(__name__)
settings = get_settings()


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class AIInsight:
    explanation: str
    business_impact: str
    remediation: str
    generated_by: str = "template"  # provider name ("claude"/"openai"/...) or "template"


def _template_insight_for_category(category: str) -> AIInsight:
    template = get_template(category)
    return AIInsight(
        explanation=template["explanation"],
        business_impact=template["business_impact"],
        remediation=template["remediation"],
        generated_by="template",
    )


def _get_template_insight(finding: RawFinding) -> AIInsight:
    return _template_insight_for_category(finding.category)


# ── explain_vulnerability (single finding) ─────────────────────────────────────

_EXPLAIN_SYSTEM_PROMPT = (
    "You are a senior cybersecurity expert specializing in banking and "
    "financial systems security. Respond with ONLY a JSON object, no "
    "markdown fences, no preamble."
)


def _build_explain_prompt(sanitized: SanitizedFinding) -> str:
    return f"""A security scan of a banking application flagged the following:

{sanitized.to_prompt_fragment()}

Provide a structured analysis in this exact JSON format:

{{
  "explanation": "2-3 sentence plain language explanation of what this vulnerability is and how it can be exploited. Avoid technical jargon.",
  "business_impact": "2-3 sentences explaining the specific business impact on a banking institution — financial loss, regulatory penalties, reputational damage, customer data risk.",
  "why_auditors_care": "1-2 sentences explaining why RBI/PCI-DSS/SWIFT auditors specifically flag this type of issue.",
  "remediation": "3-5 concrete, actionable steps to fix this vulnerability. Be specific to the technology and ecosystem indicated by the file type."
}}

Focus on banking context: payment systems, customer data, regulatory compliance, and financial risk."""


def _strip_fences(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
    return clean


def _parse_insight_json(raw_response: str) -> dict:
    return json.loads(_strip_fences(raw_response))


def _insight_from_parsed(data: dict, *, generated_by: str) -> AIInsight:
    return AIInsight(
        explanation=data.get("explanation", ""),
        business_impact=data.get("business_impact", data.get("why_auditors_care", "")),
        remediation=data.get("remediation", ""),
        generated_by=generated_by,
    )


def explain_vulnerability(
    finding: RawFinding,
    compliance: Optional[ComplianceMappingData] = None,
) -> AIInsight:
    """
    Generate a business-language insight for a single finding. Tries
    configured providers via the middleware (sanitized input, semantic
    cache, dedup); falls back to a deterministic template if none are
    configured, all fail, or the response can't be parsed.
    """
    sanitized = sanitize_finding(finding, compliance)

    response = get_middleware().dispatch(
        function_name="explain_vulnerability",
        system=_EXPLAIN_SYSTEM_PROMPT,
        prompt=_build_explain_prompt(sanitized),
        semantic_tokens=sanitized.semantic_tokens(),
        max_tokens=600,
    )
    if response is None:
        return _get_template_insight(finding)

    try:
        data = _parse_insight_json(response.text)
        return _insight_from_parsed(data, generated_by=response.provider)
    except json.JSONDecodeError as exc:
        logger.warning("ai_engine.parse_failed — using template", provider=response.provider, error=str(exc))
        return _get_template_insight(finding)


# Backward-compatible alias.
generate_ai_insight = explain_vulnerability


# ── explain_vulnerability_stream (incremental, for interactive display) ───────

_EXPLAIN_STREAM_SYSTEM_PROMPT = (
    "You are a senior cybersecurity expert specializing in banking and "
    "financial systems security. Respond in plain prose only — no JSON, "
    "no markdown headers or bullet lists — suitable for showing to a user "
    "incrementally as it's generated."
)


def _build_explain_stream_prompt(sanitized: SanitizedFinding) -> str:
    return f"""A security scan of a banking application flagged the following:

{sanitized.to_prompt_fragment()}

In 4-6 sentences of continuous plain prose, explain what this vulnerability is, how it could be exploited, its business impact on a banking institution, and the key remediation steps. Do not use JSON, headers, or bullet points — this text is displayed to a user as it streams in."""


def explain_vulnerability_stream(
    finding: RawFinding,
    compliance: Optional[ComplianceMappingData] = None,
) -> Optional[Iterator[str]]:
    """
    Streaming counterpart to `explain_vulnerability()`: same sanitized
    input and semantic-cache signature, but asks for plain prose instead
    of JSON so partial chunks are immediately displayable. Dispatched
    under its own function_name/cache namespace — deliberately kept
    separate from "explain_vulnerability"'s JSON-shaped cache entries,
    since a prose response would break `explain_vulnerabilities_batch`'s
    JSON parsing (and vice versa) if the two ever collided under the same
    key.

    Returns `None` if no provider is configured or every provider fails
    before producing any output; callers should fall back to
    `explain_vulnerability()` (which has its own deterministic template
    fallback) in that case, since there is nothing to stream.
    """
    sanitized = sanitize_finding(finding, compliance)
    return get_middleware().dispatch_stream(
        function_name="explain_vulnerability_stream",
        system=_EXPLAIN_STREAM_SYSTEM_PROMPT,
        prompt=_build_explain_stream_prompt(sanitized),
        semantic_tokens=sanitized.semantic_tokens(),
        max_tokens=500,
    )


# ── explain_vulnerabilities_batch (many findings, few provider calls) ─────────

_BATCH_EXPLAIN_SYSTEM_PROMPT = (
    "You are a senior cybersecurity expert specializing in banking and "
    "financial systems security. You will be given multiple numbered "
    "findings. Respond with ONLY a JSON array with exactly one object per "
    "finding, in the same order, no markdown fences, no preamble."
)


def _build_batch_prompt(reps: list[SanitizedFinding]) -> str:
    blocks = []
    for i, rep in enumerate(reps):
        blocks.append(f"Finding {i}:\n{rep.to_prompt_fragment()}")
    joined = "\n\n".join(blocks)
    return f"""A security scan of a banking application flagged the following findings:

{joined}

Respond with a JSON array of exactly {len(reps)} objects, one per finding above in order, each shaped as:

{{
  "explanation": "2-3 sentence plain language explanation of what this vulnerability is and how it can be exploited. Avoid technical jargon.",
  "business_impact": "2-3 sentences explaining the specific business impact on a banking institution.",
  "why_auditors_care": "1-2 sentences on why RBI/PCI-DSS/SWIFT auditors flag this.",
  "remediation": "3-5 concrete, actionable steps specific to the technology/ecosystem indicated."
}}"""


class _Group:
    __slots__ = ("representative", "semantic_key", "member_indices")

    def __init__(self, representative: SanitizedFinding, semantic_key: str):
        self.representative = representative
        self.semantic_key = semantic_key
        self.member_indices: list[int] = []


def explain_vulnerabilities_batch(
    findings: list[RawFinding],
    compliance_list: list[Optional[ComplianceMappingData]],
    *,
    max_ai_calls: int = 10,
) -> list[AIInsight]:
    """
    Explains a batch of findings using far fewer provider calls than one
    call per finding, in three layers:

      1. Exact duplicates within this batch (same category/severity/CVE/
         package after sanitization — e.g. the same hardcoded-secret
         pattern found in 5 files) collapse to a single representative;
         one explanation is reused across every member.
      2. Each remaining unique representative is checked against the
         Redis semantic cache first — reuse across scans/processes/time,
         not just within this call.
      3. Whatever's left (genuine cache misses) is grouped into token-
         bounded chunks (`chunking.py`) and each chunk is explained with
         ONE provider call requesting a JSON array, instead of one call
         per representative.

    Only CRITICAL/HIGH severity groups are sent to AI at all (mirrors the
    previous cost-control policy); everything else, and anything beyond
    `max_ai_calls` worth of groups, gets the deterministic template.
    """
    n = len(findings)
    if n == 0:
        return []

    sanitized = [sanitize_finding(f, compliance_list[i] if i < len(compliance_list) else None) for i, f in enumerate(findings)]

    # ── Layer 1: intra-batch duplicate-request detection ──────────────────
    groups: dict[str, _Group] = {}
    order: list[str] = []
    for i, s in enumerate(sanitized):
        key = semantic_cache.semantic_key("explain_vulnerability", s.semantic_tokens())
        if key not in groups:
            groups[key] = _Group(s, key)
            order.append(key)
        groups[key].member_indices.append(i)

    results: dict[str, AIInsight] = {}
    ai_eligible: list[_Group] = []
    for key in order:
        group = groups[key]
        severity = group.representative.severity.upper()
        if severity not in {"CRITICAL", "HIGH"}:
            results[key] = _template_insight_for_category(group.representative.category)
            continue

        # ── Layer 2: cross-time response reuse via the Redis semantic cache ──
        cached = semantic_cache.get_cached(key)
        if cached is not None:
            try:
                results[key] = _insight_from_parsed(_parse_insight_json(cached["text"]), generated_by=cached["provider"])
                continue
            except json.JSONDecodeError as exc:
                logger.warning("ai_engine.cached_insight_parse_failed", error=str(exc))
                # Fall through and treat this as a cache miss.

        ai_eligible.append(group)

    # ── Layer 3: chunk the real cache misses, one provider call per chunk ────
    budget = ai_eligible[:max_ai_calls]
    overflow = ai_eligible[max_ai_calls:]
    for group in overflow:
        results[group.semantic_key] = _template_insight_for_category(group.representative.category)

    chunks = chunk_by_tokens(budget, render_fn=lambda g: g.representative.to_prompt_fragment())

    ai_calls_made = 0
    for chunk in chunks:
        chunk_lock_key = "batch:" + "|".join(sorted(g.semantic_key for g in chunk))
        acquired = try_acquire(chunk_lock_key)
        if not acquired:
            reused = wait_for_result(lambda: _all_members_cached(chunk))
            if reused is not None:
                for group in chunk:
                    results[group.semantic_key] = reused[group.semantic_key]
                continue
            # Gave up waiting on the concurrent holder — proceed independently.

        try:
            response = get_middleware().dispatch(
                function_name="explain_vulnerabilities_batch",
                system=_BATCH_EXPLAIN_SYSTEM_PROMPT,
                prompt=_build_batch_prompt([g.representative for g in chunk]),
                cache_payload={"chunk_members": [g.semantic_key for g in chunk]},
                max_tokens=min(2500, 300 * len(chunk) + 200),
            )
            if response is None:
                for group in chunk:
                    results[group.semantic_key] = _template_insight_for_category(group.representative.category)
                continue

            try:
                parsed_array = json.loads(_strip_fences(response.text))
                if not isinstance(parsed_array, list) or len(parsed_array) != len(chunk):
                    raise ValueError(f"expected {len(chunk)} items, got {parsed_array!r}")
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("ai_engine.batch_parse_failed — using template", error=str(exc))
                for group in chunk:
                    results[group.semantic_key] = _template_insight_for_category(group.representative.category)
                continue

            ai_calls_made += 1
            for group, item in zip(chunk, parsed_array):
                insight = _insight_from_parsed(item, generated_by=response.provider)
                results[group.semantic_key] = insight
                # Same value shape ({"text","provider","model"}) as middleware.py's
                # own semantic-cache writes, since both share the
                # "explain_vulnerability" key namespace and either one may read
                # back what the other wrote (see `LLMResponse(**cached)` in
                # middleware.py's dispatch()).
                semantic_cache.set_cached(
                    group.semantic_key,
                    {"text": json.dumps(item), "provider": response.provider, "model": response.model},
                    ttl_seconds=settings.ai_cache_ttl_seconds,
                )
        finally:
            if acquired:
                release(chunk_lock_key)

    logger.info(
        "ai_engine.batch_complete",
        total_findings=n,
        unique_groups=len(order),
        ai_calls_made=ai_calls_made,
    )

    return [results[semantic_cache.semantic_key("explain_vulnerability", sanitized[i].semantic_tokens())] for i in range(n)]


def _all_members_cached(chunk: list[_Group]) -> Optional[dict[str, AIInsight]]:
    resolved = {}
    for group in chunk:
        cached = semantic_cache.get_cached(group.semantic_key)
        if cached is None:
            return None
        try:
            resolved[group.semantic_key] = _insight_from_parsed(_parse_insight_json(cached["text"]), generated_by=cached["provider"])
        except json.JSONDecodeError:
            return None
    return resolved


def generate_batch_insights(
    findings: list[RawFinding],
    compliance_list: list[Optional[ComplianceMappingData]],
    max_ai_calls: int = 10,
) -> list[AIInsight]:
    """Backward-compatible name — delegates to explain_vulnerabilities_batch."""
    return explain_vulnerabilities_batch(findings, compliance_list, max_ai_calls=max_ai_calls)


# ── suggest_remediation ────────────────────────────────────────────────────────

def suggest_remediation(finding: RawFinding) -> str:
    """Focused remediation steps for a single finding, independent of the full explanation."""
    sanitized = sanitize_finding(finding)
    prompt = f"""A security scan flagged the following in a banking application:

{sanitized.to_prompt_fragment()}

Provide 3-5 concrete, actionable remediation steps specific to this vulnerability and the ecosystem indicated by the file type. Respond with plain numbered steps only, no preamble or markdown."""

    response = get_middleware().dispatch(
        function_name="suggest_remediation",
        system="You are a senior application security engineer advising a banking engineering team.",
        prompt=prompt,
        semantic_tokens=sanitized.semantic_tokens(),
        max_tokens=400,
    )
    if response is None:
        return get_template(finding.category)["remediation"]
    return response.text


# ── generate_executive_summary ─────────────────────────────────────────────────
# Deliberately never receives the findings list itself in the prompt — only
# pre-computed aggregate counts/scores, all deterministic. This function was
# already compliant with "never send raw scan results" before this task;
# it's routed through the same middleware for consistent policy enforcement,
# token guarding, and (exact-match, not semantic — see module docstring)
# caching.

_EXEC_SUMMARY_TEMPLATE = (
    "This scan identified {total} finding(s): {critical} critical, {high} high, "
    "{medium} medium, and {low} low/info severity. {risk_sentence}{compliance_sentence}"
    "Priority should be given to remediating critical and high severity findings, "
    "particularly those affecting payment, authentication, or customer data systems, "
    "before the next audit cycle."
)


def _template_executive_summary(
    severity_counts: dict[str, int],
    total: int,
    brs_total: Optional[float],
    risk_level: Optional[str],
    compliance_percentage: Optional[float],
) -> str:
    risk_sentence = ""
    if brs_total is not None and risk_level:
        risk_sentence = f"The aggregate Banking Risk Score is {brs_total:.1f}/100 ({risk_level} risk). "
    compliance_sentence = ""
    if compliance_percentage is not None:
        compliance_sentence = f"Overall regulatory compliance across PCI DSS, RBI, and SWIFT frameworks stands at {compliance_percentage:.1f}%. "

    return _EXEC_SUMMARY_TEMPLATE.format(
        total=total,
        critical=severity_counts.get("CRITICAL", 0),
        high=severity_counts.get("HIGH", 0),
        medium=severity_counts.get("MEDIUM", 0),
        low=severity_counts.get("LOW", 0) + severity_counts.get("INFO", 0),
        risk_sentence=risk_sentence,
        compliance_sentence=compliance_sentence,
    )


def generate_executive_summary(
    findings: list[RawFinding],
    *,
    brs_total: Optional[float] = None,
    risk_level: Optional[str] = None,
    compliance_percentage: Optional[float] = None,
) -> str:
    """
    A short, non-technical summary of an entire scan for executives/auditors
    rather than engineers — overall posture, headline numbers, and what to
    prioritize, without per-finding technical detail.
    """
    severity_counts = Counter(f.severity.upper() for f in findings)
    total = len(findings)

    cache_payload = {
        "total": total,
        "critical": severity_counts.get("CRITICAL", 0),
        "high": severity_counts.get("HIGH", 0),
        "medium": severity_counts.get("MEDIUM", 0),
        "low": severity_counts.get("LOW", 0),
        "brs_total": brs_total,
        "risk_level": risk_level,
        "compliance_percentage": compliance_percentage,
    }

    prompt = f"""A security scan of a banking application produced these results:

Total findings: {total}
Critical: {severity_counts.get('CRITICAL', 0)}
High: {severity_counts.get('HIGH', 0)}
Medium: {severity_counts.get('MEDIUM', 0)}
Low/Info: {severity_counts.get('LOW', 0) + severity_counts.get('INFO', 0)}
Banking Risk Score: {brs_total if brs_total is not None else 'N/A'} ({risk_level or 'N/A'})
Regulatory compliance (PCI DSS / RBI / SWIFT): {compliance_percentage if compliance_percentage is not None else 'N/A'}%

Write a 4-6 sentence executive summary for a non-technical audience (bank executives, auditors): overall security posture, the business risk in plain terms, and what should be prioritized. No jargon, no bullet points, no markdown."""

    response = get_middleware().dispatch(
        function_name="generate_executive_summary",
        system="You are a CISO briefing bank executives and auditors on a security assessment. Be direct and non-technical.",
        prompt=prompt,
        cache_payload=cache_payload,
        max_tokens=500,
    )
    if response is None:
        return _template_executive_summary(severity_counts, total, brs_total, risk_level, compliance_percentage)
    return response.text


# ── generate_risk_explanation ──────────────────────────────────────────────────

def _template_risk_explanation(category: str, severity: str, brs_score: Optional[float], module: Optional[str]) -> str:
    module_phrase = f" in the {module} module" if module else ""
    score_phrase = f" a Banking Risk Score of {brs_score:.1f}/100" if brs_score is not None else " an elevated risk score"
    return (
        f"This {severity.lower()} severity {category} finding{module_phrase} "
        f"was assigned{score_phrase}, reflecting its technical severity combined with the "
        f"business criticality of the affected module, its exposure, and applicable "
        f"regulatory impact. Findings in higher-criticality modules such as payments or "
        f"authentication are scored higher for equivalent technical severity because a "
        f"successful exploit there carries greater financial and compliance consequences."
    )


def generate_risk_explanation(
    finding: RawFinding,
    *,
    brs_score: Optional[float] = None,
    module: Optional[str] = None,
) -> str:
    """Business-language explanation of *why* a finding's Banking Risk Score is what it is."""
    sanitized = sanitize_finding(finding)
    semantic_tokens = sanitized.semantic_tokens() + (module or "unclassified",)

    prompt = f"""A finding was scored using NOVA's Banking Risk Score model:

{sanitized.to_prompt_fragment()}
Business module: {module or 'unclassified'}
Banking Risk Score: {brs_score if brs_score is not None else 'N/A'}/100

In 2-3 sentences, explain in business terms why this finding received this risk score — factor in the module's business criticality, exposure, and regulatory impact, not just the technical severity. No jargon, no markdown."""

    response = get_middleware().dispatch(
        function_name="generate_risk_explanation",
        system="You are explaining a quantitative risk score to a bank risk committee.",
        prompt=prompt,
        semantic_tokens=semantic_tokens,
        max_tokens=300,
    )
    if response is None:
        return _template_risk_explanation(sanitized.category, sanitized.severity, brs_score, module)
    return response.text
