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

    # Stage 1: Knowledge Planner & Vector Search
    plan = knowledge_planner.analyze_and_plan(query)
    dynamic_settings = await settings_service.get_settings(db)
    min_thresh = float(dynamic_settings.get("rag.similarity_threshold", settings.assistant_min_confidence))

    try:
        query_embedding = await asyncio.to_thread(embedding_manager.embed_query, query)
        candidates = await vector_store.similarity_search(
            db,
            query_embedding=query_embedding,
            top_k=int(dynamic_settings.get("rag.top_k", settings.assistant_retrieval_candidates)),
        )

        if not candidates:
            confidence = 0.0
            calibrated_score = 0.0
            c_vector = {}
            consensus_mat = {"status": "no_candidates"}
            citations = []
            context_block = ""
            sufficient = False
        else:
            documents_text = [chunk.content for chunk, _ in candidates]
            rerank_scores = await asyncio.to_thread(rerank_manager.rerank, query, documents_text)
            ranked = sorted(zip(candidates, rerank_scores), key=lambda pair: pair[1], reverse=True)
            top = ranked[: settings.assistant_top_k]

            confidence = rerank_manager.normalize_confidence(top[0][1]) if top else 0.0

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

            context_block = build_context_block(citations)
            agreement_score, consensus_mat = consensus_engine.evaluate_consensus(
                [{"excerpt": c.excerpt} for c in citations]
            )

            calibrated_score, c_vector = confidence_calibrator.calibrate(
                retrieval_score=confidence,
                agreement_score=agreement_score,
            )
            sufficient = calibrated_score >= min_thresh

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
            },
            retrieved_count=len(candidates),
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
