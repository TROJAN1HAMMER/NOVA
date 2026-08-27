"""
NOVA — Auth Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, computed_field

from app.models.enums import AuthProvider, UserRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None
    role: UserRole = UserRole.DEVELOPER


class UserRead(BaseModel):
    id: uuid.UUID
    email: str  # str (not EmailStr) so internal/demo emails with .local TLD don't crash response serialisation
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    auth_provider: AuthProvider

    model_config = {"from_attributes": True}

    # Computed, not stored: the frontend gets both the raw role (for
    # anything backend-specific, e.g. PATCH .../role) and the resolved
    # display name + permission set for this exact role, so route
    # guarding/nav filtering/permission-aware UI reads one source of truth
    # (app/auth/permissions.py's ROLE_PERMISSIONS) instead of duplicating
    # the matrix in TypeScript where it could drift out of sync.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def role_display_name(self) -> str:
        from app.auth.permissions import ROLE_DISPLAY_NAMES

        return ROLE_DISPLAY_NAMES.get(self.role, self.role.value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def permissions(self) -> list[str]:
        from app.auth.permissions import ROLE_PERMISSIONS

        return sorted(p.value for p in ROLE_PERMISSIONS.get(self.role, frozenset()))


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LDAPLoginRequest(BaseModel):
    username: str
    password: str


class RoleUpdateRequest(BaseModel):
    role: UserRole


class ActiveStatusUpdateRequest(BaseModel):
    is_active: bool


class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    entries: list[AuditLogEntryResponse]
