"""
NOVA — System Settings Service & API Endpoints Unit Tests
Validates dynamic settings resolution, single-key lookup, bulk upsert, reset behavior,
schema validation, audit logging, and RBAC permission enforcement.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.settings import (
    get_single_setting as api_get_single_setting,
    get_system_settings as api_get_system_settings,
    reset_system_settings as api_reset_system_settings,
    update_single_setting as api_update_single_setting,
    update_system_settings as api_update_system_settings,
)
from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import AuthProvider, UserRole
from app.models.user import User
from app.schemas.settings import (
    SingleSettingResponse,
    SingleSettingUpdateRequest,
    SystemSettingsResetRequest,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
)
from app.services.settings_service import DEFAULT_SETTINGS, settings_service


# ── 1. Settings Service Unit Tests ────────────────────────────────────────────


class TestSettingsServiceUnit:
    @pytest.mark.asyncio
    async def test_get_settings_empty_db_returns_defaults(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        settings = await settings_service.get_settings(mock_db)

        assert settings == DEFAULT_SETTINGS
        assert settings["rag.chunk_size"] == 1000
        assert settings["rag.temperature"] == 0.7
        assert settings["rag.enable_web_search"] is True

    @pytest.mark.asyncio
    async def test_get_settings_with_db_overrides(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        custom_row = SimpleNamespace(key="rag.chunk_size", value=512)
        mock_result.scalars.return_value.all.return_value = [custom_row]
        mock_db.execute.return_value = mock_result

        settings = await settings_service.get_settings(mock_db)

        assert settings["rag.chunk_size"] == 512
        assert settings["rag.temperature"] == 0.7  # default preserved

    @pytest.mark.asyncio
    async def test_get_single_setting_from_db(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = SimpleNamespace(key="rag.top_k", value=10)
        mock_db.execute.return_value = mock_result

        val = await settings_service.get_setting(mock_db, "rag.top_k")
        assert val == 10

    @pytest.mark.asyncio
    async def test_get_single_setting_fallback_to_default(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        val = await settings_service.get_setting(mock_db, "rag.similarity_threshold")
        assert val == 0.15

    @pytest.mark.asyncio
    async def test_get_single_setting_unknown_key(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        val = await settings_service.get_setting(mock_db, "non_existent_key", default="fallback")
        assert val == "fallback"

    @pytest.mark.asyncio
    async def test_update_settings_bulk(self):
        mock_db = AsyncMock()
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = None

        all_result = MagicMock()
        all_result.scalars.return_value.all.return_value = [
            SimpleNamespace(key="rag.temperature", value=0.2)
        ]
        mock_db.execute.side_effect = [lookup_result, all_result]

        updated = await settings_service.update_settings(mock_db, {"rag.temperature": 0.2})
        assert updated["rag.temperature"] == 0.2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_setting_single(self):
        mock_db = AsyncMock()
        lookup_result = MagicMock()
        existing_row = SimpleNamespace(key="rag.chunk_size", value=1000)
        lookup_result.scalar_one_or_none.return_value = existing_row

        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = SimpleNamespace(key="rag.chunk_size", value=2048)

        mock_db.execute.side_effect = [lookup_result, get_result]

        val = await settings_service.update_setting(mock_db, "rag.chunk_size", 2048)
        assert existing_row.value == 2048
        assert val == 2048
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_settings_all(self):
        mock_db = AsyncMock()
        lookup_result = MagicMock()
        row_to_delete = SimpleNamespace(key="rag.temperature", value=0.9)
        lookup_result.scalars.return_value.all.return_value = [row_to_delete]

        all_result = MagicMock()
        all_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [lookup_result, all_result]

        res = await settings_service.reset_settings(mock_db)
        mock_db.delete.assert_called_once_with(row_to_delete)
        mock_db.commit.assert_called_once()
        assert res["rag.temperature"] == 0.7  # restored default

    @pytest.mark.asyncio
    async def test_reset_settings_specific_keys(self):
        mock_db = AsyncMock()
        row = SimpleNamespace(key="rag.chunk_size", value=256)
        lookup_result = MagicMock()
        lookup_result.scalar_one_or_none.return_value = row

        all_result = MagicMock()
        all_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [lookup_result, all_result]

        await settings_service.reset_settings(mock_db, keys=["rag.chunk_size"])
        mock_db.delete.assert_called_once_with(row)
        mock_db.commit.assert_called_once()


# ── 2. Schemas Validation Tests ───────────────────────────────────────────────


class TestSettingsSchemas:
    def test_update_request_accepts_valid_dict(self):
        req = SystemSettingsUpdateRequest(settings={"rag.chunk_size": 500, "rag.temperature": 0.5})
        assert req.settings["rag.chunk_size"] == 500

    def test_update_request_rejects_empty_dict(self):
        with pytest.raises(ValidationError):
            SystemSettingsUpdateRequest(settings={})

    def test_single_setting_request(self):
        req_str = SingleSettingUpdateRequest(value="custom-prompt")
        assert req_str.value == "custom-prompt"

        req_dict = SingleSettingUpdateRequest(value={"nested": 123})
        assert req_dict.value == {"nested": 123}

    def test_reset_request(self):
        req_none = SystemSettingsResetRequest()
        assert req_none.keys is None

        req_keys = SystemSettingsResetRequest(keys=["rag.top_k", "rag.chunk_size"])
        assert req_keys.keys == ["rag.top_k", "rag.chunk_size"]


# ── 3. API Endpoints & Permission Enforcement Tests ───────────────────────────


class TestSettingsEndpoints:
    @pytest.mark.asyncio
    async def test_api_get_system_settings(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch.object(settings_service, "get_settings", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"rag.chunk_size": 1000}
            response = await api_get_system_settings(_current_user=admin_user, db=mock_db)

            assert isinstance(response, SystemSettingsResponse)
            assert response.settings == {"rag.chunk_size": 1000}
            mock_get.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_api_get_single_setting_success(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch.object(settings_service, "get_setting", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = 1000
            response = await api_get_single_setting(
                key="rag.chunk_size",
                _current_user=admin_user,
                db=mock_db,
            )
            assert isinstance(response, SingleSettingResponse)
            assert response.key == "rag.chunk_size"
            assert response.value == 1000

    @pytest.mark.asyncio
    async def test_api_get_single_setting_not_found(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch.object(settings_service, "get_setting", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            with pytest.raises(NotFoundError) as exc_info:
                await api_get_single_setting(
                    key="unknown.key",
                    _current_user=admin_user,
                    db=mock_db,
                )
            assert "Setting 'unknown.key' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_api_update_system_settings_bulk(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = SystemSettingsUpdateRequest(settings={"rag.chunk_size": 2000})

        with patch.object(settings_service, "update_settings", new_callable=AsyncMock) as mock_update:
            with patch("app.api.v1.endpoints.settings.log_action", new_callable=AsyncMock) as mock_log:
                mock_update.return_value = {"rag.chunk_size": 2000}
                res = await api_update_system_settings(
                    payload=payload,
                    request=mock_request,
                    current_user=admin_user,
                    db=mock_db,
                )
                assert res.settings == {"rag.chunk_size": 2000}
                mock_update.assert_called_once_with(mock_db, {"rag.chunk_size": 2000})
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_update_single_setting(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = SingleSettingUpdateRequest(value=0.5)

        with patch.object(settings_service, "update_setting", new_callable=AsyncMock) as mock_update:
            with patch("app.api.v1.endpoints.settings.log_action", new_callable=AsyncMock) as mock_log:
                mock_update.return_value = 0.5
                res = await api_update_single_setting(
                    key="rag.temperature",
                    payload=payload,
                    request=mock_request,
                    current_user=admin_user,
                    db=mock_db,
                )
                assert res.key == "rag.temperature"
                assert res.value == 0.5
                mock_update.assert_called_once_with(mock_db, "rag.temperature", 0.5)
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_reset_system_settings(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        payload = SystemSettingsResetRequest(keys=["rag.chunk_size"])

        with patch.object(settings_service, "reset_settings", new_callable=AsyncMock) as mock_reset:
            with patch("app.api.v1.endpoints.settings.log_action", new_callable=AsyncMock) as mock_log:
                mock_reset.return_value = DEFAULT_SETTINGS
                res = await api_reset_system_settings(
                    request=mock_request,
                    current_user=admin_user,
                    db=mock_db,
                    payload=payload,
                )
                assert res.settings == DEFAULT_SETTINGS
                mock_reset.assert_called_once_with(mock_db, keys=["rag.chunk_size"])
                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_gate_enforcement(self):
        # ADMIN_WRITE is strictly reserved for UserRole.ADMIN
        # Other roles (SECURITY_ENGINEER, DEVELOPER, AUDITOR, READ_ONLY) must get ForbiddenError (403)
        dep = require_permission(Permission.ADMIN_WRITE)

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

            admin_user = User(
                id=uuid.uuid4(),
                email="admin@nova.example",
                role=UserRole.ADMIN,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            passed = await dep(current_user=admin_user)
            assert passed == admin_user
