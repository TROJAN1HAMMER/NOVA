"""
NOVA — RAG Benchmark Service
Runs a small, fixed set of timing probes against the live embedding
model, reranker, vector store, and (if configured) LLM gateway — a
performance smoke test, not an accuracy/quality benchmark. See this
package's __init__.py for why this is unrelated to the pre-existing
scanner-accuracy "benchmark suite."

Each stage is timed independently so a slow run can be attributed to a
specific layer (e.g. "the embedding model is slow" vs. "the LLM provider
is slow") rather than only reporting one opaque end-to-end number.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.gateway import get_gateway
from app.services.assistant import rerank_manager
from app.services.knowledge_base import embedding_manager, vector_store

# Deliberately generic, not tied to any one uploaded document's content —
# this measures pipeline latency, not retrieval quality (Milestone 3's
# manual testing procedure already covers quality/relevance).
BENCHMARK_QUERIES = [
    "What are the password rotation and access control requirements?",
    "How should a vulnerable third-party dependency be remediated?",
    "What compliance controls apply to payment card data handling?",
]


@dataclass
class StageTiming:
    stage: str
    avg_duration_ms: float
    detail: Optional[str] = None


@dataclass
class BenchmarkResult:
    ran_at: str
    stages: list[StageTiming] = field(default_factory=list)
    total_duration_ms: float = 0.0
    documents_indexed: int = 0
    llm_configured: bool = False


async def _count_indexed_documents(db: AsyncSession) -> int:
    from sqlalchemy import func, select

    from app.models.knowledge import KnowledgeDocument

    result = await db.execute(
        select(func.count(KnowledgeDocument.id)).where(
            KnowledgeDocument.is_latest.is_(True), KnowledgeDocument.status == "indexed"
        )
    )
    return result.scalar_one()


async def run_benchmark(db: AsyncSession) -> BenchmarkResult:
    overall_start = time.monotonic()
    stages: list[StageTiming] = []

    # A random suffix per call defeats the embedding cache (Milestone 5's
    # own caching layer) deliberately — this measures real model
    # inference latency, not a cache hit, which would otherwise make the
    # embedding stage look artificially fast on a second run.
    embed_start = time.monotonic()
    for query in BENCHMARK_QUERIES:
        embedding_manager.embed_query(f"{query} [benchmark:{uuid.uuid4().hex[:8]}]")
    embed_ms = (time.monotonic() - embed_start) * 1000 / len(BENCHMARK_QUERIES)
    stages.append(StageTiming("embedding_per_query", round(embed_ms, 2)))

    search_start = time.monotonic()
    total_results = 0
    last_candidates = []
    for query in BENCHMARK_QUERIES:
        query_embedding = embedding_manager.embed_query(query)
        results = await vector_store.similarity_search(db, query_embedding=query_embedding, top_k=10)
        total_results += len(results)
        last_candidates = results
    search_ms = (time.monotonic() - search_start) * 1000 / len(BENCHMARK_QUERIES)
    stages.append(
        StageTiming(
            "vector_search_per_query",
            round(search_ms, 2),
            detail=f"{total_results} total matches across {len(BENCHMARK_QUERIES)} queries",
        )
    )

    if last_candidates:
        rerank_start = time.monotonic()
        rerank_manager.rerank(BENCHMARK_QUERIES[-1], [chunk.content for chunk, _ in last_candidates])
        rerank_ms = (time.monotonic() - rerank_start) * 1000
        stages.append(StageTiming("rerank_candidates", round(rerank_ms, 2), detail=f"{len(last_candidates)} candidates"))

    llm_configured = False
    llm_start = time.monotonic()
    response = get_gateway().complete(
        function_name="benchmark",
        system="Reply with a single word.",
        prompt="Say 'ready'.",
        cache_payload={"benchmark": uuid.uuid4().hex},  # unique payload — never a cache hit
        max_tokens=10,
        use_cache=False,
    )
    llm_ms = (time.monotonic() - llm_start) * 1000
    if response is not None:
        llm_configured = True
        stages.append(StageTiming("llm_completion", round(llm_ms, 2), detail=f"provider={response.provider}"))
    else:
        stages.append(StageTiming("llm_completion", round(llm_ms, 2), detail="no provider configured"))

    documents_indexed = await _count_indexed_documents(db)

    return BenchmarkResult(
        ran_at=datetime.now(timezone.utc).isoformat(),
        stages=stages,
        total_duration_ms=round((time.monotonic() - overall_start) * 1000, 2),
        documents_indexed=documents_indexed,
        llm_configured=llm_configured,
    )
