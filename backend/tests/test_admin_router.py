"""
NOVA — Admin Router & User Management Unit Tests
Validates admin user listing, creation, role override, activation/deactivation,
audit log querying with default lookback, and strict RBAC permission enforcement.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.admin_router import (
    create_user_as_admin,
    list_users,
    query_audit_log,
    update_user_active_status,
    update_user_role,
)
from app.auth.permissions import Permission, require_permission
from app.auth.schemas import (
    ActiveStatusUpdateRequest,
    AdminUserCreateRequest,
    AuditLogListResponse,
    RoleUpdateRequest,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.audit_log import AuditLog
from app.models.enums import AuthProvider, UserRole
from app.models.user import User


# ── 1. Admin User Management Tests ───────────────────────────────────────────


class TestAdminUserManagement:
    @pytest.mark.asyncio
    async def test_list_users_pagination(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        sample_users = [
            User(
                id=uuid.uuid4(),
                email=f"user{i}@nova.example",
                role=UserRole.DEVELOPER,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            for i in range(5)
        ]

        mock_repo = AsyncMock()
        mock_repo.list_all.return_value = sample_users

        result = await list_users(
            users=mock_repo,
            _current_user=admin_user,
            limit=50,
            offset=10,
        )

        assert len(result) == 5
        mock_repo.list_all.assert_called_once_with(limit=50, offset=10)

    @pytest.mark.asyncio
    async def test_create_user_as_admin_same_role(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        created_user = User(
            id=uuid.uuid4(),
            email="newuser@nova.example",
            role=UserRole.DEVELOPER,
            full_name="New Dev",
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_auth_service = AsyncMock()
        mock_auth_service.register.return_value = created_user

        mock_users_repo = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = AdminUserCreateRequest(
            email="newuser@nova.example",
            password="SecurePassword123!",
            full_name="New Dev",
            role=UserRole.DEVELOPER,
        )

        with patch("app.auth.admin_router.log_action", new_callable=AsyncMock) as mock_log:
            result = await create_user_as_admin(
                payload=payload,
                request=mock_request,
                auth_service=mock_auth_service,
                users=mock_users_repo,
                current_user=admin_user,
            )

            assert result == created_user
            mock_auth_service.register.assert_called_once_with(
                email="newuser@nova.example",
                password="SecurePassword123!",
                full_name="New Dev",
                request=mock_request,
            )
            # Role matched register role, update_role should not be called
            mock_users_repo.update_role.assert_not_called()
            mock_log.assert_called_once_with(
                user=admin_user,
                action="user.created_by_admin",
                resource_type="user",
                resource_id=str(created_user.id),
                request=mock_request,
                details={"assigned_role": "developer", "email": "newuser@nova.example"},
            )

    @pytest.mark.asyncio
    async def test_create_user_as_admin_custom_role_override(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        registered_user = User(
            id=uuid.uuid4(),
            email="engineer@nova.example",
            role=UserRole.DEVELOPER,  # default registration role
            full_name="AI Engineer",
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        updated_role_user = User(
            id=registered_user.id,
            email="engineer@nova.example",
            role=UserRole.SECURITY_ENGINEER,
            full_name="AI Engineer",
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_auth_service = AsyncMock()
        mock_auth_service.register.return_value = registered_user

        mock_users_repo = AsyncMock()
        mock_users_repo.update_role.return_value = updated_role_user

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = AdminUserCreateRequest(
            email="engineer@nova.example",
            password="SecurePassword123!",
            full_name="AI Engineer",
            role=UserRole.SECURITY_ENGINEER,
        )

        with patch("app.auth.admin_router.log_action", new_callable=AsyncMock) as mock_log:
            result = await create_user_as_admin(
                payload=payload,
                request=mock_request,
                auth_service=mock_auth_service,
                users=mock_users_repo,
                current_user=admin_user,
            )

            assert result == updated_role_user
            mock_users_repo.update_role.assert_called_once_with(registered_user.id, UserRole.SECURITY_ENGINEER)
            mock_log.assert_called_once_with(
                user=admin_user,
                action="user.created_by_admin",
                resource_type="user",
                resource_id=str(updated_role_user.id),
                request=mock_request,
                details={"assigned_role": "security_engineer", "email": "engineer@nova.example"},
            )

    @pytest.mark.asyncio
    async def test_update_user_active_status_activate(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        target_user_id = uuid.uuid4()
        activated_user = User(
            id=target_user_id,
            email="user@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_users_repo = AsyncMock()
        mock_users_repo.set_active.return_value = activated_user

        mock_request = MagicMock()
        payload = ActiveStatusUpdateRequest(is_active=True)

        with patch("app.auth.admin_router.log_action", new_callable=AsyncMock) as mock_log:
            result = await update_user_active_status(
                user_id=target_user_id,
                payload=payload,
                request=mock_request,
                users=mock_users_repo,
                current_user=admin_user,
            )

            assert result == activated_user
            mock_users_repo.set_active.assert_called_once_with(target_user_id, True)
            mock_log.assert_called_once_with(
                user=admin_user,
                action="user.activated",
                resource_type="user",
                resource_id=str(target_user_id),
                request=mock_request,
            )

    @pytest.mark.asyncio
    async def test_update_user_active_status_deactivate(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        target_user_id = uuid.uuid4()
        deactivated_user = User(
            id=target_user_id,
            email="user@nova.example",
            role=UserRole.DEVELOPER,
            is_active=False,
            auth_provider=AuthProvider.LOCAL,
        )

        mock_users_repo = AsyncMock()
        mock_users_repo.set_active.return_value = deactivated_user

        mock_request = MagicMock()
        payload = ActiveStatusUpdateRequest(is_active=False)

        with patch("app.auth.admin_router.log_action", new_callable=AsyncMock) as mock_log:
            result = await update_user_active_status(
                user_id=target_user_id,
                payload=payload,
                request=mock_request,
                users=mock_users_repo,
                current_user=admin_user,
            )

            assert result == deactivated_user
            mock_users_repo.set_active.assert_called_once_with(target_user_id, False)
            mock_log.assert_called_once_with(
                user=admin_user,
                action="user.deactivated",
                resource_type="user",
                resource_id=str(target_user_id),
                request=mock_request,
            )

    @pytest.mark.asyncio
    async def test_update_user_active_status_not_found(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        target_user_id = uuid.uuid4()

        mock_users_repo = AsyncMock()
        mock_users_repo.set_active.return_value = None

        mock_request = MagicMock()
        payload = ActiveStatusUpdateRequest(is_active=False)

        with pytest.raises(NotFoundError) as exc_info:
            await update_user_active_status(
                user_id=target_user_id,
                payload=payload,
                request=mock_request,
                users=mock_users_repo,
                current_user=admin_user,
            )
        assert "User not found" in str(exc_info.value)


# ── 2. Admin Audit Log Tests ──────────────────────────────────────────────────


class TestAdminAuditLog:
    @pytest.mark.asyncio
    async def test_query_audit_log_default_lookback(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_audit_repo = AsyncMock()
        entry = AuditLog(
            id=uuid.uuid4(),
            action="user.login",
            user_id=admin_user.id,
            user_email="admin@nova.example",
            status="success",
            created_at=datetime.now(timezone.utc),
        )
        mock_audit_repo.list.return_value = [entry]
        mock_audit_repo.count.return_value = 1

        res = await query_audit_log(
            audit_logs=mock_audit_repo,
            _current_user=admin_user,
            since=None,  # triggers 90 days default lookback
            limit=50,
            offset=0,
        )

        assert isinstance(res, AuditLogListResponse)
        assert res.total == 1
        assert len(res.entries) == 1
        assert res.limit == 50
        assert res.offset == 0
        mock_audit_repo.list.assert_called_once()
        mock_audit_repo.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_audit_log_with_explicit_filters(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        target_user_id = uuid.uuid4()
        explicit_since = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_audit_repo = AsyncMock()
        mock_audit_repo.list.return_value = []
        mock_audit_repo.count.return_value = 0

        res = await query_audit_log(
            audit_logs=mock_audit_repo,
            _current_user=admin_user,
            user_id=target_user_id,
            action="settings.updated",
            status="success",
            since=explicit_since,
            limit=20,
            offset=40,
        )

        assert res.total == 0
        assert res.entries == []
        mock_audit_repo.list.assert_called_once_with(
            user_id=target_user_id,
            action="settings.updated",
            status="success",
            since=explicit_since,
            limit=20,
            offset=40,
        )
        mock_audit_repo.count.assert_called_once_with(
            user_id=target_user_id,
            action="settings.updated",
            status="success",
            since=explicit_since,
        )


# ── 3. Administration RBAC Permissions Tests ──────────────────────────────────


class TestAdminPermissions:
    @pytest.mark.asyncio
    async def test_user_manage_permission_gating(self):
        dep = require_permission(Permission.USER_MANAGE)

        # ADMIN should be granted access
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        assert await dep(current_user=admin_user) == admin_user

        # Non-admin roles should be rejected with ForbiddenError (403)
        non_admin_roles = [
            UserRole.SECURITY_ENGINEER,
            UserRole.DEVELOPER,
            UserRole.AUDITOR,
            UserRole.READ_ONLY,
        ]
        with patch("app.auth.permissions.log_action", new_callable=AsyncMock):
            for role in non_admin_roles:
                user = User(
                    id=uuid.uuid4(),
                    email=f"{role.value}@nova.example",
                    role=role,
                    is_active=True,
                    auth_provider=AuthProvider.LOCAL,
                )
                with pytest.raises(ForbiddenError):
                    await dep(current_user=user)

    @pytest.mark.asyncio
    async def test_audit_log_read_permission_gating(self):
        dep = require_permission(Permission.AUDIT_LOG_READ)

        # ADMIN, SECURITY_ENGINEER, AUDITOR are authorized to read audit logs
        authorized_roles = [
            UserRole.ADMIN,
            UserRole.SECURITY_ENGINEER,
            UserRole.AUDITOR,
        ]
        for role in authorized_roles:
            user = User(
                id=uuid.uuid4(),
                email=f"{role.value}@nova.example",
                role=role,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            assert await dep(current_user=user) == user

        # DEVELOPER and READ_ONLY must be rejected with ForbiddenError (403)
        unauthorized_roles = [
            UserRole.DEVELOPER,
            UserRole.READ_ONLY,
        ]
        with patch("app.auth.permissions.log_action", new_callable=AsyncMock):
            for role in unauthorized_roles:
                user = User(
                    id=uuid.uuid4(),
                    email=f"{role.value}@nova.example",
                    role=role,
                    is_active=True,
                    auth_provider=AuthProvider.LOCAL,
                )
                with pytest.raises(ForbiddenError):
                    await dep(current_user=user)
