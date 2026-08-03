"""
NOVA — Global Exception Handlers
Registers handlers on the FastAPI app so that:

  1. `AppError` subclasses (raised by future repositories/services) map to
     the correct HTTP status with a response shape compatible with the
     existing `{"detail": ...}` contract the frontend already parses.
  2. Any *unhandled* exception is caught, logged with full context, and
     turned into a generic 500 — never leaking a stack trace to the client.

Existing routes that raise `fastapi.HTTPException` directly are untouched:
FastAPI's default handler for it is left in place, so current API responses
do not change shape.

Both handlers manually attach CORS headers to their response. This isn't
optional decoration: exception handlers registered via
`@app.exception_handler(...)` run through Starlette's `ServerErrorMiddleware`,
which wraps *outside* every user-added middleware — including
`CORSMiddleware` (see app/main.py). A response built here never passes back
through CORSMiddleware, so without this, any error response to a
cross-origin browser request arrives with no `Access-Control-Allow-Origin`
header, which the browser then blocks outright — surfacing to the frontend
as an opaque network failure ("could not reach the API") instead of the
actual error body, no matter how informative `detail` is.
"""

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)
settings = get_settings()


def _add_cors_headers(response: JSONResponse, request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin in settings.allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "request.app_error",
            path=request.url.path,
            code=exc.code,
            message=exc.message,
        )
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code, "details": exc.details},
        )
        _add_cors_headers(response, request)
        return response

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "request.unhandled_exception",
            path=request.url.path,
            error=str(exc),
        )
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
        _add_cors_headers(response, request)
        return response
