"""
NOVA — RBAC Permissions & Role Alignment Unit Tests
Validates the canonical 5-role UserRole enum, role-to-permission mapping,
display names, computed schema properties, permission dependency enforcement,
and Admin role update validation.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.auth.admin_router import update_user_role
from app.auth.permissions import (
    _ALL_PERMISSIONS,
    _AUDITOR_PERMISSIONS,
    _DEVELOPER_PERMISSIONS,
    _READ_ONLY_PERMISSIONS,
    _SECURITY_ENGINEER_PERMISSIONS,
    Permission,
    ROLE_DISPLAY_NAMES,
    ROLE_PERMISSIONS,
    has_permission,
    require_permission,
)
from app.auth.schemas import (
    AdminUserCreateRequest,
    RoleUpdateRequest,
    UserRead,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import AuthProvider, UserRole
from app.models.user import User


# ── 1. Canonical Enum & Vocabulary Tests ──────────────────────────────────────


class TestUserRoleEnum:
    def test_canonical_roles_defined(self):
        expected_roles = {
            "admin",
            "security_engineer",
            "developer",
            "auditor",
            "read_only",
        }
        actual_roles = {r.value for r in UserRole}
        assert actual_roles == expected_roles

    def test_no_legacy_roles_in_enum(self):
        # "analyst" and "contributor" were retired in migration 0006
        assert "analyst" not in UserRole._value2member_map_
        assert "contributor" not in UserRole._value2member_map_


# ── 2. Role Permissions Matrix Tests ──────────────────────────────────────────


class TestRolePermissionsMatrix:
    def test_every_role_has_permissions_defined(self):
        for role in UserRole:
            assert role in ROLE_PERMISSIONS
            assert isinstance(ROLE_PERMISSIONS[role], frozenset)

    def test_admin_has_all_permissions(self):
        assert ROLE_PERMISSIONS[UserRole.ADMIN] == _ALL_PERMISSIONS
        assert Permission.USER_MANAGE in ROLE_PERMISSIONS[UserRole.ADMIN]
        assert Permission.ADMIN_WRITE in ROLE_PERMISSIONS[UserRole.ADMIN]

    def test_security_engineer_permissions(self):
        perms = ROLE_PERMISSIONS[UserRole.SECURITY_ENGINEER]
        assert perms == _SECURITY_ENGINEER_PERMISSIONS
        assert Permission.PROMPT_TUNING_WRITE in perms
        assert Permission.AUDIT_LOG_READ in perms
        assert Permission.TEAM_ANALYTICS_READ in perms
        assert Permission.KNOWLEDGE_WRITE in perms
        assert Permission.FAQ_WRITE in perms
        assert Permission.REPORT_READ in perms
        assert Permission.USER_MANAGE not in perms
        assert Permission.ADMIN_WRITE not in perms

    def test_developer_permissions(self):
        perms = ROLE_PERMISSIONS[UserRole.DEVELOPER]
        assert perms == _DEVELOPER_PERMISSIONS
        assert Permission.KNOWLEDGE_WRITE in perms
        assert Permission.FAQ_WRITE in perms
        assert Permission.KNOWLEDGE_READ in perms
        assert Permission.REPORT_READ in perms
        assert Permission.AUDIT_LOG_READ not in perms
        assert Permission.TEAM_ANALYTICS_READ not in perms
        assert Permission.USER_MANAGE not in perms

    def test_auditor_permissions(self):
        perms = ROLE_PERMISSIONS[UserRole.AUDITOR]
        assert perms == _AUDITOR_PERMISSIONS
        assert Permission.AUDIT_LOG_READ in perms
        assert Permission.TEAM_ANALYTICS_READ in perms
        assert Permission.REPORT_READ in perms
        assert Permission.KNOWLEDGE_READ in perms
        # Auditors must NOT have write mutations
        assert Permission.KNOWLEDGE_WRITE not in perms
        assert Permission.FAQ_WRITE not in perms
        assert Permission.PROMPT_TUNING_WRITE not in perms
        assert Permission.USER_MANAGE not in perms
        assert Permission.ADMIN_WRITE not in perms

    def test_read_only_permissions(self):
        perms = ROLE_PERMISSIONS[UserRole.READ_ONLY]
        assert perms == _READ_ONLY_PERMISSIONS
        assert Permission.REPORT_READ in perms
        assert Permission.REPORT_DOWNLOAD in perms
        assert Permission.KNOWLEDGE_READ in perms
        assert Permission.AUDIT_LOG_READ not in perms
        assert Permission.TEAM_ANALYTICS_READ not in perms
        assert Permission.KNOWLEDGE_WRITE not in perms


# ── 3. Role Display Names Tests ───────────────────────────────────────────────


class TestRoleDisplayNames:
    def test_all_roles_have_display_names(self):
        for role in UserRole:
            assert role in ROLE_DISPLAY_NAMES
            assert len(ROLE_DISPLAY_NAMES[role]) > 0

    def test_expected_display_names(self):
        assert ROLE_DISPLAY_NAMES[UserRole.ADMIN] == "Platform Administrator"
        assert ROLE_DISPLAY_NAMES[UserRole.SECURITY_ENGINEER] == "AI Systems Engineer"
        assert ROLE_DISPLAY_NAMES[UserRole.DEVELOPER] == "Knowledge Analyst"
        assert ROLE_DISPLAY_NAMES[UserRole.AUDITOR] == "Executive / Auditor"
        assert ROLE_DISPLAY_NAMES[UserRole.READ_ONLY] == "Read Only"


# ── 4. Permission Helpers & Dependency Enforcement ────────────────────────────


class TestPermissionHelpers:
    def test_has_permission(self):
        assert has_permission(UserRole.ADMIN, Permission.USER_MANAGE) is True
        assert has_permission(UserRole.DEVELOPER, Permission.USER_MANAGE) is False
        assert has_permission(UserRole.DEVELOPER, Permission.KNOWLEDGE_WRITE) is True
        assert has_permission(UserRole.AUDITOR, Permission.KNOWLEDGE_WRITE) is False
        assert has_permission(UserRole.AUDITOR, Permission.AUDIT_LOG_READ) is True

    @pytest.mark.asyncio
    async def test_require_permission_allows_authorized_user(self):
        user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        dependency = require_permission(Permission.USER_MANAGE)
        result = await dependency(current_user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_require_permission_denies_unauthorized_user_and_logs(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        dependency = require_permission(Permission.USER_MANAGE)

        with patch("app.auth.permissions.log_action", new_callable=AsyncMock) as mock_log:
            with pytest.raises(ForbiddenError) as exc_info:
                await dependency(current_user=user)

            assert "lacks required permission" in str(exc_info.value)
            mock_log.assert_called_once()


# ── 5. Schema Validation & Computed Fields Tests ──────────────────────────────


class TestRoleSchemasAndValidation:
    def test_role_update_request_accepts_all_canonical_roles(self):
        for role_str in ["admin", "security_engineer", "developer", "auditor", "read_only"]:
            req = RoleUpdateRequest(role=role_str)
            assert req.role == UserRole(role_str)

    def test_role_update_request_rejects_invalid_roles(self):
        invalid_roles = ["analyst", "contributor", "superadmin", "manager", "guest", ""]
        for invalid in invalid_roles:
            with pytest.raises(ValidationError):
                RoleUpdateRequest(role=invalid)

    def test_admin_user_create_request_role(self):
        req_default = AdminUserCreateRequest(email="new@nova.example", password="securepassword123")
        assert req_default.role == UserRole.DEVELOPER

        req_custom = AdminUserCreateRequest(
            email="auditor@nova.example",
            password="securepassword123",
            role=UserRole.AUDITOR,
        )
        assert req_custom.role == UserRole.AUDITOR

    def test_user_read_computed_fields_for_all_roles(self):
        for role in UserRole:
            user_data = {
                "id": uuid.uuid4(),
                "email": f"{role.value}@nova.example",
                "full_name": f"{role.name} User",
                "role": role,
                "is_active": True,
                "auth_provider": AuthProvider.LOCAL,
            }
            user_read = UserRead.model_validate(user_data)
            assert user_read.role_display_name == ROLE_DISPLAY_NAMES[role]
            assert user_read.permissions == sorted(p.value for p in ROLE_PERMISSIONS[role])


# ── 6. Admin Role Update Endpoint Tests ───────────────────────────────────────


class TestAdminRoleUpdateEndpoint:
    @pytest.mark.asyncio
    async def test_update_user_role_endpoint_success(self):
        target_user_id = uuid.uuid4()
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        updated_user = User(
            id=target_user_id,
            email="target@nova.example",
            role=UserRole.SECURITY_ENGINEER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_users_repo = AsyncMock()
        mock_users_repo.update_role.return_value = updated_user

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = RoleUpdateRequest(role=UserRole.SECURITY_ENGINEER)

        with patch("app.auth.admin_router.log_action", new_callable=AsyncMock) as mock_log:
            result = await update_user_role(
                user_id=target_user_id,
                payload=payload,
                request=mock_request,
                users=mock_users_repo,
                current_user=admin_user,
            )

            assert result == updated_user
            mock_users_repo.update_role.assert_called_once_with(target_user_id, UserRole.SECURITY_ENGINEER)
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_role_endpoint_not_found(self):
        target_user_id = uuid.uuid4()
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_users_repo = AsyncMock()
        mock_users_repo.update_role.return_value = None

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = RoleUpdateRequest(role=UserRole.AUDITOR)

        with pytest.raises(NotFoundError):
            await update_user_role(
                user_id=target_user_id,
                payload=payload,
                request=mock_request,
                users=mock_users_repo,
                current_user=admin_user,
            )
