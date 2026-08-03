"""
NOVA — Knowledge Search Service
Orchestrates a search request: embed the query, run pgvector similarity
search with metadata filters, and shape results (similarity score, page,
section, source document) for the API response. This is the only
knowledge-base component app/api/v1/endpoints/knowledge.py calls for
search — it never touches vector_store/embedding_manager directly.

Deliberately returns raw matched chunks only — no LLM call, no
summarization. That's the whole point of stopping at Milestone 1: this
proves the retrieval substrate works before anything is built on top of it.

Milestone 5: every search is persisted (search_analytics.log_search) and
timed into the RAG Prometheus series (record_rag_operation) — both best-
effort, neither can fail the actual search response.
"""

import time
import uuid
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import record_rag_operation
from app.services.knowledge_base import embedding_manager, vector_store
from app.services.search_analytics import analytics_service

logger = structlog.get_logger(__name__)

FEATURE_NAME = "knowledge_search"


async def search(
    db: AsyncSession,
    *,
    query: str,
    top_k: int,
    document_type: Optional[str] = None,
    tag: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
) -> dict:
    start = time.monotonic()
    success = True
    try:
        query_embedding = embedding_manager.embed_query(query)
        matches = await vector_store.similarity_search(
            db,
            query_embedding=query_embedding,
            top_k=top_k,
            document_type=document_type,
            tag=tag,
        )
    except Exception:
        success = False
        raise
    finally:
        took_ms = round((time.monotonic() - start) * 1000, 1)
        record_rag_operation(FEATURE_NAME, duration_seconds=took_ms / 1000, success=success)

    logger.info(
        "knowledge.search",
        query_length=len(query),
        result_count=len(matches),
        took_ms=took_ms,
    )

    results = [
        {
            "document_id": chunk.document_id,
            "filename": chunk.document.filename,
            "chunk_id": chunk.id,
            "content": chunk.content,
            "similarity_score": round(score, 4),
            "page_number": chunk.page_number,
            "heading": chunk.heading,
            "section_path": chunk.section_path,
        }
        for chunk, score in matches
    ]

    await analytics_service.log_search(
        feature=FEATURE_NAME,
        query=query,
        result_count=len(results),
        top_score=results[0]["similarity_score"] if results else None,
        latency_ms=took_ms,
        user_id=user_id,
    )

    return {"query": query, "took_ms": took_ms, "results": results}
