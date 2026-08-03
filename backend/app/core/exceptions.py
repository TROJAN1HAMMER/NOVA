"""
NOVA — Application Exception Hierarchy
Domain/service-layer code raises these instead of `fastapi.HTTPException`.
`app.core.error_handlers` translates them into HTTP responses at the edge,
keeping services and repositories free of any HTTP-layer concerns.
"""

from typing import Any, Optional


class AppError(Exception):
    """Base class for all application-raised errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
