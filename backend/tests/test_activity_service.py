"""
NOVA — Activity Analytics Service & Endpoint Unit Tests
Validates personal activity aggregation (get_my_activity), team-wide activity aggregation
(get_team_activity) with User.full_name, empty states, and endpoint permissions.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.analytics import get_my_activity as api_get_my_activity
from app.api.v1.endpoints.analytics import get_team_activity as api_get_team_activity
from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ForbiddenError
from app.models.enums import AuthProvider, UserRole
from app.models.user import User
from app.schemas.analytics import MyActivitySummary, TeamActivitySummary, TeamMemberActivity
from app.services.analytics.activity_service import get_my_activity, get_team_activity


# ── 1. My Activity Service Tests ──────────────────────────────────────────────


class TestMyActivityService:
    @pytest.mark.asyncio
    async def test_get_my_activity_success(self):
        user_id = uuid.uuid4()
        mock_db = AsyncMock()

        search_res = MagicMock()
        search_res.scalar_one.return_value = 14

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 5

        mock_db.execute.side_effect = [search_res, doc_res]

        summary = await get_my_activity(mock_db, user_id=user_id)

        assert isinstance(summary, MyActivitySummary)
        assert summary.total_scans == 14
        assert summary.scans_by_status == {"completed": 14}
        assert summary.total_findings == 5
        assert summary.findings_by_severity == {"knowledge_docs": 5}
        assert summary.average_scan_duration_seconds == 0.45
        assert summary.average_brs_score == 95.0
        assert summary.recent_scans == []
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_my_activity_zero_data(self):
        user_id = uuid.uuid4()
        mock_db = AsyncMock()

        search_res = MagicMock()
        search_res.scalar_one.return_value = 0

        doc_res = MagicMock()
        doc_res.scalar_one.return_value = 0

        mock_db.execute.side_effect = [search_res, doc_res]

        summary = await get_my_activity(mock_db, user_id=user_id)

        assert summary.total_scans == 0
        assert summary.total_findings == 0
        assert summary.scans_by_status == {"completed": 0}
        assert summary.findings_by_severity == {"knowledge_docs": 0}


# ── 2. Team Activity Service Tests ────────────────────────────────────────────


class TestTeamActivityService:
    @pytest.mark.asyncio
    async def test_get_team_activity_success_with_users(self):
        mock_db = AsyncMock()

        search_res = MagicMock()
        search_res.scalar_one.return_value = 42

        u1_id = uuid.uuid4()
        u2_id = uuid.uuid4()

        members_res = MagicMock()
        members_res.all.return_value = [
            (u1_id, "alice@nova.example", "Alice Engineer"),
            (u2_id, "bob@nova.example", None),  # tests optional full_name
        ]

        mock_db.execute.side_effect = [search_res, members_res]

        summary = await get_team_activity(mock_db)

        assert isinstance(summary, TeamActivitySummary)
        assert summary.total_scans == 42
        assert summary.total_findings == 0
        assert len(summary.members) == 2

        m1 = summary.members[0]
        assert isinstance(m1, TeamMemberActivity)
        assert m1.user_id == u1_id
        assert m1.email == "alice@nova.example"
        assert m1.full_name == "Alice Engineer"
        assert m1.total_scans == 1
        assert m1.total_findings == 0
        assert m1.average_brs_score == 98.0

        m2 = summary.members[1]
        assert m2.user_id == u2_id
        assert m2.email == "bob@nova.example"
        assert m2.full_name is None

    @pytest.mark.asyncio
    async def test_get_team_activity_empty_team(self):
        mock_db = AsyncMock()

        search_res = MagicMock()
        search_res.scalar_one.return_value = 0

        members_res = MagicMock()
        members_res.all.return_value = []

        mock_db.execute.side_effect = [search_res, members_res]

        summary = await get_team_activity(mock_db)

        assert summary.total_scans == 0
        assert summary.total_findings == 0
        assert summary.members == []


# ── 3. Endpoint & Permission Tests ────────────────────────────────────────────


class TestAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_api_get_my_activity(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            full_name="Dev User",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch("app.services.analytics.activity_service.get_my_activity", new_callable=AsyncMock) as mock_svc:
            expected = MyActivitySummary(
                total_scans=10,
                scans_by_status={"completed": 10},
                total_findings=3,
                findings_by_severity={"knowledge_docs": 3},
                recent_scans=[],
            )
            mock_svc.return_value = expected

            res = await api_get_my_activity(current_user=user, db=mock_db)
            assert res == expected
            mock_svc.assert_called_once_with(mock_db, user_id=user.id)

    @pytest.mark.asyncio
    async def test_api_get_team_activity(self):
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@nova.example",
            role=UserRole.ADMIN,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch("app.services.analytics.activity_service.get_team_activity", new_callable=AsyncMock) as mock_svc:
            expected = TeamActivitySummary(total_scans=25, total_findings=0, members=[])
            mock_svc.return_value = expected

            res = await api_get_team_activity(_current_user=admin_user, db=mock_db)
            assert res == expected
            mock_svc.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_team_activity_permission_gate(self):
        # TEAM_ANALYTICS_READ is held by ADMIN, SECURITY_ENGINEER, AUDITOR
        # DEVELOPER and READ_ONLY must be rejected with ForbiddenError
        dev_user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        dep = require_permission(Permission.TEAM_ANALYTICS_READ)

        with patch("app.auth.permissions.log_action", new_callable=AsyncMock):
            with pytest.raises(ForbiddenError):
                await dep(current_user=dev_user)

        # SECURITY_ENGINEER is permitted
        sec_eng_user = User(
            id=uuid.uuid4(),
            email="sec@nova.example",
            role=UserRole.SECURITY_ENGINEER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        passed_user = await dep(current_user=sec_eng_user)
        assert passed_user == sec_eng_user
