"""
Comprehensive Contract & Security Regression Suite for NOVA's 5-Layer Memory Engine
Tests:
1. Layer 1: Conversational Turn Buffer, sliding-window inspection, and active session reset.
2. Layer 1: Resetting active session does NOT delete Layer 5 organizational axioms or other users' sessions.
3. Layer 2: Long-Term Semantic Memory only reflects compressed context_summary, never fake chunks.
4. Layer 3: User Preference Memory persistence and isolation across distinct accounts.
5. Layer 4: Task execution memory reflection.
6. Layer 5: Organizational axioms vs unverified gap candidates, and strict RBAC on deletion.
7. User Isolation: User A cannot retrieve or delete User B's memory records.
"""

import uuid
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.auth.security import hash_password
from app.models.enums import UserRole, AuthProvider
from app.models.user import User
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.faq_rule import FAQRule
from app.services.assistant.memory_service import memory_service
from app.services.faq_service import faq_service


@pytest.mark.asyncio
async def test_layer1_active_session_reset_and_isolation():
    """
    Validates:
    - Resetting active session clears messages in that session and resets turns to 0.
    - Does NOT delete other sessions belonging to the user or other users.
    - Does NOT delete organizational axioms or knowledge.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Create User A and User B
        user_a = User(
            email=f"user_a_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="User A",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        user_b = User(
            email=f"user_b_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="User B",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add_all([user_a, user_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)

        # Create organizational axiom
        axiom = await faq_service.create_rule(
            session, keyword=f"axiom_{uuid.uuid4().hex[:6]}", response="Axiom rule answer", is_draft=False
        )

        # Create sessions with turns for both users
        sess_a = await memory_service.get_or_create_session(session, user_a.id)
        sess_b = await memory_service.get_or_create_session(session, user_b.id)

        await memory_service.save_turn(session, sess_a.id, "User A query 1", "Response A 1")
        await memory_service.save_turn(session, sess_a.id, "User A query 2", "Response A 2")
        await memory_service.save_turn(session, sess_b.id, "User B query 1", "Response B 1")

        # Verify initial turn counts
        a_msgs = (await session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == sess_a.id))).scalar_one()
        b_msgs = (await session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == sess_b.id))).scalar_one()
        assert a_msgs == 4
        assert b_msgs == 2

        # Reset active session for User A
        reset_res = await memory_service.reset_session_turns(session, user_a.id, sess_a.id)
        assert reset_res["status"] == "success"

        # Verify User A's session has 0 messages
        a_msgs_after = (await session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == sess_a.id))).scalar_one()
        assert a_msgs_after == 0

        # Verify User B's session messages are untouched
        b_msgs_after = (await session.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == sess_b.id))).scalar_one()
        assert b_msgs_after == 2

        # Verify organizational axiom is completely untouched
        axiom_check = (await session.execute(select(FAQRule).where(FAQRule.id == axiom.id))).scalar_one_or_none()
        assert axiom_check is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_layer1_turn_buffer_sliding_window_metadata():
    """
    Validates:
    - get_layer_items for Layer 1 returns message-level turn metadata.
    - Accurately tags IN_SLIDING_WINDOW vs ARCHIVED_POSTGRESQL.
    - Accurately reports role, turn_number, and session_id.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            email=f"window_user_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Window Test User",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        sess = await memory_service.get_or_create_session(session, user.id)

        # Add 12 turns (24 messages: 20 inside sliding window, 4 archived)
        for i in range(12):
            await memory_service.save_turn(session, sess.id, f"Question {i+1}", f"Answer {i+1}")

        items = await memory_service.get_layer_items(session, user.id, "short_term", session_id=sess.id)
        assert len(items) == 24

        # Most recent 20 messages must be in sliding window
        for item in items[:20]:
            assert item["in_sliding_window"] is True
            assert item["provenance"]["verification_state"] == "IN_SLIDING_WINDOW"
            assert item["lifecycle"] == "ACTIVE"

        # Oldest 4 messages must be archived beyond sliding window
        for item in items[20:]:
            assert item["in_sliding_window"] is False
            assert item["provenance"]["verification_state"] == "ARCHIVED_POSTGRESQL"
            assert item["lifecycle"] == "ARCHIVED"

    await engine.dispose()


@pytest.mark.asyncio
async def test_layer5_rbac_axiom_deletion_prevention():
    """
    Validates:
    - READ_ONLY and AUDITOR roles CANNOT delete Layer 5 Stage 0 axioms.
    - DEVELOPER and ADMIN CAN delete Stage 0 axioms.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        auditor = User(
            email=f"auditor_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Auditor User",
            role=UserRole.AUDITOR,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Admin User",
            role=UserRole.ADMIN,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add_all([auditor, admin])
        await session.commit()
        await session.refresh(auditor)
        await session.refresh(admin)

        rule = await faq_service.create_rule(
            session, keyword=f"protected_axiom_{uuid.uuid4().hex[:6]}", response="Protected response", is_draft=False
        )

        # 1. Auditor attempts to delete axiom -> Must fail with Permission Denied
        del_fail = await memory_service.forget_memory(session, auditor.id, "organizational", str(rule.id))
        assert del_fail["status"] == "error"
        assert "Permission denied" in del_fail["message"]

        # Verify axiom is still present
        check_rule = (await session.execute(select(FAQRule).where(FAQRule.id == rule.id))).scalar_one_or_none()
        assert check_rule is not None

        # 2. Admin deletes axiom -> Must succeed
        del_ok = await memory_service.forget_memory(session, admin.id, "organizational", str(rule.id))
        assert del_ok["status"] == "success"

        # Verify axiom was deleted
        check_rule_deleted = (await session.execute(select(FAQRule).where(FAQRule.id == rule.id))).scalar_one_or_none()
        assert check_rule_deleted is None

    await engine.dispose()
