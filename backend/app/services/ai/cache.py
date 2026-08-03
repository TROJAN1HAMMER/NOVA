"""
NOVA — LLM Response Cache

Redis-backed so a repeated (category, severity, title) combination — very
common across a scan with many similar findings — costs one provider call
instead of one per finding, and the cache is shared across every Celery
worker process rather than living per-process.

Fails open: a Redis outage degrades to "no caching", never to a hard error,
matching this codebase's existing rate-limiter convention.
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


def _key(function_name: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"NOVA:ai:cache:{function_name}:{digest}"


def get_cached(function_name: str, payload: dict) -> Optional[dict]:
    try:
        raw = _get_redis().get(_key(function_name, payload))
    except redis.RedisError as exc:
        logger.warning("ai_cache.get_failed", error=str(exc))
        return None
    return json.loads(raw) if raw else None


def set_cached(function_name: str, payload: dict, value: dict, *, ttl_seconds: int) -> None:
    try:
        _get_redis().set(_key(function_name, payload), json.dumps(value), ex=ttl_seconds)
    except redis.RedisError as exc:
        logger.warning("ai_cache.set_failed", error=str(exc))
