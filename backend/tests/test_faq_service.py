"""
NOVA — FAQ Service & Knowledge Gap Inbox Unit Tests
Validates deterministic Stage-0 FAQ keyword matching, case insensitivity,
longest keyword prioritization, active/draft filtering, gap inbox promotion,
lifecycle operations, and RBAC permission gating.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.faq import (
    FAQRuleCreate,
    create_faq as api_create_faq,
    delete_faq as api_delete_faq,
    get_evolution_metrics as api_get_evolution_metrics,
    get_gap_inbox as api_get_gap_inbox,
    list_faq as api_list_faq,
    promote_draft_faq as api_promote_draft_faq,
)
from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ForbiddenError
from app.models.enums import AuthProvider, UserRole
from app.models.faq_rule import FAQRule
from app.models.user import User
from app.services.faq_service import FAQService, faq_service


# ── 1. FAQ Service Unit Tests ─────────────────────────────────────────────────


class TestFAQServiceUnit:
    @pytest.mark.asyncio
    async def test_match_faq_exact_and_substring(self):
        mock_db = AsyncMock()
        rule = FAQRule(
            id=uuid.uuid4(),
            keyword="password reset",
            response="Go to Settings -> Security to reset your password.",
            is_active=True,
            is_draft=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_db.execute.return_value = mock_result

        match = await faq_service.match_faq(mock_db, "How do I perform a password reset?")
        assert match is not None
        assert match.keyword == "password reset"
        assert match.response == "Go to Settings -> Security to reset your password."

    @pytest.mark.asyncio
    async def test_match_faq_case_insensitive(self):
        mock_db = AsyncMock()
        rule = FAQRule(
            id=uuid.uuid4(),
            keyword="API Token",
            response="Generate tokens from the Developer Settings page.",
            is_active=True,
            is_draft=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_db.execute.return_value = mock_result

        match = await faq_service.match_faq(mock_db, "HOW DO I CREATE AN api token FOR NOVA?")
        assert match is not None
        assert match.keyword == "API Token"

    @pytest.mark.asyncio
    async def test_match_faq_longest_keyword_priority(self):
        mock_db = AsyncMock()
        short_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="vpn",
            response="Generic VPN instructions.",
            is_active=True,
            is_draft=False,
        )
        long_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="vpn access request",
            response="Specific workflow for VPN access requests.",
            is_active=True,
            is_draft=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [short_rule, long_rule]
        mock_db.execute.return_value = mock_result

        match = await faq_service.match_faq(mock_db, "I need to submit a vpn access request today")
        assert match is not None
        # Longest matching keyword should be chosen
        assert match.keyword == "vpn access request"
        assert match.response == "Specific workflow for VPN access requests."

    @pytest.mark.asyncio
    async def test_match_faq_no_match(self):
        mock_db = AsyncMock()
        rule = FAQRule(
            id=uuid.uuid4(),
            keyword="sso login",
            response="SSO guidance.",
            is_active=True,
            is_draft=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule]
        mock_db.execute.return_value = mock_result

        match = await faq_service.match_faq(mock_db, "What is the capital of France?")
        assert match is None

    @pytest.mark.asyncio
    async def test_list_rules_exclude_drafts(self):
        mock_db = AsyncMock()
        active_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="active kw",
            response="active res",
            is_active=True,
            is_draft=False,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_rule]
        mock_db.execute.return_value = mock_result

        rules = await faq_service.list_rules(mock_db, include_drafts=False)
        assert len(rules) == 1
        assert rules[0].is_draft is False

    @pytest.mark.asyncio
    async def test_list_rules_include_drafts(self):
        mock_db = AsyncMock()
        active_rule = FAQRule(id=uuid.uuid4(), keyword="kw1", response="res1", is_draft=False)
        draft_rule = FAQRule(id=uuid.uuid4(), keyword="kw2", response="res2", is_draft=True)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_rule, draft_rule]
        mock_db.execute.return_value = mock_result

        rules = await faq_service.list_rules(mock_db, include_drafts=True)
        assert len(rules) == 2

    @pytest.mark.asyncio
    async def test_create_rule(self):
        mock_db = AsyncMock()
        creator_id = uuid.uuid4()

        rule = await faq_service.create_rule(
            db=mock_db,
            keyword="  git auth  ",
            response="  Use SSH keys.  ",
            user_id=creator_id,
            is_draft=False,
        )

        assert rule.keyword == "git auth"
        assert rule.response == "Use SSH keys."
        assert rule.is_active is True
        assert rule.is_draft is False
        assert rule.created_by_id == creator_id
        mock_db.add.assert_called_once_with(rule)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(rule)

    @pytest.mark.asyncio
    async def test_promote_draft_success(self):
        mock_db = AsyncMock()
        rule_id = uuid.uuid4()
        draft_rule = FAQRule(
            id=rule_id,
            keyword="unanswered query",
            response="Generated response",
            is_active=False,
            is_draft=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = draft_rule
        mock_db.execute.return_value = mock_result

        promoted = await faq_service.promote_draft(mock_db, rule_id)
        assert promoted is not None
        assert promoted.is_draft is False
        assert promoted.is_active is True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(draft_rule)

    @pytest.mark.asyncio
    async def test_promote_draft_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        promoted = await faq_service.promote_draft(mock_db, uuid.uuid4())
        assert promoted is None
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_rule_success(self):
        mock_db = AsyncMock()
        rule_id = uuid.uuid4()
        rule = FAQRule(id=rule_id, keyword="kw", response="res")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = rule
        mock_db.execute.return_value = mock_result

        deleted = await faq_service.delete_rule(mock_db, rule_id)
        assert deleted is True
        mock_db.delete.assert_called_once_with(rule)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        deleted = await faq_service.delete_rule(mock_db, uuid.uuid4())
        assert deleted is False
        mock_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_evolution_metrics_empty_db(self):
        mock_db = AsyncMock()

        stats_mock = MagicMock()
        stats_mock.one.return_value = (0, 0, 0)

        rules_mock = MagicMock()
        rules_mock.one.return_value = (0, 0)

        mock_db.execute.side_effect = [stats_mock, rules_mock]

        metrics = await faq_service.get_evolution_metrics(mock_db)

        assert metrics["total_queries"] == 0
        assert metrics["failure_refusal_rate"] is None
        assert metrics["stage_0_match_ratio"] is None
        assert metrics["pending_gap_candidates_count"] == 0
        assert metrics["active_faq_count"] == 0

    @pytest.mark.asyncio
    async def test_get_evolution_metrics_populated(self):
        mock_db = AsyncMock()

        # 100 queries: 10 failures, 40 Stage 0 hits
        stats_mock = MagicMock()
        stats_mock.one.return_value = (100, 10, 40)

        # 3 draft rules, 7 active rules
        rules_mock = MagicMock()
        rules_mock.one.return_value = (3, 7)

        mock_db.execute.side_effect = [stats_mock, rules_mock]

        metrics = await faq_service.get_evolution_metrics(mock_db)

        assert metrics["total_queries"] == 100
        assert metrics["failure_refusal_rate"] == 0.10
        assert metrics["stage_0_match_ratio"] == 0.40
        assert metrics["pending_gap_candidates_count"] == 3
        assert metrics["active_faq_count"] == 7


# ── 2. FAQ Endpoints Tests ───────────────────────────────────────────────────


class TestFAQEndpoints:
    @pytest.mark.asyncio
    async def test_api_list_faq(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        rule = FAQRule(
            id=uuid.uuid4(),
            keyword="kw",
            response="res",
            is_active=True,
            is_draft=False,
        )

        with patch.object(faq_service, "list_rules", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [rule]
            res = await api_list_faq(current_user=user, db=mock_db)

            assert len(res) == 1
            assert res[0].keyword == "kw"
            mock_list.assert_called_once_with(mock_db, include_drafts=False)

    @pytest.mark.asyncio
    async def test_api_create_faq(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        payload = FAQRuleCreate(keyword="new kw", response="new res")
        created_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="new kw",
            response="new res",
            is_active=True,
            is_draft=False,
        )

        with patch.object(faq_service, "create_rule", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = created_rule
            res = await api_create_faq(payload=payload, current_user=user, db=mock_db)

            assert res.keyword == "new kw"
            mock_create.assert_called_once_with(
                mock_db,
                keyword="new kw",
                response="new res",
                user_id=user.id,
            )

    @pytest.mark.asyncio
    async def test_api_delete_faq_success(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        target_id = uuid.uuid4()

        with patch.object(faq_service, "delete_rule", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = True
            # Should return None with HTTP 204
            res = await api_delete_faq(rule_id=target_id, current_user=user, db=mock_db)
            assert res is None
            mock_del.assert_called_once_with(mock_db, target_id)

    @pytest.mark.asyncio
    async def test_api_delete_faq_not_found(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        target_id = uuid.uuid4()

        with patch.object(faq_service, "delete_rule", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = False
            with pytest.raises(HTTPException) as exc_info:
                await api_delete_faq(rule_id=target_id, current_user=user, db=mock_db)
            assert exc_info.value.status_code == 404
            assert "FAQ rule not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_get_gap_inbox(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        draft_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="gap query",
            response="suggested response",
            is_active=True,
            is_draft=True,
        )
        published_rule = FAQRule(
            id=uuid.uuid4(),
            keyword="pub",
            response="res",
            is_active=True,
            is_draft=False,
        )

        with patch.object(faq_service, "list_rules", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [draft_rule, published_rule]
            res = await api_get_gap_inbox(current_user=user, db=mock_db)

            # Must only return draft rules
            assert len(res) == 1
            assert res[0].keyword == "gap query"
            assert res[0].is_draft is True
            mock_list.assert_called_once_with(mock_db, include_drafts=True)

    @pytest.mark.asyncio
    async def test_api_promote_draft_faq_success(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        target_id = uuid.uuid4()
        promoted = FAQRule(
            id=target_id,
            keyword="promoted kw",
            response="promoted res",
            is_active=True,
            is_draft=False,
        )

        with patch.object(faq_service, "promote_draft", new_callable=AsyncMock) as mock_promote:
            mock_promote.return_value = promoted
            res = await api_promote_draft_faq(rule_id=target_id, current_user=user, db=mock_db)

            assert res.id == target_id
            assert res.is_draft is False
            mock_promote.assert_called_once_with(mock_db, target_id)

    @pytest.mark.asyncio
    async def test_api_promote_draft_faq_not_found(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()
        target_id = uuid.uuid4()

        with patch.object(faq_service, "promote_draft", new_callable=AsyncMock) as mock_promote:
            mock_promote.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await api_promote_draft_faq(rule_id=target_id, current_user=user, db=mock_db)
            assert exc_info.value.status_code == 404
            assert "Draft FAQ rule not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_get_evolution_metrics(self):
        user = User(
            id=uuid.uuid4(),
            email="dev@nova.example",
            role=UserRole.DEVELOPER,
            is_active=True,
            auth_provider=AuthProvider.LOCAL,
        )
        mock_db = AsyncMock()

        with patch.object(faq_service, "get_evolution_metrics", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "total_queries": 50,
                "failure_refusal_rate": 0.04,
                "stage_0_match_ratio": 0.30,
                "pending_gap_candidates_count": 2,
                "active_faq_count": 8,
            }
            res = await api_get_evolution_metrics(current_user=user, db=mock_db)

            assert res.total_queries == 50
            assert res.failure_refusal_rate == 0.04
            assert res.stage_0_match_ratio == 0.30
            assert res.pending_gap_candidates_count == 2
            assert res.active_faq_count == 8
            mock_get.assert_called_once_with(mock_db)


# ── 3. FAQ Permissions Tests ──────────────────────────────────────────────────


class TestFAQPermissions:
    @pytest.mark.asyncio
    async def test_knowledge_read_permission_gating(self):
        dep = require_permission(Permission.KNOWLEDGE_READ)

        # All 5 roles have KNOWLEDGE_READ
        for role in UserRole:
            user = User(
                id=uuid.uuid4(),
                email=f"{role.value}@nova.example",
                role=role,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            assert await dep(current_user=user) == user

    @pytest.mark.asyncio
    async def test_knowledge_write_permission_gating(self):
        dep = require_permission(Permission.KNOWLEDGE_WRITE)

        # ADMIN, SECURITY_ENGINEER, DEVELOPER have KNOWLEDGE_WRITE
        authorized_roles = [
            UserRole.ADMIN,
            UserRole.SECURITY_ENGINEER,
            UserRole.DEVELOPER,
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

        # AUDITOR and READ_ONLY must be rejected with ForbiddenError (403)
        unauthorized_roles = [
            UserRole.AUDITOR,
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
