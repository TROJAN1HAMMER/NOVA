"""
NOVA — Redis Semantic Cache

Sits above the exact-match prompt cache (`cache.py`) with a coarser key:
a canonical signature of (function_name, category, severity, cve/package)
via `SanitizedFinding.semantic_tokens()` — not the literal rendered prompt.

Why this matters: a scan commonly finds the same vulnerability class in
many files (e.g. the same hardcoded-secret pattern in 5 config files).
Those produce 5 different exact prompts (different file extensions, CVSS
rounding, etc.) but are the same *kind* of finding — the sanitizer already
strips out the only things that would differentiate them for explanation
purposes. Keying on the semantic signature instead of the exact prompt
means all 5 reuse one provider response instead of paying for 5 near-
identical calls.

No embeddings/ML involved — "semantic" here means "matches on meaning-
bearing fields after the sanitizer has already discarded everything
incidental", which is deterministic and requires no model.

Fails open on Redis errors, same as `cache.py`.
"""

import hashlib
import json
from typing import Optional

import redis
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def semantic_key(function_name: str, semantic_tokens: tuple[str, ...]) -> str:
    digest = hashlib.sha256("|".join((function_name, *semantic_tokens)).encode()).hexdigest()
    return f"NOVA:ai:semantic:{function_name}:{digest}"


def get_cached(key: str) -> Optional[dict]:
    try:
        raw = _get_redis().get(key)
    except redis.RedisError as exc:
        logger.warning("ai_semantic_cache.get_failed", error=str(exc))
        return None
    return json.loads(raw) if raw else None


def set_cached(key: str, value: dict, *, ttl_seconds: int) -> None:
    try:
        _get_redis().set(key, json.dumps(value), ex=ttl_seconds)
    except redis.RedisError as exc:
        logger.warning("ai_semantic_cache.set_failed", error=str(exc))
