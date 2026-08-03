"""
NOVA — Request Context Middleware
Stamps every request with a correlation ID, binds it into structlog's
contextvars (so every log line emitted while handling the request carries
it automatically), and logs a single start/complete pair with timing.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("request.failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("request.completed", status_code=response.status_code, duration_ms=duration_ms)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
