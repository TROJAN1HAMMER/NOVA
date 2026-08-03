"""
AEKOF — Prometheus Metrics Subsystem
"""

import time
from typing import Optional

import redis
import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

REGISTRY = CollectorRegistry()

# ── 1. HTTP metrics (in-process, per-pod) ──────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "aekof_http_requests_total",
    "Total HTTP requests handled by this pod",
    ["method", "path", "status"],
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aekof_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    registry=REGISTRY,
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "aekof_http_requests_in_progress",
    "HTTP requests currently being handled by this pod",
    registry=REGISTRY,
)

async def collect_business_metrics(db: AsyncSession) -> None:
    """Placeholder for platform level metrics."""
    pass


# ── 2. Redis Client ──────────────────────────────────────────────────────────

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


# ── 3. RAG metrics ────────────────────────────────────────────────────────────

RAG_DOCUMENTS_BY_STATUS = Gauge(
    "aekof_rag_documents_by_status",
    "Current knowledge base document count by status (latest version of each document only)",
    ["status"],
    registry=REGISTRY,
)
RAG_OPERATIONS = Gauge(
    "aekof_rag_operations",
    "Cumulative RAG operation outcomes, mirrored from Redis",
    ["feature", "outcome"],
    registry=REGISTRY,
)
RAG_AVG_LATENCY_SECONDS = Gauge(
    "aekof_rag_avg_latency_seconds",
    "Rolling average end-to-end latency of a RAG operation",
    ["feature"],
    registry=REGISTRY,
)
RAG_CACHE_OPERATIONS = Gauge(
    "aekof_rag_cache_operations",
    "Cumulative embedding/rerank cache hit/miss counts",
    ["cache", "outcome"],
    registry=REGISTRY,
)
RAG_TOKEN_USAGE_ESTIMATED = Gauge(
    "aekof_rag_token_usage_estimated_total",
    "Estimated cumulative token usage for RAG LLM calls",
    ["feature", "direction"],
    registry=REGISTRY,
)
RAG_FEEDBACK = Gauge(
    "aekof_rag_feedback_total",
    "Cumulative user feedback submissions on RAG outputs",
    ["feature", "rating"],
    registry=REGISTRY,
)

KNOWN_RAG_FEATURES = ("knowledge_search", "assistant_chat", "executive_ask")
KNOWN_RAG_CACHES = ("embedding", "rerank")


def _rag_metrics_key(suffix: str) -> str:
    return f"aekof:metrics:rag:{suffix}"


def record_rag_operation(feature: str, *, duration_seconds: float, success: bool) -> None:
    try:
        r = _get_redis()
        key = _rag_metrics_key(f"ops:{feature}")
        pipe = r.pipeline()
        pipe.hincrby(key, "success" if success else "error", 1)
        pipe.hincrbyfloat(key, "duration_sum", duration_seconds)
        pipe.hincrby(key, "duration_count", 1)
        pipe.expire(key, 60 * 60 * 24 * 7)
        pipe.execute()
    except redis.RedisError as exc:
        logger.warning("metrics.rag_operation_record_failed", feature=feature, error=str(exc))


def record_cache_result(cache: str, *, hit: bool) -> None:
    try:
        r = _get_redis()
        key = _rag_metrics_key(f"cache:{cache}")
        pipe = r.pipeline()
        pipe.hincrby(key, "hit" if hit else "miss", 1)
        pipe.expire(key, 60 * 60 * 24 * 7)
        pipe.execute()
    except redis.RedisError as exc:
        logger.warning("metrics.rag_cache_record_failed", cache=cache, error=str(exc))


def record_token_usage(feature: str, *, prompt_tokens: int, completion_tokens: int) -> None:
    try:
        r = _get_redis()
        key = _rag_metrics_key(f"tokens:{feature}")
        pipe = r.pipeline()
        pipe.hincrby(key, "prompt", prompt_tokens)
        pipe.hincrby(key, "completion", completion_tokens)
        pipe.expire(key, 60 * 60 * 24 * 7)
        pipe.execute()
    except redis.RedisError as exc:
        logger.warning("metrics.rag_token_record_failed", feature=feature, error=str(exc))


def record_feedback(feature: str, *, positive: bool) -> None:
    try:
        r = _get_redis()
        key = _rag_metrics_key(f"feedback:{feature}")
        pipe = r.pipeline()
        pipe.hincrby(key, "positive" if positive else "negative", 1)
        pipe.expire(key, 60 * 60 * 24 * 30)
        pipe.execute()
    except redis.RedisError as exc:
        logger.warning("metrics.rag_feedback_record_failed", feature=feature, error=str(exc))


def collect_rag_redis_metrics() -> None:
    try:
        r = _get_redis()
        for feature in KNOWN_RAG_FEATURES:
            ops = r.hgetall(_rag_metrics_key(f"ops:{feature}"))
            duration_count = int(ops.get("duration_count", 0))
            RAG_OPERATIONS.labels(feature=feature, outcome="success").set(int(ops.get("success", 0)))
            RAG_OPERATIONS.labels(feature=feature, outcome="error").set(int(ops.get("error", 0)))
            RAG_AVG_LATENCY_SECONDS.labels(feature=feature).set(
                float(ops.get("duration_sum", 0.0)) / duration_count if duration_count else 0.0
            )

            tokens = r.hgetall(_rag_metrics_key(f"tokens:{feature}"))
            RAG_TOKEN_USAGE_ESTIMATED.labels(feature=feature, direction="prompt").set(int(tokens.get("prompt", 0)))
            RAG_TOKEN_USAGE_ESTIMATED.labels(feature=feature, direction="completion").set(
                int(tokens.get("completion", 0))
            )

            feedback = r.hgetall(_rag_metrics_key(f"feedback:{feature}"))
            RAG_FEEDBACK.labels(feature=feature, rating="positive").set(int(feedback.get("positive", 0)))
            RAG_FEEDBACK.labels(feature=feature, rating="negative").set(int(feedback.get("negative", 0)))

        for cache in KNOWN_RAG_CACHES:
            cache_data = r.hgetall(_rag_metrics_key(f"cache:{cache}"))
            RAG_CACHE_OPERATIONS.labels(cache=cache, outcome="hit").set(int(cache_data.get("hit", 0)))
            RAG_CACHE_OPERATIONS.labels(cache=cache, outcome="miss").set(int(cache_data.get("miss", 0)))
    except redis.RedisError as exc:
        logger.warning("metrics.rag_redis_collect_failed", error=str(exc))


async def collect_rag_document_metrics(db: AsyncSession) -> None:
    from app.models.knowledge import KnowledgeDocument

    status_counts = await db.execute(
        select(KnowledgeDocument.status, func.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.is_latest.is_(True))
        .group_by(KnowledgeDocument.status)
    )
    counts_by_status = dict(status_counts.all())
    for status in ("pending", "processing", "indexed", "failed"):
        RAG_DOCUMENTS_BY_STATUS.labels(status=status).set(counts_by_status.get(status, 0))


class ScannerTimer:
    def __init__(self) -> None:
        self._start = 0.0

    def __enter__(self) -> "ScannerTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start
