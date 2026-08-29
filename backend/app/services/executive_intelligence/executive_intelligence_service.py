"""
NOVA — Executive Intelligence Service
Orchestrates one executive question: always gather scan-history evidence
+ (best-effort) knowledge-base support first, then stream a grounded
answer. See this package's __init__.py for why evidence is the PRIMARY
grounding (always present) and knowledge-base citations are secondary
(only included when they clear Milestone 2's confidence gate).
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Iterator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.metrics import record_rag_operation, record_token_usage
from app.services.ai.gateway import get_gateway
from app.services.ai.token_estimator import estimate_tokens
from app.services.assistant import rerank_manager
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.executive_intelligence import evidence_service
from app.services.executive_intelligence.evidence_service import ExecutiveEvidenceSnapshot
from app.services.executive_intelligence.prompts import (
    EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT,
    EXECUTIVE_INTELLIGENCE_USER_PROMPT_TEMPLATE,
)
from app.services.knowledge_base import embedding_manager, vector_store
from app.services.search_analytics import analytics_service

logger = structlog.get_logger(__name__)
settings = get_settings()

FEATURE_NAME = "executive_ask"

NO_DATA_MESSAGE = (
    "There is no completed scan history and no relevant knowledge-base documentation yet, "
    "so there is nothing to report on."
)


@dataclass
class Citation:
    document_id: str
    filename: str
    page_number: Optional[int]
    section_path: Optional[str]
    heading: Optional[str]
    similarity_score: float
    excerpt: str


@dataclass
class EvidenceBundle:
    snapshot: ExecutiveEvidenceSnapshot
    evidence_block: str
    citations: list[Citation] = field(default_factory=list)
    kb_confidence: float = 0.0
    kb_retrieved_count: int = 0

    @property
    def has_any_grounding(self) -> bool:
        return self.snapshot.has_any_data or len(self.citations) > 0


async def gather_evidence(
    db: AsyncSession, *, question: str, user_id: Optional[uuid.UUID] = None
) -> EvidenceBundle:
    start = time.monotonic()
    success = True
    try:
        snapshot = await evidence_service.build_evidence_snapshot(db)
        evidence_block = evidence_service.render_evidence_block(snapshot)

        query_embedding = await asyncio.to_thread(embedding_manager.embed_query, question)
        candidates = await vector_store.similarity_search(
            db, query_embedding=query_embedding, top_k=settings.assistant_retrieval_candidates
        )

        citations: list[Citation] = []
        kb_confidence = 0.0
        if candidates:
            documents_text = [chunk.content for chunk, _ in candidates]
            rerank_scores = await asyncio.to_thread(rerank_manager.rerank, question, documents_text)
            ranked = sorted(zip(candidates, rerank_scores), key=lambda pair: pair[1], reverse=True)
            top = ranked[: settings.assistant_top_k]
            raw_conf = rerank_manager.normalize_confidence(top[0][1]) if top else 0.0
            doc_dates = [chunk.document.created_at for (chunk, _), _ in top if hasattr(chunk, "document") and getattr(chunk, "document", None)]
            freshness_score = confidence_calibrator.compute_freshness(doc_dates)
            calibrated_score, _ = confidence_calibrator.calibrate(
                retrieval_score=raw_conf,
                freshness_score=freshness_score,
                source_reliability=0.95,
            )
            kb_confidence = calibrated_score
            if kb_confidence >= settings.assistant_min_confidence:

                citations = [
                    Citation(
                        document_id=str(chunk.document_id),
                        filename=chunk.document.filename,
                        page_number=chunk.page_number,
                        section_path=chunk.section_path,
                        heading=chunk.heading,
                        similarity_score=round(similarity, 4),
                        excerpt=chunk.content,
                    )
                    for (chunk, similarity), _ in top
                ]

        bundle = EvidenceBundle(
            snapshot=snapshot,
            evidence_block=evidence_block,
            citations=citations,
            kb_confidence=kb_confidence,
            kb_retrieved_count=len(candidates),
        )
    except Exception:
        success = False
        raise
    finally:
        record_rag_operation(FEATURE_NAME, duration_seconds=(time.monotonic() - start), success=success)

    await analytics_service.log_search(
        feature=FEATURE_NAME,
        query=question,
        result_count=bundle.kb_retrieved_count,
        top_score=bundle.kb_confidence or None,
        latency_ms=round((time.monotonic() - start) * 1000, 1),
        user_id=user_id,
    )
    return bundle


def _citation_header(citation: Citation) -> str:
    parts = [f"Source: {citation.filename}"]
    section = citation.section_path or citation.heading
    if section:
        parts.append(f"Section: {section}")
    if citation.page_number is not None:
        parts.append(f"Page: {citation.page_number}")
    return ", ".join(parts)


def build_context_section(citations: list[Citation]) -> str:
    if not citations:
        return ""
    block = "\n\n".join(f"[{i}] ({_citation_header(c)})\n{c.excerpt}" for i, c in enumerate(citations, start=1))
    return f"Knowledge base excerpts (supplementary context only — never a source for statistics):\n{block}\n\n"


def format_history(history: list[dict], max_turns: int) -> str:
    recent = history[-max_turns:] if max_turns > 0 else []
    if not recent:
        return "(no earlier turns)"
    return "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in recent)


def stream_answer(evidence: EvidenceBundle, *, question: str, history: list[dict]) -> Iterator[str]:
    context_section = build_context_section(evidence.citations)
    history_block = format_history(history, settings.assistant_max_history_turns)
    prompt = EXECUTIVE_INTELLIGENCE_USER_PROMPT_TEMPLATE.format(
        evidence_block=evidence.evidence_block,
        context_section=context_section,
        history_block=history_block,
        question=question,
    )

    chunk_iter = None
    try:
        chunk_iter = get_gateway().stream(
            function_name="executive_intelligence",
            system=EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=settings.assistant_max_tokens,
            temperature=settings.assistant_temperature,
        )
    except Exception as e:
        logger.warning("llm_gateway_stream_error", error=str(e))

    if chunk_iter is not None:
        prompt_tokens = estimate_tokens(EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT) + estimate_tokens(prompt)
        completion_chars = 0
        for _, text in chunk_iter:
            completion_chars += len(text)
            yield text
        record_token_usage(
            FEATURE_NAME, prompt_tokens=prompt_tokens, completion_tokens=estimate_tokens("x" * completion_chars)
        )
        return

    # Structured Executive AI Intelligence Synthesizer fallback
    logger.info("executive_intelligence_service.generating_structured_intelligence_fallback")
    s = evidence.snapshot
    avg_brs = f"{s.portfolio_average_brs:.2f}" if s.portfolio_average_brs is not None else "N/A"

    lines = [
        "## 📊 Executive Security Intelligence Report\n",
        f"**User Query**: \"{question}\"\n\n",
        "### 🛡️ Portfolio Risk Metrics\n",
        f"- **Portfolio Average BRS Score**: `{avg_brs}` / 100.0\n",
        f"- **Total Monitored Repositories**: `{s.total_repositories}`\n",
        f"- **Total Completed Scans**: `{s.total_completed_scans}`\n",
        f"- **Total Identified Findings**: `{s.total_findings}`\n\n",
        "### 📂 Scanned Repositories & Risk Scores\n",
    ]

    if s.top_risk_repositories:
        for repo in s.top_risk_repositories:
            risk_level = repo.latest_brs_risk_level or "Unknown"
            score = f"{repo.latest_brs_score:.2f}"
            lines.append(f"- **{repo.repository_name}** — BRS: `{score}` ({risk_level} Risk)\n")
    else:
        lines.append("- No active repositories logged yet.\n")
    lines.append("\n")

    lines.append("### 🔍 Vulnerabilities by Severity\n")
    crit = s.findings_by_severity.get("CRITICAL", 0)
    high = s.findings_by_severity.get("HIGH", 0)
    med = s.findings_by_severity.get("MEDIUM", 0)
    low = s.findings_by_severity.get("LOW", 0)
    lines.append(f"- 🔴 **Critical**: `{crit}`\n")
    lines.append(f"- 🟠 **High**: `{high}`\n")
    lines.append(f"- 🟡 **Medium**: `{med}`\n")
    lines.append(f"- 🔵 **Low**: `{low}`\n\n")

    if s.compliance_by_framework:
        lines.append("### ⚖️ Regulatory Compliance Posture\n")
        for fw in s.compliance_by_framework:
            status = "Compliant ✅" if fw.non_compliant_repo_count == 0 else f"{fw.non_compliant_repo_count} Non-Compliant Repo(s) ⚠️"
            lines.append(f"- **{fw.framework_name}**: {status} (`{fw.total_violations}` active violations)\n")
        lines.append("\n")

    lines.append("### 📌 Recommended Executive Action Items\n")
    if crit > 0 or high > 0:
        lines.append(f"1. **Remediation Focus**: Prioritize fixing the `{crit}` Critical and `{high}` High findings in high-risk repositories.\n")
    lines.append("2. **DevSecOps Pipeline**: Mandate automated Semgrep and Secrets scanning on all pull requests.\n")
    lines.append("3. **Compliance Audit**: Download latest SARIF and PDF executive reports for stakeholder review.\n")

    if evidence.citations:
        lines.append("\n### 📚 Relevant Knowledge Base Excerpts\n")
        for i, c in enumerate(evidence.citations, start=1):
            lines.append(f"[{i}] **{_citation_header(c)}**\n{c.excerpt}\n\n")

    full_text = "".join(lines)
    for part in full_text.split("\n"):
        yield part + "\n"
