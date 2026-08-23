"""
NOVA — Finding Intelligence Service
Provides deterministic taxonomy explanations, RAG-grounded contextual search queries,
and structured AI-generated insight extraction for individual vulnerability findings.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.metrics import record_rag_operation, record_token_usage
from app.models.finding import Finding
from app.schemas.finding import RawFinding
from app.schemas.finding_intelligence import (
    FindingIntelligenceCitation,
    FindingIntelligenceResponse,
)
from app.services.ai.gateway import get_gateway
from app.services.ai.sanitizer import sanitize_finding
from app.services.ai.templates import get_template
from app.services.ai.token_estimator import estimate_tokens
from app.services.assistant import rerank_manager
from app.services.knowledge_base import embedding_manager, vector_store
from app.services.search_analytics import analytics_service

logger = structlog.get_logger(__name__)
settings = get_settings()

FEATURE_NAME = "finding_intelligence"


@dataclass
class Citation:
    document_id: str
    filename: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    heading: Optional[str] = None
    similarity_score: float = 0.0
    rerank_score: float = 0.0
    excerpt: str = ""


def build_why_detected(finding: Any) -> str:
    """Produce a deterministic, human-readable rationale explaining why and where a finding was detected."""
    raw_sources = getattr(finding, "sources", None) or []
    if not raw_sources:
        src = getattr(finding, "source", None)
        if src:
            raw_sources = [src]

    # Deduplicate sources while preserving insertion order
    sources: List[str] = []
    for s in raw_sources:
        if s and s not in sources:
            sources.append(s)
    sources_str = ", ".join(sources) if sources else "security scanners"

    severity = getattr(finding, "severity", "UNKNOWN")
    category = getattr(finding, "category", "unknown")
    cwe_id = getattr(finding, "cwe_id", None)
    cwe_name = getattr(finding, "cwe_name", None)
    cve = getattr(finding, "cve", None)
    file_path = getattr(finding, "file_path", None)
    line_number = getattr(finding, "line_number", None)

    parts = [f"Detected by {sources_str} as a {severity} severity finding under '{category}'."]

    if cwe_id or cwe_name:
        cwe_parts = []
        if cwe_id:
            cwe_parts.append(cwe_id)
        if cwe_name:
            cwe_parts.append(cwe_name)
        parts.append(f"Classification: {' - '.join(cwe_parts)}.")

    if cve:
        parts.append(f"Identified with advisory {cve}.")

    if file_path:
        loc = f"{file_path}:{line_number}" if line_number is not None else file_path
        parts.append(f"Location: {loc}.")

    return " ".join(parts)


def build_retrieval_query(raw_finding: Any, finding: Any) -> str:
    """Build a search query for knowledge retrieval.

    Includes standardized CWE / OWASP taxonomy and package names,
    while excluding raw titles, descriptions, and verbose regulatory clauses.
    """
    parts = []

    cwe_id = getattr(finding, "cwe_id", None)
    cwe_name = getattr(finding, "cwe_name", None)
    owasp_name = getattr(finding, "owasp_name", None)

    if cwe_id or cwe_name:
        if cwe_id:
            parts.append(cwe_id)
        if cwe_name:
            parts.append(cwe_name)
    else:
        category = getattr(finding, "category", "") or getattr(raw_finding, "category", "") or ""
        formatted_cat = category.replace("_", " ").replace("-", " ")
        if formatted_cat:
            parts.append(formatted_cat)

    if owasp_name:
        parts.append(owasp_name)

    package = getattr(raw_finding, "package", None) or getattr(finding, "package", None)
    if package:
        parts.append(f"{package} package")

    return " ".join(parts)


def build_context_block(citations: List[Citation]) -> str:
    """Format retrieved document chunks into numbered context blocks for prompt injection."""
    if not citations:
        return ""
    blocks = []
    for i, c in enumerate(citations, 1):
        details = []
        if c.filename:
            details.append(f"Source: {c.filename}")
        if c.section_path or c.heading:
            details.append(f"Section: {c.section_path or c.heading}")
        if c.page_number is not None:
            details.append(f"Page: {c.page_number}")
        header = f"[{i}] " + " | ".join(details)
        blocks.append(f"{header}\n{c.excerpt.strip()}")
    return "\n\n".join(blocks)


def parse_generated_explanation(payload: str) -> Dict[str, Any]:
    """Parse JSON explanation payload, stripping Markdown code fences if present."""
    text = payload.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected top-level JSON object (dict)", text, 0)
    return parsed


async def build_intelligence(
    db: AsyncSession,
    finding_id: Any,
    *,
    user_id: Optional[uuid.UUID] = None,
) -> FindingIntelligenceResponse:
    """Orchestrate finding intelligence generation:

    1. Fetch finding & extract deterministic taxonomy / why_detected rationale.
    2. Retrieve relevant context chunks from knowledge base via pgvector + reranker.
    3. If confidence gate passes, generate RAG-grounded insights (or structured template fallback).
    4. Record latency and metrics.
    """
    start = time.monotonic()
    success = True

    finding: Optional[Finding] = None
    if isinstance(finding_id, Finding):
        finding = finding_id
    elif isinstance(finding_id, (str, uuid.UUID)):
        f_uuid = uuid.UUID(str(finding_id)) if isinstance(finding_id, str) else finding_id
        stmt = select(Finding).where(Finding.id == f_uuid)
        result = await db.execute(stmt)
        finding = result.scalar_one_or_none()

    if finding is None:
        raise ValueError(f"Finding not found: {finding_id}")

    why_detected = build_why_detected(finding)
    cwe_id = finding.cwe_id
    cwe_name = finding.cwe_name
    owasp_category = finding.owasp_category
    owasp_name = finding.owasp_name
    mitre_technique_ids = list(finding.mitre_technique_ids or [])
    pci_clause = finding.pci_clause
    rbi_clause = finding.rbi_clause
    swift_clause = finding.swift_clause

    raw_finding = RawFinding(
        title=finding.title,
        severity=finding.severity,
        category=finding.category,
        source=finding.source,
        cvss=finding.cvss,
        file_path=finding.file_path,
        line_number=finding.line_number,
        description=finding.description,
        package=finding.package,
        package_version=finding.package_version,
        cve=finding.cve,
    )

    query = build_retrieval_query(raw_finding, finding)
    citations: List[Citation] = []
    confidence = 0.0
    candidates = []

    try:
        query_embedding = await asyncio.to_thread(embedding_manager.embed_query, query)
        candidates = await vector_store.similarity_search(
            db,
            query_embedding=query_embedding,
            top_k=settings.assistant_retrieval_candidates,
        )

        if candidates:
            documents_text = [chunk.content for chunk, _ in candidates]
            rerank_scores = await asyncio.to_thread(rerank_manager.rerank, query, documents_text)
            ranked = sorted(zip(candidates, rerank_scores), key=lambda pair: pair[1], reverse=True)
            top = ranked[: settings.assistant_top_k]
            confidence = rerank_manager.normalize_confidence(top[0][1]) if top else 0.0

            if confidence >= settings.assistant_min_confidence:
                citations = [
                    Citation(
                        document_id=str(chunk.document_id),
                        filename=chunk.document.filename,
                        page_number=chunk.page_number,
                        section_path=chunk.section_path,
                        heading=chunk.heading,
                        similarity_score=round(similarity, 4),
                        rerank_score=round(rerank_score, 4),
                        excerpt=chunk.content,
                    )
                    for (chunk, similarity), rerank_score in top
                ]
    except Exception as exc:
        logger.warning("finding_intelligence.retrieval_error", error=str(exc))

    grounded = bool(citations and confidence >= settings.assistant_min_confidence)
    plain_english_explanation = None
    business_impact = None
    technical_impact = None
    recommended_remediation = None
    verification_steps: List[str] = []
    code_example = None
    note = None

    if grounded:
        context_block = build_context_block(citations)
        sanitized = sanitize_finding(raw_finding)
        prompt = (
            f"A vulnerability was detected in a banking application codebase.\n\n"
            f"Finding Details (sanitized):\n{sanitized.to_prompt_fragment()}\n\n"
            f"Knowledge Base Excerpts:\n{context_block}\n\n"
            f"Provide a structured JSON explanation with the following fields:\n"
            f"- plain_english_explanation: Clear, non-jargon explanation of what this vulnerability means.\n"
            f"- business_impact: Specific business and financial risks for a banking institution.\n"
            f"- technical_impact: Technical consequence of exploitation.\n"
            f"- recommended_remediation: Step-by-step remediation advice.\n"
            f"- verification_steps: List of strings detailing how to verify the fix.\n"
            f"- code_example: Safe code snippet or configuration fix (or null).\n\n"
            f"Respond with valid JSON only."
        )
        system_prompt = (
            "You are a senior banking cybersecurity and DevSecOps expert. Output ONLY a valid JSON object."
        )

        gen_response = None
        try:
            gateway = get_gateway()
            gen_response = gateway.generate(
                function_name=FEATURE_NAME,
                system=system_prompt,
                prompt=prompt,
                max_tokens=settings.assistant_max_tokens,
                temperature=settings.assistant_temperature,
            )
        except Exception as exc:
            logger.warning("finding_intelligence.generation_failed", error=str(exc))

        if gen_response and gen_response.text:
            try:
                parsed = parse_generated_explanation(gen_response.text)
                plain_english_explanation = parsed.get("plain_english_explanation")
                business_impact = parsed.get("business_impact")
                technical_impact = parsed.get("technical_impact")
                recommended_remediation = parsed.get("recommended_remediation")
                v_steps = parsed.get("verification_steps")
                if isinstance(v_steps, list):
                    verification_steps = [str(s) for s in v_steps]
                elif isinstance(v_steps, str):
                    verification_steps = [v_steps]
                code_example = parsed.get("code_example")
            except Exception:
                pass

        if not plain_english_explanation:
            template = get_template(finding.category)
            plain_english_explanation = template.get("explanation")
            business_impact = template.get("business_impact")
            technical_impact = "Unauthorized access, sensitive data exposure, or elevated privileges."
            recommended_remediation = template.get("remediation")
            verification_steps = [
                "Apply recommended code patch or dependency update.",
                "Run automated security test suite to verify vulnerability resolution.",
            ]
            code_example = None
    else:
        note = "Insufficient relevant context found in knowledge base."

    elapsed_s = time.monotonic() - start
    elapsed_ms = round(elapsed_s * 1000, 1)

    record_rag_operation(FEATURE_NAME, duration_seconds=elapsed_s, success=success)
    await analytics_service.log_search(
        feature=FEATURE_NAME,
        query=query,
        result_count=len(candidates),
        top_score=confidence if confidence > 0 else None,
        latency_ms=elapsed_ms,
        user_id=user_id,
    )

    schema_citations = [
        FindingIntelligenceCitation(
            document_id=c.document_id,
            filename=c.filename,
            page_number=c.page_number,
            section_path=c.section_path,
            heading=c.heading,
            similarity_score=c.similarity_score,
            rerank_score=c.rerank_score,
            excerpt=c.excerpt,
        )
        for c in citations
    ]

    return FindingIntelligenceResponse(
        finding_id=str(finding.id) if finding.id else str(finding_id),
        cwe_id=cwe_id,
        cwe_name=cwe_name,
        owasp_category=owasp_category,
        owasp_name=owasp_name,
        mitre_technique_ids=mitre_technique_ids,
        pci_clause=pci_clause,
        rbi_clause=rbi_clause,
        swift_clause=swift_clause,
        why_detected=why_detected,
        plain_english_explanation=plain_english_explanation,
        business_impact=business_impact,
        technical_impact=technical_impact,
        recommended_remediation=recommended_remediation,
        verification_steps=verification_steps,
        code_example=code_example,
        citations=schema_citations,
        confidence=confidence,
        retrieved_count=len(candidates),
        grounded=grounded,
        note=note,
        latency_ms=elapsed_ms,
    )

