"""
NOVA — Rerank Manager
Wraps a local ONNX cross-encoder (fastembed's `TextCrossEncoder`) so
nothing outside this module imports it directly — same "one gateway
module" discipline as app/services/knowledge_base/embedding_manager.py.

This is a second-stage precision pass over the first-stage vector-search
candidates: cosine similarity (bi-encoder) is fast but coarser, and a
cross-encoder scores the (query, chunk) pair jointly, which is slower but
meaningfully better at telling "actually answers this question" apart
from "merely mentions similar words." Runs fully in-process — no external
API call, consistent with the embedding model's reasoning.

Milestone 5: per-pair scores are cached (query, passage, model) — reusing
app/services/ai/cache.py's existing Redis exact-match cache rather than a
parallel cache module, since the shape (hash a JSON payload, get/set with
a TTL, fail open on Redis errors) is identical. A (query, passage) pair's
score is stable regardless of what else is in the knowledge base, so
there's no staleness risk the way there would be for cached search
*results* (which depend on the KB's current contents).
"""

import math
import time
from typing import Optional

import structlog

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.core.metrics import record_cache_result
from app.services.ai import cache as response_cache

logger = structlog.get_logger(__name__)
settings = get_settings()

_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days — a (query, passage) score never changes for a fixed model

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            start = time.monotonic()
            _model = TextCrossEncoder(
                model_name=settings.assistant_rerank_model,
                cache_dir=settings.assistant_rerank_cache_dir,
            )
            logger.info(
                "rerank_manager.model_loaded",
                model=settings.assistant_rerank_model,
                load_time_ms=round((time.monotonic() - start) * 1000, 1),
            )
        except Exception as exc:
            logger.error("rerank_manager.model_load_failed", error=str(exc))
            raise ServiceUnavailableError(
                f"Reranking model '{settings.assistant_rerank_model}' failed to load: {exc}"
            ) from exc
    return _model


def is_ready() -> bool:
    """Used by /health/ready (Milestone 5) — cheap after the first
    successful call, same reasoning as embedding_manager.is_ready()."""
    try:
        _get_model()
        return True
    except ServiceUnavailableError:
        return False


def _cache_payload(query: str, document: str) -> dict:
    return {"model": settings.assistant_rerank_model, "query": query, "document": document}


def rerank(query: str, documents: list[str]) -> list[float]:
    """
    Raw cross-encoder scores, one per document, in the same order as
    `documents` (NOT sorted — the caller sorts, since it also needs to
    keep each score paired with its originating chunk).

    Also doubles as Milestone 5's "incremental indexing" mechanism where
    it matters most in practice: re-uploading a lightly-edited document
    (see document_manager.py's version chains) produces mostly-identical
    chunk text, so most rerank calls for it are cache hits rather than
    fresh model inference.
    """
    if not documents:
        return []

    scores: list[Optional[float]] = [None] * len(documents)
    to_compute: list[int] = []
    for index, document in enumerate(documents):
        cached = response_cache.get_cached("rerank_pair", _cache_payload(query, document))
        if cached is not None:
            scores[index] = cached["score"]
            record_cache_result("rerank", hit=True)
        else:
            to_compute.append(index)
            record_cache_result("rerank", hit=False)

    if to_compute:
        model = _get_model()
        start = time.monotonic()
        computed = [float(score) for score in model.rerank(query, [documents[i] for i in to_compute])]
        logger.debug(
            "rerank_manager.rerank",
            count=len(to_compute),
            cache_hits=len(documents) - len(to_compute),
            duration_ms=round((time.monotonic() - start) * 1000, 1),
        )
        for index, score in zip(to_compute, computed):
            scores[index] = score
            response_cache.set_cached(
                "rerank_pair", _cache_payload(query, documents[index]), {"score": score}, ttl_seconds=_CACHE_TTL_SECONDS
            )

    return scores  # type: ignore[return-value]  # every slot is filled by either branch above


def normalize_confidence(raw_score: Optional[float]) -> float:
    """
    Cross-encoder scores are unbounded real-valued logits, not
    probabilities — this squashes the top match's score through a sigmoid
    to get a 0..1 "confidence" NOVA's assistant gate and UI can compare
    against a fixed threshold. This is a measure of how relevant the
    best-matching retrieved excerpt is to the question, NOT a probability
    that the eventual generated answer is factually correct — the same
    "don't overclaim what the number means" discipline this codebase
    already applies to the BRS/Attack Surface Exposure scores.
    """
    if raw_score is None:
        return 0.0
    return round(1.0 / (1.0 + math.exp(-raw_score)), 4)
