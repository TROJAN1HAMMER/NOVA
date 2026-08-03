"""
NOVA — Audit Logger

The curated set of events this platform actually audits, and why it's a
curated set rather than every request:
  - Auth events (login success/failure, register, token refresh) — who
    authenticated, when, and whether it succeeded. Logged from
    `app/auth/service.py` and the SSO callback routes.
  - RBAC permission denials — every 403 `app/auth/permissions.py`'s
    `require_permission` produces, for free, on every protected route,
    with zero per-route code changes.
  - Admin actions (role changes, activation/deactivation) — logged
    explicitly at their own call sites in the admin routes.

Logging every GET request would bury the events that actually matter to
an auditor in noise without adding security value — request-level access
logging already exists via `RequestContextMiddleware`'s structured logs;
this is specifically the *security-relevant* subset.

Uses its own short-lived DB session (the same pattern `report_tasks.py`
uses) rather than piggybacking on the calling route's session/transaction:
an audit record — especially a permission-denied one — should be durably
written regardless of what happens to the request's own transaction
afterward, including if that transaction itself fails or rolls back.
"""

import uuid
from typing import Optional

import structlog
from starlette.requests import Request

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository

logger = structlog.get_logger(__name__)


async def log_action(
    *,
    user: Optional[User] = None,
    user_id: Optional[uuid.UUID] = None,
    user_email: Optional[str] = None,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: str = "success",
    request: Optional[Request] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Never raises — fails open like the rest of this codebase's
    infrastructure dependencies (Redis cache, rate limiter): a broken
    audit-log database should degrade to "this event wasn't recorded",
    logged as a warning, not "logins/permission checks stop working".

    Accepts either a hydrated `user` (the common case — most call sites
    already have one from `get_current_active_user`) or a bare
    `user_id`/`user_email` pair for callers that only have a JWT payload
    and don't want to pay for a DB fetch just to build a `User` object
    (see `PermissionMiddleware`, which resolves role from the token
    directly without loading the user).
    """
    try:
        async with AsyncSessionLocal() as db:
            repo = AuditLogRepository(db)
            await repo.create(
                user_id=user.id if user else user_id,
                user_email=user.email if user else user_email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status=status,
                ip_address=request.client.host if request and request.client else None,
                user_agent=request.headers.get("user-agent") if request else None,
                details=details,
            )
            await db.commit()
    except Exception as exc:
        logger.warning("audit_logger.write_failed", action=action, error=str(exc))
