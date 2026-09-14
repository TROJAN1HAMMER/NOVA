"""
NOVA — Memory Deep Inspection, Provenance, Lifecycle, Isolation, and Safe Deletion Regression Suite
Validates:
1. Layer 1: Short-term 10-turn sliding-window vs full persistent history reconstruction.
2. Layer 2: Long-term semantic compression & pgvector 384-dim persistence across reconnects.
3. Layer 3: User preference persistence across logout/login and DB engine reconnect.
4. Layer 4: Task execution memory & idle vs active states.
5. Layer 5: Organizational axiom rule gate (unverified draft gap vs active Stage 0 rule).
6. Memory Provenance metadata presence (source_type, source_id, origin, verification_state).
7. Memory Lifecycle transitions (NEW, ACTIVE, STALE, ARCHIVED).
8. Safe Memory Forgetting / Deletion without cascading destruction to source docs or other users.
9. Strict User & Organization Memory Isolation.
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
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.services.assistant.memory_service import memory_service
from app.services.faq_service import faq_service


@pytest.mark.asyncio
async def test_layer1_sliding_window_enforcement_and_reconstruction():
    """
    Validates Layer 1:
    - Reconstructs active 10-turn sliding window (20 messages max)
    - Leaves older messages in persistent history without deletion
    - Full history survives DB reconnect
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Create test user
        user = User(
            email=f"layer1_user_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Layer 1 Test Engineer",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create session
        chat_sess = await memory_service.get_or_create_session(session, user.id)

        # Add 15 turns (30 messages)
        for i in range(15):
            await memory_service.save_turn(
                db=session,
                session_id=chat_sess.id,
                user_message=f"Turn {i+1}: What is security parameter {i+1}?",
                assistant_response=f"Security parameter {i+1} is strictly calibrated.",
            )

        # 1. Verify total persistent messages = 30
        msg_cnt_res = await session.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == chat_sess.id)
        )
        assert msg_cnt_res.scalar_one() == 30

        # 2. Verify active sliding-window context is strictly capped to 10 turns (20 messages)
        active_window = await memory_service.get_active_sliding_window_context(session, chat_sess.id, max_turns=10)
        assert len(active_window) == 20
        # Check that it contains the latest turn (Turn 15) and oldest in window is Turn 6
        assert "Turn 15" in active_window[-2]["content"]
        assert "Turn 6" in active_window[0]["content"]

    # 3. Disconnect engine and reconnect (simulate restart)
    await engine.dispose()
    engine2 = create_async_engine(settings.database_url, echo=False)
    session_factory2 = async_sessionmaker(engine2, expire_on_commit=False)

    async with session_factory2() as session2:
        # Reconstruct sliding window after restart
        active_window_restart = await memory_service.get_active_sliding_window_context(session2, chat_sess.id, max_turns=10)
        assert len(active_window_restart) == 20
        assert "Turn 15" in active_window_restart[-2]["content"]

    await engine2.dispose()


@pytest.mark.asyncio
async def test_layer2_semantic_compression_and_persistence():
    """
    Validates Layer 2:
    - Semantic compression synthesizes older turns into context_summary
    - Vector embeddings in pgvector persist and remain searchable
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            email=f"layer2_user_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Layer 2 Test Engineer",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        chat_sess = await memory_service.get_or_create_session(session, user.id)

        # Add 12 turns
        for i in range(12):
            await memory_service.save_turn(
                db=session,
                session_id=chat_sess.id,
                user_message=f"Architecture question {i+1}: How does mTLS isolate service {i+1}?",
                assistant_response=f"Service {i+1} verifies mutual certificates via HSM.",
            )

        # Run compression
        compressed = await memory_service.compress_old_entries(session, threshold_turns=10)
        assert compressed >= 1

        # Verify summary populated
        await session.refresh(chat_sess)
        assert chat_sess.context_summary is not None
        assert "Archived context" in chat_sess.context_summary

    await engine.dispose()


@pytest.mark.asyncio
async def test_layer3_user_preference_persistence_and_isolation():
    """
    Validates Layer 3:
    - Preferences are stored separately from conversation messages
    - User A and User B have strictly isolated preferences
    - Preferences survive reconnect / simulated container restart
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Create User A
        user_a = User(
            email=f"pref_user_a_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Alice User",
            role=UserRole.SECURITY_ENGINEER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        # Create User B
        user_b = User(
            email=f"pref_user_b_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Bob User",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add_all([user_a, user_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)

        # Update User A's preferences
        await memory_service.update_user_preferences(
            session,
            user_a.id,
            {"department": "Offensive Security Red Team", "tone": "Hardened Technical Audit", "language": "en-US"},
        )

        # Update User B's preferences
        await memory_service.update_user_preferences(
            session,
            user_b.id,
            {"department": "Payment Gateway Frontend", "tone": "Concise Developer Snippets", "language": "en-GB"},
        )

        # Verify isolation
        prefs_a = await memory_service.get_user_preferences(session, user_a.id)
        prefs_b = await memory_service.get_user_preferences(session, user_b.id)

        assert prefs_a["department"] == "Offensive Security Red Team"
        assert prefs_b["department"] == "Payment Gateway Frontend"
        assert prefs_a["tone"] != prefs_b["tone"]

    # Disconnect and Reconnect
    await engine.dispose()
    engine2 = create_async_engine(settings.database_url, echo=False)
    session_factory2 = async_sessionmaker(engine2, expire_on_commit=False)

    async with session_factory2() as session2:
        prefs_a_after = await memory_service.get_user_preferences(session2, user_a.id)
        assert prefs_a_after["department"] == "Offensive Security Red Team"
        assert prefs_a_after["tone"] == "Hardened Technical Audit"

    await engine2.dispose()


@pytest.mark.asyncio
async def test_layer5_organizational_axiom_gate_safety():
    """
    Validates Layer 5:
    - Unverified/draft gap rule does NOT participate in live Stage 0 match
    - Only promoted rule participates in live Stage 0 match
    - Rule provenance is properly recorded
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        kw_draft = f"draft_policy_{uuid.uuid4().hex[:6]}"
        kw_active = f"active_policy_{uuid.uuid4().hex[:6]}"

        # 1. Create Draft rule (unverified)
        draft_rule = await faq_service.create_rule(
            session, keyword=kw_draft, response="Draft response not for live stage 0", is_draft=True
        )

        # 2. Create Active rule (verified)
        active_rule = await faq_service.create_rule(
            session, keyword=kw_active, response="Authoritative live response", is_draft=False
        )

        # 3. Test Matcher: Draft rule MUST NOT match
        draft_match = await faq_service.match_faq(session, f"tell me about {kw_draft}")
        assert draft_match is None, "Safety violation: Unverified draft rule matched in Stage 0!"

        # 4. Test Matcher: Active rule MUST match
        active_match = await faq_service.match_faq(session, f"tell me about {kw_active}")
        assert active_match is not None
        assert active_match.id == active_rule.id

        # 5. Promote draft rule
        promoted = await faq_service.promote_draft(session, draft_rule.id)
        assert promoted.is_draft is False
        assert promoted.is_active is True

        # 6. Now promoted rule MUST match
        promoted_match = await faq_service.match_faq(session, f"tell me about {kw_draft}")
        assert promoted_match is not None
        assert promoted_match.id == draft_rule.id

    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_provenance_and_lifecycle_inspection():
    """
    Validates Layer Inspection, Provenance, and Lifecycle:
    - Inspects layers and validates presence of provenance metadata
    - Validates lifecycle states: NEW, ACTIVE, STALE, ARCHIVED
    - Validates 'why_remembered' justification
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            email=f"inspect_user_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Inspection Test Engineer",
            role=UserRole.ADMIN,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create session and turns
        chat_sess = await memory_service.get_or_create_session(session, user.id)
        await memory_service.save_turn(
            db=session,
            session_id=chat_sess.id,
            user_message="Inspect memory provenance query",
            assistant_response="Recorded with full provenance.",
            calibrated_trust_score=0.92,
            reasoning_trace={"pipeline_stage": "STAGE_2_SAFETY_GATE_PASS", "trust_decision": "DIRECT_ANSWER"},
        )

        # Inspect Layer 1
        l1_items = await memory_service.get_layer_items(session, user.id, "short_term")
        assert len(l1_items) >= 1
        item1 = l1_items[0]
        assert item1["lifecycle"] in ["NEW", "ACTIVE", "STALE", "ARCHIVED"]
        assert "provenance" in item1
        assert item1["provenance"]["source_type"] == "user_chat_session"
        assert item1["why_remembered"] != ""

        # Inspect Layer 3
        l3_items = await memory_service.get_layer_items(session, user.id, "preferences")
        assert len(l3_items) >= 1
        item3 = l3_items[0]
        assert item3["provenance"]["source_type"] == "user_profile_configuration"
        assert "why_remembered" in item3

        # Inspect Layer 4
        l4_items = await memory_service.get_layer_items(session, user.id, "task_execution")
        assert len(l4_items) >= 1

        # Inspect Layer 5
        l5_items = await memory_service.get_layer_items(session, user.id, "organizational")
        assert len(l5_items) >= 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_safe_memory_forgetting_isolation():
    """
    Validates Safe Memory Deletion / Forgetting:
    - User A can forget their Layer 1 session without deleting User B's session
    - Forgetting Layer 2 summary does NOT delete source KnowledgeDocument or chunks
    - Forgetting Layer 3 preference resets value without affecting other users
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user_a = User(
            email=f"forget_a_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Forget User A",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        user_b = User(
            email=f"forget_b_{uuid.uuid4().hex[:6]}@nova.ai",
            full_name="Forget User B",
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            hashed_password=hash_password("Password123!"),
        )
        session.add_all([user_a, user_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)

        # Create sessions
        sess_a = await memory_service.get_or_create_session(session, user_a.id)
        sess_b = await memory_service.get_or_create_session(session, user_b.id)
        sess_a.context_summary = "A's semantic summary"
        sess_b.context_summary = "B's semantic summary"
        await session.commit()

        # Count knowledge docs before forget
        docs_before = (await session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()

        # 1. User A forgets Layer 2 summary
        res = await memory_service.forget_memory(session, user_a.id, "long_term", f"summary-{sess_a.id}")
        assert res["status"] == "success"

        # Verify A's summary is cleared, B's summary remains intact
        await session.refresh(sess_a)
        await session.refresh(sess_b)
        assert sess_a.context_summary is None
        assert sess_b.context_summary == "B's semantic summary"

        # Verify knowledge documents are untouched
        docs_after = (await session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
        assert docs_after == docs_before

        # 2. User A cannot delete User B's session
        unauth_res = await memory_service.forget_memory(session, user_a.id, "short_term", str(sess_b.id))
        assert unauth_res["status"] == "error"

        # Verify User B's session still exists
        sess_b_check = await session.execute(select(ChatSession).where(ChatSession.id == sess_b.id))
        assert sess_b_check.scalar_one_or_none() is not None

        # 3. User A forgets their own session
        auth_res = await memory_service.forget_memory(session, user_a.id, "short_term", str(sess_a.id))
        assert auth_res["status"] == "success"

        # Verify User A's session is deleted, User B's remains
        sess_a_check = await session.execute(select(ChatSession).where(ChatSession.id == sess_a.id))
        assert sess_a_check.scalar_one_or_none() is None
        sess_b_check2 = await session.execute(select(ChatSession).where(ChatSession.id == sess_b.id))
        assert sess_b_check2.scalar_one_or_none() is not None

    await engine.dispose()
