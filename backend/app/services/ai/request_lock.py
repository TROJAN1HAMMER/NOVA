"""
NOVA — Duplicate Request Detection

Celery runs the 9 scanners in parallel and, on a large scan, many findings
that share a semantic cache key can reach the aggregation/AI step at
close to the same time — before the first one has finished its provider
call and populated the cache. Without this, every one of them would fire
its own identical provider request.

This is a short-lived Redis `SET NX` claim, not a distributed mutex: at
most one caller "wins" the claim for a given key; everyone else polls the
target cache for a bounded number of short intervals and reuses whatever
the winner produces. If the winner is slow or crashes before writing a
result, losers give up waiting and proceed with their own call — never
blocking indefinitely on another worker's success.
"""

import time
from typing import Callable, Optional

import redis
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_redis_client: Optional[redis.Redis] = None

LOCK_TTL_SECONDS = 15
DEFAULT_POLL_ATTEMPTS = 5
DEFAULT_POLL_INTERVAL_SECONDS = 0.2


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _lock_key(key: str) -> str:
    return f"NOVA:ai:inflight:{key}"


def try_acquire(key: str, *, ttl_seconds: int = LOCK_TTL_SECONDS) -> bool:
    """True if this caller won the claim and should perform the actual provider call."""
    try:
        return bool(_get_redis().set(_lock_key(key), "1", nx=True, ex=ttl_seconds))
    except redis.RedisError as exc:
        logger.warning("ai_request_lock.acquire_failed", error=str(exc))
        # Fail open: treat as "we own it" rather than blocking a request
        # entirely because Redis is unavailable.
        return True


def release(key: str) -> None:
    try:
        _get_redis().delete(_lock_key(key))
    except redis.RedisError as exc:
        logger.warning("ai_request_lock.release_failed", error=str(exc))


def wait_for_result(
    getter: Callable[[], Optional[dict]],
    *,
    attempts: int = DEFAULT_POLL_ATTEMPTS,
    interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> Optional[dict]:
    """
    Called by a caller that lost the claim: polls `getter` (a cache lookup)
    a bounded number of times for the winner's result. Returns None (never
    raises) if the winner hasn't produced a result within the poll window —
    the caller is expected to fall back to proceeding independently.
    """
    for _ in range(attempts):
        result = getter()
        if result is not None:
            return result
        time.sleep(interval_seconds)
    return None
