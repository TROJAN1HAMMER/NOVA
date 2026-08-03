"""
AEKOF — RBAC Permissions Matrix

A fixed, code-defined role -> permission matrix for the 5 UserRoles:
ADMIN, SECURITY_ENGINEER (AI_ENGINEER), DEVELOPER, AUDITOR, READ_ONLY.
"""

import enum
from typing import Annotated, Callable

from fastapi import Depends

from app.auth.dependencies import get_current_active_user
from app.core.exceptions import ForbiddenError
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit.audit_logger import log_action


class Permission(str, enum.Enum):
    REPORT_READ = "report:read"
    REPORT_DOWNLOAD = "report:download"
    USER_MANAGE = "user:manage"
    AUDIT_LOG_READ = "audit_log:read"
    TEAM_ANALYTICS_READ = "team_analytics:read"
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    FAQ_WRITE = "faq:write"
    PROMPT_TUNING_WRITE = "prompt_tuning:write"
    ADMIN_WRITE = "admin:write"


_ALL_PERMISSIONS = frozenset(Permission)

_READ_ONLY_PERMISSIONS = frozenset(
    {
        Permission.REPORT_READ,
        Permission.REPORT_DOWNLOAD,
        Permission.KNOWLEDGE_READ,
    }
)

_DEVELOPER_PERMISSIONS = _READ_ONLY_PERMISSIONS | frozenset(
    {
        Permission.KNOWLEDGE_WRITE,
        Permission.FAQ_WRITE,
    }
)

_SECURITY_ENGINEER_PERMISSIONS = _DEVELOPER_PERMISSIONS | frozenset(
    {
        Permission.PROMPT_TUNING_WRITE,
        Permission.AUDIT_LOG_READ,
        Permission.TEAM_ANALYTICS_READ,
    }
)

_AUDITOR_PERMISSIONS = _READ_ONLY_PERMISSIONS | frozenset(
    {
        Permission.AUDIT_LOG_READ,
        Permission.TEAM_ANALYTICS_READ,
    }
)

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.ADMIN: _ALL_PERMISSIONS,
    UserRole.SECURITY_ENGINEER: _SECURITY_ENGINEER_PERMISSIONS,
    UserRole.DEVELOPER: _DEVELOPER_PERMISSIONS,
    UserRole.AUDITOR: _AUDITOR_PERMISSIONS,
    UserRole.READ_ONLY: _READ_ONLY_PERMISSIONS,
}

ROLE_DISPLAY_NAMES: dict[UserRole, str] = {
    UserRole.ADMIN: "Platform Administrator",
    UserRole.SECURITY_ENGINEER: "AI Systems Engineer",
    UserRole.DEVELOPER: "Knowledge Analyst",
    UserRole.AUDITOR: "Executive / Auditor",
    UserRole.READ_ONLY: "Read Only",
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(*permissions: Permission) -> Callable[..., User]:
    async def _dependency(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        missing = [p for p in permissions if not has_permission(current_user.role, p)]
        if missing:
            await log_action(
                user=current_user,
                action="permission.denied",
                resource_type="permission",
                resource_id=",".join(p.value for p in missing),
                status="denied",
            )
            raise ForbiddenError(
                f"Role '{current_user.role.value}' lacks required permission(s): "
                f"{', '.join(p.value for p in missing)}"
            )
        return current_user

    return _dependency
