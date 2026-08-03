"""
NOVA — Redis-backed Rate Limiting
Two layers, deliberately different shapes:

  1. `RateLimitMiddleware` — a flat, global, per-IP fixed-window limiter
     applied to every route (see main.py). A coarse backstop, not tuned
     for any specific endpoint's cost.
  2. `require_rate_limit(...)` (Milestone 5) — a FastAPI dependency
     applied per-route to the AI-cost-bearing RAG endpoints (knowledge
     search, assistant chat, finding intelligence, executive ask), keyed
     by USER not IP. IP-keying would either let every user behind one
     NAT/office IP share (and starve each other of) one budget, or — if
     loosened to compensate — fail to actually bound any single user's
     LLM-cost exposure, which is the whole point of this layer existing
     alongside the coarse one above.

Both share the same Redis fixed-window counter pattern and fail-open
behavior (a Redis outage degrades to "no limiting", never to a hard
error, since availability of the platform matters more than the limiter
itself).
"""

import time
from typing import Annotated, Callable

import redis.asyncio as redis
import structlog
from fastapi import Depends
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.dependencies import get_current_active_user
from app.config import get_settings
from app.core.exceptions import AppError
from app.models.user import User

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, requests_per_window: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        settings = get_settings()
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // self.window_seconds)
        key = f"NOVA:ratelimit:{client_ip}:{window}"

        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, self.window_seconds)
        except Exception:
            logger.warning("rate_limit.redis_unavailable_failing_open")
            return await call_next(request)

        if count > self.requests_per_window:
            logger.warning("rate_limit.exceeded", client_ip=client_ip, count=count)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
            )

        return await call_next(request)


_user_rate_limit_redis: "redis.Redis | None" = None


def _get_redis() -> redis.Redis:
    global _user_rate_limit_redis
    if _user_rate_limit_redis is None:
        _user_rate_limit_redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _user_rate_limit_redis


def require_rate_limit(scope: str, *, limit: int, window_seconds: int) -> Callable[..., User]:
    """
    Returns a dependency that fixed-window rate-limits the current user
    for the given `scope` (a short label identifying which budget this
    is — e.g. "assistant_chat" — so different AI endpoints can have
    independent budgets rather than sharing one counter). Use like:

        Depends(require_rate_limit("assistant_chat", limit=20, window_seconds=60))

    Fails open on Redis errors, same as RateLimitMiddleware.
    """

    async def _dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        window = int(time.time() // window_seconds)
        key = f"NOVA:ratelimit:user:{scope}:{current_user.id}:{window}"

        try:
            r = _get_redis()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window_seconds)
        except Exception:
            logger.warning("rate_limit.user_redis_unavailable_failing_open", scope=scope)
            return current_user

        if count > limit:
            logger.warning(
                "rate_limit.user_exceeded", scope=scope, user_id=str(current_user.id), count=count, limit=limit
            )
            raise AppError(
                f"Rate limit exceeded for '{scope}' — try again in under {window_seconds} seconds.",
                code="rate_limited",
                status_code=429,
            )
        return current_user

    return _dependency
