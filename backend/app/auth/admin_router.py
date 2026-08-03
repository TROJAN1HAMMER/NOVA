"""
NOVA — Admin Routes
User management (role assignment, activation) gated by
`Permission.USER_MANAGE` (Admin only, per `ROLE_PERMISSIONS`), and audit
log querying gated by `Permission.AUDIT_LOG_READ` (Admin, Security
Engineer, Auditor).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from starlette.requests import Request

from app.auth.permissions import Permission, require_permission
from app.auth.schemas import (
    ActiveStatusUpdateRequest,
    AdminUserCreateRequest,
    AuditLogListResponse,
    RoleUpdateRequest,
    UserRead,
)
from app.auth.service import AuthService
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.deps import get_audit_log_repository, get_user_repository
from app.repositories.user_repository import UserRepository
from app.services.audit.audit_logger import log_action

router = APIRouter()
settings = get_settings()


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(users)


@router.get("/auth/admin/users", response_model=list[UserRead])
async def list_users(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    _current_user: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await users.list_all(limit=limit, offset=offset)


@router.post("/auth/admin/users", response_model=UserRead, status_code=201)
async def create_user_as_admin(
    payload: AdminUserCreateRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
):
    user = await auth_service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        request=request,
    )
    if payload.role != user.role:
        user = await users.update_role(user.id, payload.role)
    await log_action(
        user=current_user,
        action="user.created_by_admin",
        resource_type="user",
        resource_id=str(user.id),
        request=request,
        details={"assigned_role": payload.role.value, "email": payload.email},
    )
    return user


@router.patch("/auth/admin/users/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdateRequest,
    request: Request,
    users: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
):
    user = await users.update_role(user_id, payload.role)
    if user is None:
        raise NotFoundError("User not found")
    await log_action(
        user=current_user,
        action="user.role_changed",
        resource_type="user",
        resource_id=str(user_id),
        request=request,
        details={"new_role": payload.role.value},
    )
    return user


@router.patch("/auth/admin/users/{user_id}/active", response_model=UserRead)
async def update_user_active_status(
    user_id: uuid.UUID,
    payload: ActiveStatusUpdateRequest,
    request: Request,
    users: Annotated[UserRepository, Depends(get_user_repository)],
    current_user: Annotated[User, Depends(require_permission(Permission.USER_MANAGE))],
):
    user = await users.set_active(user_id, payload.is_active)
    if user is None:
        raise NotFoundError("User not found")
    await log_action(
        user=current_user,
        action="user.activated" if payload.is_active else "user.deactivated",
        resource_type="user",
        resource_id=str(user_id),
        request=request,
    )
    return user


@router.get("/auth/audit-log", response_model=AuditLogListResponse)
async def query_audit_log(
    audit_logs: Annotated[AuditLogRepository, Depends(get_audit_log_repository)],
    _current_user: Annotated[User, Depends(require_permission(Permission.AUDIT_LOG_READ))],
    user_id: Optional[uuid.UUID] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    Defaults to the last `audit_log_default_lookback_days` days (90 by
    default) when `since` isn't given, so a careless unbounded query can't
    accidentally full-scan the entire table.
    """
    effective_since = since or (
        datetime.now(timezone.utc) - timedelta(days=settings.audit_log_default_lookback_days)
    )
    entries = await audit_logs.list(
        user_id=user_id, action=action, status=status, since=effective_since, limit=limit, offset=offset
    )
    total = await audit_logs.count(user_id=user_id, action=action, status=status, since=effective_since)
    return AuditLogListResponse(total=total, limit=limit, offset=offset, entries=entries)
