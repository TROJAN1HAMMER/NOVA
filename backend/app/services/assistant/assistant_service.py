"""
AEKOF — Integrated Assistant RAG Service
Orchestrates the 5-stage adaptive evidence cascade:
Stage 0: FAQ Keyword Matcher
Stage 1: Knowledge Planner & pgvector Dense Retrieval
Stage 2: FastEmbed Cross-Encoder Reranker
Stage 3: Evidence Consensus Engine & 8-Dimensional Calibrator
Stage 4: Controlled Exa Web Fallback & Multi-Provider LLM Streaming
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.metrics import record_rag_operation, record_token_usage
from app.services.ai.consensus_engine import consensus_engine
from app.services.ai.gateway import get_gateway
from app.services.ai.token_estimator import estimate_tokens
from app.services.assistant import rerank_manager
from app.services.assistant.evidence_fusion import UnifiedEvidenceItem, evidence_fusion_engine
from app.services.assistant.planner import knowledge_planner
from app.services.assistant.prompts import ASSISTANT_SYSTEM_PROMPT
from app.services.exa_service import exa_service
from app.services.faq_service import faq_service
from app.services.knowledge_base import embedding_manager, vector_store
from app.services.search_analytics import analytics_service
from app.services.search_analytics.calibrator import confidence_calibrator
from app.services.settings_service import settings_service

logger = structlog.get_logger(__name__)
settings = get_settings()

FEATURE_NAME = "assistant_chat"
INSUFFICIENT_CONTEXT_MESSAGE = "I could not find sufficient information inside the knowledge base."


def is_security_query(query: str) -> bool:
    """Deterministic routing check for security/vulnerability intent."""
    q_lower = query.lower()
    security_keywords = [
        "vulnerability", "vulnerabilities", "security", "cve", "cwe", "sqli", "sql injection",
        "xss", "cross-site", "csrf", "finding", "findings", "remediation", "scan", "sast",
        "semgrep", "joern", "ast-grep", "secrets", "pip-audit", "osv", "nvd", "docker",
        "rbi", "pci", "swift", "compliance", "severity", "critical", "cvss", "brs",
        "exploit", "patch", "fix", "flaw", "misconfiguration"
    ]
    return any(kw in q_lower for kw in security_keywords)


@dataclass
class Citation:
    document_id: str
    filename: str
    page_number: Optional[int]
    section_path: Optional[str]
    heading: Optional[str]
    similarity_score: float
    rerank_score: float
    excerpt: str
    source_type: str = "knowledge_doc"
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    severity: Optional[str] = None
    cwe_id: Optional[str] = None
    cve: Optional[str] = None


@dataclass
class RetrievalResult:
    citations: list[Citation]
    context_block: str
    confidence: float
    confidence_vector: dict
    calibrated_trust_score: float
    consensus_matrix: dict
    reasoning_trace: dict
    retrieved_count: int
    sufficient: bool
    retrieval_latency_ms: float
    faq_match_answer: Optional[str] = None
    exa_fallback_answer: Optional[str] = None


def _citation_header(citation: Citation) -> str:
    if citation.source_type == "security_finding":
        parts = [f"Security Finding [{citation.severity or 'INFO'}]"]
        if citation.file_path:
            loc = f"{citation.file_path}:{citation.line_number}" if citation.line_number else citation.file_path
            parts.append(f"Location: {loc}")
        if citation.cwe_id:
            parts.append(f"CWE: {citation.cwe_id}")
        if citation.cve:
            parts.append(f"CVE: {citation.cve}")
        return ", ".join(parts)
    else:
        parts = [f"Source: {citation.filename}"]
        section = citation.section_path or citation.heading
        if section:
            parts.append(f"Section: {section}")
        if citation.page_number is not None:
            parts.append(f"Page: {citation.page_number}")
        return ", ".join(parts)


def build_context_block(citations: list[Citation]) -> str:
    return "\n\n".join(
        f"[{index}] ({_citation_header(citation)})\n{citation.excerpt}"
        for index, citation in enumerate(citations, start=1)
    )


def format_history(history: list[dict], max_turns: int) -> str:
    recent = history[-max_turns:] if max_turns > 0 else []
    return "\n".join(f"{turn['role'].capitalize()}: {turn['content']}" for turn in recent)


async def retrieve_and_orchestrate(
    db: AsyncSession, *, query: str, user_id: Optional[uuid.UUID] = None
) -> RetrievalResult:
    start = time.monotonic()
    success = True
    fallback_triggered = False

    # Stage 0: Deterministic FAQ Matcher (<1ms)
    faq_match = await faq_service.match_faq(db, query)
    if faq_match:
        latency = round((time.monotonic() - start) * 1000, 1)
        await analytics_service.log_search(
            feature=FEATURE_NAME,
            query=query,
            result_count=1,
            top_score=1.0,
            latency_ms=latency,
            user_id=user_id,
        )
        return RetrievalResult(
            citations=[],
            context_block="",
            confidence=1.0,
            confidence_vector={"C_faq": 1.0},
            calibrated_trust_score=1.0,
            consensus_matrix={"status": "faq_match"},
            reasoning_trace={"stage": "Stage 0 (FAQ Axiom Match)", "latency_ms": latency},
            retrieved_count=1,
            sufficient=True,
            retrieval_latency_ms=latency,
            faq_match_answer=faq_match.response,
        )

    # Stage 1: Dual-Track Retrieval & Evidence Fusion
    plan = knowledge_planner.analyze_and_plan(query)
    dynamic_settings = await settings_service.get_settings(db)
    min_thresh = float(dynamic_settings.get("rag.similarity_threshold", settings.assistant_min_confidence))
    is_sec = is_security_query(query)

    try:
        # Track A: Knowledge Vector Retrieval
        query_embedding = await asyncio.to_thread(embedding_manager.embed_query, query)
        knowledge_candidates = await vector_store.similarity_search(
            db,
            query_embedding=query_embedding,
            top_k=int(dynamic_settings.get("rag.top_k", settings.assistant_retrieval_candidates)),
        )

        knowledge_items = [
            evidence_fusion_engine.format_knowledge_chunk_as_evidence(chunk, sim)
            for chunk, sim in knowledge_candidates
        ]

        # Track B: Security Evidence Retrieval
        security_items: list[UnifiedEvidenceItem] = []
        if is_sec:
            # Security Intelligence service provider
            try:
                from app.services.security_intelligence.evidence_provider import security_evidence_provider
                sec_intel_evidence = security_evidence_provider.get_security_evidence(
                    query=query, top_k=int(dynamic_settings.get("rag.top_k", settings.assistant_retrieval_candidates))
                )
                for item_dict in sec_intel_evidence:
                    security_items.append(
                        UnifiedEvidenceItem(
                            source_id=item_dict["source_id"],
                            source_type=item_dict["source_type"],
                            title=item_dict["title"],
                            content=item_dict["content"],
                            similarity_score=item_dict["score"],
                            rerank_score=item_dict["score"],
                            reliability_weight=item_dict["reliability_weight"],
                            file_path=item_dict.get("file_path"),
                            cwe_id=item_dict.get("cwe_id"),
                            cve=item_dict.get("cve"),
                            severity=item_dict.get("metadata", {}).get("severity"),
                        )
                    )
            except Exception as exc:
                logger.warning("assistant_service.sec_intel_evidence_error", error=str(exc))

        # Stage 2: Evidence Fusion & Cross-Encoder Reranking
        fused_items = evidence_fusion_engine.fuse_evidence(
            knowledge_items, security_items, top_k=int(dynamic_settings.get("rag.top_k", settings.assistant_retrieval_candidates))
        )

        if not fused_items:
            confidence = 0.0
            calibrated_score = 0.0
            c_vector = {}
            consensus_mat = {"status": "no_candidates"}
            citations = []
            context_block = ""
            sufficient = False
            trust_eval = {
                "trust_score": 0.0,
                "confidence_vector": c_vector,
                "decision": "FALLBACK_WEB" if dynamic_settings.get("rag.enable_web_search", True) else "ABSTAIN",
                "reasons": ["No evidence chunks retrieved."],
            }
            safety_exp = confidence_calibrator.build_safety_explanation(
                trust_eval=trust_eval,
                c_vector=c_vector,
                consensus_mat=consensus_mat,
                citations=[],
                is_security_query=is_sec,
            )
        else:
            documents_text = [item.content for item in fused_items]
            rerank_scores = await asyncio.to_thread(rerank_manager.rerank, query, documents_text)

            for item, r_score in zip(fused_items, rerank_scores):
                item.rerank_score = round(r_score, 4)

            ranked_items = sorted(
                fused_items,
                key=lambda item: (item.rerank_score * item.reliability_weight),
                reverse=True,
            )
            top_items = ranked_items[: settings.assistant_top_k]

            confidence = rerank_manager.normalize_confidence(top_items[0].rerank_score) if top_items else 0.0

            citations = [
                Citation(
                    document_id=item.source_id,
                    filename=item.title,
                    page_number=item.provenance.get("page_number"),
                    section_path=item.provenance.get("section_path"),
                    heading=item.provenance.get("heading"),
                    similarity_score=item.similarity_score,
                    rerank_score=item.rerank_score,
                    excerpt=item.content,
                    source_type=item.source_type,
                    file_path=item.file_path,
                    line_number=item.line_number,
                    severity=item.severity,
                    cwe_id=item.cwe_id,
                    cve=item.cve,
                )
                for item in top_items
            ]

            context_block = build_context_block(citations)
            agreement_score, consensus_mat = consensus_engine.evaluate_consensus(
                [
                    {
                        "source_id": c.document_id,
                        "excerpt": c.excerpt,
                        "title": c.filename,
                        "source_type": c.source_type,
                        "file_path": c.file_path,
                        "line_number": c.line_number,
                        "severity": c.severity,
                        "cwe_id": c.cwe_id,
                        "cve": c.cve,
                    }
                    for c in citations
                ]
            )

            doc_dates = [item.timestamp for item in top_items if item.timestamp]
            freshness_score = confidence_calibrator.compute_freshness(doc_dates)
            source_types = [item.source_type for item in top_items]
            source_reliability = confidence_calibrator.compute_source_reliability(source_types)
            reasoning_score = confidence_calibrator.compute_reasoning_score(
                candidate_count=len(fused_items),
                top_k=settings.assistant_top_k,
                plan_complexity=plan.complexity_level,
            )
            citation_coverage = round(min(len(citations) / max(settings.assistant_top_k, 1), 1.0), 4)
            hallucination_risk = confidence_calibrator.compute_hallucination_risk(
                retrieval_score=confidence,
                agreement_score=agreement_score,
                citation_coverage=citation_coverage,
            )

            calibrated_score, c_vector = confidence_calibrator.calibrate(
                retrieval_score=confidence,
                agreement_score=agreement_score,
                citation_coverage=citation_coverage,
                reasoning_score=reasoning_score,
                freshness_score=freshness_score,
                hallucination_risk=hallucination_risk,
                source_reliability=source_reliability,
                user_feedback_score=0.5,
            )
            trust_eval = confidence_calibrator.evaluate_trust_decision(
                trust_score=calibrated_score,
                c_vector=c_vector,
                min_thresh=min_thresh,
                enable_web_fallback=dynamic_settings.get("rag.enable_web_search", True),
                is_security_query=is_sec,
            )
            sufficient = trust_eval["decision"] in {"GENERATE", "GENERATE_WITH_WARNING"}
            safety_exp = confidence_calibrator.build_safety_explanation(
                trust_eval=trust_eval,
                c_vector=c_vector,
                consensus_mat=consensus_mat,
                citations=citations,
                is_security_query=is_sec,
            )


        # Exa Web Search Fallback if insufficient
        exa_answer = None
        if not sufficient and dynamic_settings.get("rag.enable_web_search", True):
            logger.info("assistant_service.triggering_exa_fallback", query=query)
            exa_answer = exa_service.search_fallback(query)
            fallback_triggered = True

        retrieval_latency = round((time.monotonic() - start) * 1000, 1)

        result = RetrievalResult(
            citations=citations,
            context_block=context_block,
            confidence=confidence,
            confidence_vector=c_vector,
            calibrated_trust_score=calibrated_score,
            consensus_matrix=consensus_mat,
            reasoning_trace={
                "plan": {
                    "complexity": plan.complexity_level,
                    "active_paths": plan.active_paths,
                },
                "confidence_calibrated": calibrated_score,
                "fallback_triggered": fallback_triggered,
                "latency_ms": retrieval_latency,
                "trust_decision": trust_eval["decision"],
                "safety_explanation": safety_exp,
            },
            retrieved_count=len(fused_items),
            sufficient=sufficient or bool(exa_answer),
            retrieval_latency_ms=retrieval_latency,
            exa_fallback_answer=exa_answer,
        )

    except Exception:
        success = False
        raise
    finally:
        record_rag_operation(FEATURE_NAME, duration_seconds=(time.monotonic() - start), success=success)

    await analytics_service.log_search(
        feature=FEATURE_NAME,
        query=query,
        result_count=result.retrieved_count,
        top_score=result.citations[0].similarity_score if result.citations else None,
        latency_ms=result.retrieval_latency_ms,
        user_id=user_id,
    )

    return result


def stream_answer(retrieval: RetrievalResult, *, message: str, history: list[dict]) -> Iterator[str]:
    if retrieval.faq_match_answer:
        yield retrieval.faq_match_answer
        return

    if retrieval.exa_fallback_answer:
        yield retrieval.exa_fallback_answer
        return

    history_text = format_history(history, settings.assistant_max_history_turns)
    prompt_sections = []
    if history_text:
        prompt_sections.append(f"Conversation so far:\n{history_text}")
    prompt_sections.append(f"Context excerpts:\n{retrieval.context_block}")
    prompt_sections.append(f"Question: {message}")
    prompt = "\n\n".join(prompt_sections)

    chunk_iter = get_gateway().stream(
        function_name="assistant_chat",
        system=ASSISTANT_SYSTEM_PROMPT,
        prompt=prompt,
        max_tokens=settings.assistant_max_tokens,
        temperature=settings.assistant_temperature,
    )

    if chunk_iter is not None:
        prompt_tokens = estimate_tokens(ASSISTANT_SYSTEM_PROMPT) + estimate_tokens(prompt)
        completion_chars = 0
        for _, text in chunk_iter:
            completion_chars += len(text)
            yield text
        record_token_usage(
            FEATURE_NAME, prompt_tokens=prompt_tokens, completion_tokens=estimate_tokens("x" * completion_chars)
        )
        return

    yield "No AI model is currently configured, so here are the most relevant excerpts found in the knowledge base:\n\n"
    for index, citation in enumerate(retrieval.citations, start=1):
        yield f"[{index}] ({_citation_header(citation)})\n{citation.excerpt}\n\n"
