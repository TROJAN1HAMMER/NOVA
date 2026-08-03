"""
NOVA — RBAC Permission Middleware

A coarse, cheap, role-only gate that runs before any route's own
dependencies — defense in depth alongside `app/auth/permissions.py`'s
fine-grained, per-route `require_permission(...)` dependency, not a
replacement for it.

What it checks: the JWT access token's embedded `role` claim (no DB
round-trip on the common/allowed path — see `security.py`'s
`create_access_token` docstring for why that's safe for a coarse check)
against one blanket rule — READ_ONLY and AUDITOR can never perform a
mutating HTTP method (POST/PUT/PATCH/DELETE) anywhere in the API, except
the narrow, explicit `READ_ONLY_QUERY_PATH_PREFIXES` allowlist below for
POST-shaped read/search endpoints. This catches "a developer forgot to
add `require_permission` to a new mutating route" for free, for exactly
those two strictly-read-only roles, without every route needing to
remember to protect itself.

It deliberately does NOT enforce anything more specific than that (e.g.
"a Developer can't write risk_config") — that's what the resource-
specific `require_permission(...)` dependencies are for. Duplicating that
logic here would need per-route path matching and would just be a second
source of truth to keep in sync with `ROLE_PERMISSIONS`. Since this
middleware only ever narrows what's already true for the two strictly-
read-only roles, it can never contradict a route's own dependency-based
check.

Fails open on any decode error (missing/expired/malformed token, no token
at all) — this is NOT the authentication layer. A request with no valid
token just proceeds to whatever the route's own `get_current_active_user`
dependency decides (typically a 401). This middleware only ever adds an
extra rejection on top of an already-successfully-authenticated,
already-role-bearing request; it never grants anything a missing/invalid
token wouldn't already block.
"""

import structlog
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.security import decode_token
from app.models.enums import UserRole
from app.services.audit.audit_logger import log_action

logger = structlog.get_logger(__name__)

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
BLOCKED_ROLES_FOR_MUTATION = frozenset({UserRole.READ_ONLY.value, UserRole.AUDITOR.value})

# Auth bootstrapping itself must stay reachable regardless of the blanket
# rule above — a read-only user still needs to be able to log in, refresh
# an expiring token, or complete an SSO callback.
EXEMPT_PATH_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/register",
    "/api/v1/auth/sso/",
    "/api/v1/auth/ldap/login",
)

# Not an auth-bootstrapping exemption like the list above — these are POST
# endpoints where POST only carries a JSON request body (filters/a search
# query too complex for a query string), not a mutation. Blocking them for
# READ_ONLY/AUDITOR would contradict those roles' own fine-grained
# permissions — Auditor is deliberately granted Permission.KNOWLEDGE_READ
# specifically so it CAN search (see app/auth/permissions.py), and the
# HTTP-verb heuristic this middleware otherwise relies on can't tell a
# search from a write. Every path listed here must already be protected by
# its own `require_permission(...)` dependency at the route — this list
# only lifts the coarse verb-based block, it never grants access on its own.
READ_ONLY_QUERY_PATH_PREFIXES = (
    "/api/v1/knowledge/search",
    "/api/v1/assistant/chat",
    "/api/v1/executive-intelligence/",
)


class PermissionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
            return await call_next(request)

        if any(request.url.path.startswith(prefix) for prefix in READ_ONLY_QUERY_PATH_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)  # no/malformed token — the route's own auth dependency handles it

        token = auth_header[len("Bearer "):]
        try:
            payload = decode_token(token)
        except JWTError:
            return await call_next(request)  # invalid/expired — same reasoning

        role = payload.get("role")
        if role in BLOCKED_ROLES_FOR_MUTATION:
            logger.warning(
                "permission_middleware.blocked", role=role, path=request.url.path, method=request.method
            )
            await log_action(
                user_id=_safe_uuid(payload.get("sub")),
                action="permission.denied",
                resource_type="route",
                resource_id=f"{request.method} {request.url.path}",
                status="denied",
                request=request,
                details={"role": role, "reason": "read-only role attempted a mutating request"},
            )
            return JSONResponse(
                status_code=403,
                content={"detail": f"Role '{role}' is read-only and cannot perform {request.method} requests."},
            )

        return await call_next(request)


def _safe_uuid(value):
    import uuid

    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None
