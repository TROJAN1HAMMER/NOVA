"""
NOVA — HTTP Metrics Middleware
Records the in-process HTTP metrics defined in app/core/metrics.py. See
that module's docstring for why these are recorded here (in-process,
per-pod) rather than tunneled through Redis/Postgres like the business
and scanner metrics are.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # /metrics itself is excluded — a scrape shouldn't inflate its own
        # request count/duration series every time it's scraped.
        if request.url.path == "/metrics":
            return await call_next(request)

        # The raw path (with real IDs in it, e.g. /api/v1/scan/<uuid>)
        # would blow up cardinality — one time series per unique UUID ever
        # requested, forever. `request.scope["route"].path` is the
        # *matched route template* (e.g. /api/v1/scan/{scan_job_id}),
        # available only after routing — hence reading it from the
        # response side, not before `call_next`.
        HTTP_REQUESTS_IN_PROGRESS.inc()
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            HTTP_REQUESTS_IN_PROGRESS.dec()

        duration = time.monotonic() - start
        route = request.scope.get("route")
        path_template = route.path if route is not None else request.url.path

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method, path=path_template, status=str(response.status_code)
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path_template).observe(duration)

        return response
