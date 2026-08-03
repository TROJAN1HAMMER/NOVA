"""
NOVA — Embedding Manager
Wraps a local ONNX-runtime embedding model (fastembed) so the rest of the
knowledge base never imports fastembed/onnxruntime directly — the same
"one gateway module" discipline as app/services/ai/gateway.py enforces
for LLM providers, just for embeddings instead of completions.

The model runs fully in-process: no external API call, no document text
ever leaves the deployment to reach a third-party embedding service — a
real requirement for banking-internal documentation, not just a
convenience. Loaded lazily (first call, not import time) and cached as a
process-wide singleton, since construction (loading the ONNX model into
memory) takes roughly a second and shouldn't repeat per-request.

Milestone 5: embeddings themselves are also cached — reusing
app/services/ai/cache.py's Redis exact-match cache rather than a parallel
module (identical shape: hash a payload, get/set with a TTL, fail open on
Redis errors). A given (model, text) pair's embedding never changes, so
this doubles as the "incremental indexing" mechanism for document
versioning (document_manager.py): re-uploading a lightly-edited document
produces mostly-identical chunk text, so most of its chunks are cache
hits rather than fresh model inference.
"""

import time

import structlog

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.metrics import record_cache_result
from app.services.ai import cache as response_cache

logger = structlog.get_logger(__name__)
settings = get_settings()

# BAAI/bge-small-en-v1.5 (and the bge family generally) is trained
# asymmetrically: prefixing a *query* with this instruction measurably
# improves retrieval quality, while passages/chunks are embedded as-is
# with no prefix. This is the model's own documented usage convention,
# not a NOVA-specific invention — changing the configured embedding
# model may mean this prefix no longer applies and should be revisited.
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days — a (model, text) embedding never changes

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding

            start = time.monotonic()
            _model = TextEmbedding(
                model_name=settings.knowledge_embedding_model,
                cache_dir=settings.knowledge_embedding_cache_dir,
            )
            logger.info(
                "embedding_manager.model_loaded",
                model=settings.knowledge_embedding_model,
                load_time_ms=round((time.monotonic() - start) * 1000, 1),
            )
        except Exception as exc:
            logger.error("embedding_manager.model_load_failed", error=str(exc))
            raise ServiceUnavailableError(
                f"Embedding model '{settings.knowledge_embedding_model}' failed to load: {exc}"
            ) from exc
    return _model


def _cache_payload(kind: str, text: str) -> dict:
    return {"model": settings.knowledge_embedding_model, "kind": kind, "text": text}


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for storage — no query instruction prefix."""
    if not texts:
        return []

    vectors: list[list[float] | None] = [None] * len(texts)
    to_compute: list[int] = []
    for index, text in enumerate(texts):
        cached = response_cache.get_cached("embed_passage", _cache_payload("passage", text))
        if cached is not None:
            vectors[index] = cached["vector"]
            record_cache_result("embedding", hit=True)
        else:
            to_compute.append(index)
            record_cache_result("embedding", hit=False)

    if to_compute:
        model = _get_model()
        start = time.monotonic()
        computed = [vector.tolist() for vector in model.embed([texts[i] for i in to_compute])]
        logger.debug(
            "embedding_manager.embed_passages",
            count=len(to_compute),
            cache_hits=len(texts) - len(to_compute),
            duration_ms=round((time.monotonic() - start) * 1000, 1),
        )
        for index, vector in zip(to_compute, computed):
            vectors[index] = vector
            response_cache.set_cached(
                "embed_passage", _cache_payload("passage", texts[index]), {"vector": vector}, ttl_seconds=_CACHE_TTL_SECONDS
            )

    return vectors  # type: ignore[return-value]  # every slot is filled by either branch above


def embed_query(text: str) -> list[float]:
    """Embed a search query — includes bge's asymmetric instruction prefix."""
    cache_payload = _cache_payload("query", text)
    cached = response_cache.get_cached("embed_query", cache_payload)
    if cached is not None:
        record_cache_result("embedding", hit=True)
        return cached["vector"]
    record_cache_result("embedding", hit=False)

    model = _get_model()
    start = time.monotonic()
    vector = next(iter(model.embed([_BGE_QUERY_INSTRUCTION + text]))).tolist()
    logger.debug(
        "embedding_manager.embed_query",
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    response_cache.set_cached("embed_query", cache_payload, {"vector": vector}, ttl_seconds=_CACHE_TTL_SECONDS)
    return vector


def embedding_dimensions() -> int:
    return settings.knowledge_embedding_dim


def is_ready() -> bool:
    """Used by /health/ready (Milestone 5) — the model is a lazy
    singleton (see _get_model), so this is a cheap no-op after the first
    successful call, not a repeated model load on every readiness probe."""
    try:
        _get_model()
        return True
    except ServiceUnavailableError:
        return False
