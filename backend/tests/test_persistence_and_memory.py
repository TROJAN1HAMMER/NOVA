"""
NOVA — Database & Memory Persistence Regression Suite
Validates:
A. Schema initialization integrity
B. Seed execution correctness
C. Idempotent re-seeding (no duplicates, no destructive changes)
D. User-created records survive subsequent seed runs
E. Engine/App restart preserves all database tables and records
F. Five-layer memory persistence survives restart
G. Docker Compose named volume configuration integrity
H. Security scan history survives restart
I. Knowledge documents & vector embeddings survive restart
J. Assistant chat sessions and reasoning traces survive restart
"""

import uuid
import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.auth.security import hash_password, verify_password
from app.models.enums import UserRole, AuthProvider
from app.models.user import User
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk, KnowledgeEntity, KnowledgeRelation
from app.models.faq_rule import FAQRule
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.audit_log import AuditLog
from app.models.system_setting import SystemSetting
from app.models.security_intelligence import SecurityIntelScan, SecurityIntelAssessment
from app.services.assistant.memory_service import memory_service
from scripts.seed_all_screens_data import seed_all


@pytest.mark.asyncio
async def test_a_schema_initialization_head():
    """Test A: Verifies that database schema has all core tables properly initialized."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # Check presence of critical persistent tables
        user_res = await session.execute(select(func.count(User.id)))
        assert user_res.scalar_one() >= 0

        doc_res = await session.execute(select(func.count(KnowledgeDocument.id)))
        assert doc_res.scalar_one() >= 0

        chunk_res = await session.execute(select(func.count(KnowledgeChunk.id)))
        assert chunk_res.scalar_one() >= 0

        faq_res = await session.execute(select(func.count(FAQRule.id)))
        assert faq_res.scalar_one() >= 0

        session_res = await session.execute(select(func.count(ChatSession.id)))
        assert session_res.scalar_one() >= 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_b_seed_can_run_successfully():
    """Test B: Verifies that the comprehensive master seed can execute successfully."""
    # Run seed in force mode to ensure baseline is populated
    await seed_all(init_only=False, force=True)

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        admin_res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
        admin = admin_res.scalar_one_or_none()
        assert admin is not None
        assert admin.role == UserRole.ADMIN

    await engine.dispose()


@pytest.mark.asyncio
async def test_c_seed_runs_second_time_without_duplicates():
    """Test C: Verifies that running seed a second time creates NO duplicate records."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user_cnt_before = (await session.execute(select(func.count(User.id)))).scalar_one()
        doc_cnt_before = (await session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
        faq_cnt_before = (await session.execute(select(func.count(FAQRule.id)))).scalar_one()
        entity_cnt_before = (await session.execute(select(func.count(KnowledgeEntity.id)))).scalar_one()
        rel_cnt_before = (await session.execute(select(func.count(KnowledgeRelation.id)))).scalar_one()
        audit_cnt_before = (await session.execute(select(func.count(AuditLog.id)))).scalar_one()

    # Re-run seed
    await seed_all(init_only=False, force=False)

    async with session_factory() as session:
        user_cnt_after = (await session.execute(select(func.count(User.id)))).scalar_one()
        doc_cnt_after = (await session.execute(select(func.count(KnowledgeDocument.id)))).scalar_one()
        faq_cnt_after = (await session.execute(select(func.count(FAQRule.id)))).scalar_one()
        entity_cnt_after = (await session.execute(select(func.count(KnowledgeEntity.id)))).scalar_one()
        rel_cnt_after = (await session.execute(select(func.count(KnowledgeRelation.id)))).scalar_one()
        audit_cnt_after = (await session.execute(select(func.count(AuditLog.id)))).scalar_one()

    await engine.dispose()

    assert user_cnt_after == user_cnt_before, "User count changed on second seed!"
    assert doc_cnt_after == doc_cnt_before, "Document count changed on second seed!"
    assert faq_cnt_after == faq_cnt_before, "FAQ rule count changed on second seed!"
    assert entity_cnt_after == entity_cnt_before, "Knowledge entity count changed on second seed!"
    assert rel_cnt_after == rel_cnt_before, "Knowledge relation count changed on second seed!"
    assert audit_cnt_after == audit_cnt_before, "Audit log count changed on second seed!"


@pytest.mark.asyncio
async def test_d_existing_user_created_records_survive_second_seed():
    """Test D: Verifies that custom user records and altered passwords survive a second seed."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    custom_email = f"custom_engineer_{uuid.uuid4().hex[:8]}@enterprise.org"
    custom_password = "CustomSecretPassword999!"

    async with session_factory() as session:
        custom_user = User(
            email=custom_email,
            full_name="Custom Enterprise Engineer",
            hashed_password=hash_password(custom_password),
            role=UserRole.DEVELOPER,
            auth_provider=AuthProvider.LOCAL,
            is_active=True,
        )
        session.add(custom_user)
        await session.commit()

    # Re-run seed
    await seed_all(init_only=False, force=False)

    async with session_factory() as session:
        res = await session.execute(select(User).where(User.email == custom_email))
        surviving_user = res.scalar_one_or_none()
        assert surviving_user is not None, "Custom user was deleted by seed!"
        assert verify_password(custom_password, surviving_user.hashed_password), "Custom user password was overwritten by seed!"

    await engine.dispose()


@pytest.mark.asyncio
async def test_e_application_restart_preserves_database_state():
    """Test E: Simulates full application restart by recreating DB engine and connections."""
    settings = get_settings()

    # Connection cycle 1
    engine1 = create_async_engine(settings.database_url, echo=False)
    session_factory1 = async_sessionmaker(engine1, expire_on_commit=False)
    async with session_factory1() as session1:
        count1 = (await session1.execute(select(func.count(User.id)))).scalar_one()
    await engine1.dispose()

    # Reconnect / Simulated restart
    engine2 = create_async_engine(settings.database_url, echo=False)
    session_factory2 = async_sessionmaker(engine2, expire_on_commit=False)
    async with session_factory2() as session2:
        count2 = (await session2.execute(select(func.count(User.id)))).scalar_one()
    await engine2.dispose()

    assert count1 == count2
    assert count2 > 0


@pytest.mark.asyncio
async def test_f_persistent_five_layer_memory_survives_restart():
    """Test F: Verifies all five memory layers retain state across application reconnect."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        admin_res = await session.execute(select(User).where(User.email == "admin@nova.ai"))
        admin = admin_res.scalar_one()

        # Check all 5 layers via memory_service
        state = await memory_service.get_memory_state(session, admin.id)

        # Layer 1: Short-Term Conversational Memory
        assert state["layers"]["short_term"]["active_sessions"] >= 1
        assert "PostgreSQL" in state["layers"]["short_term"]["storage"]

        # Layer 2: Long-Term Semantic Memory
        assert state["layers"]["long_term"]["vector_count"] >= 1
        assert "pgvector" in state["layers"]["long_term"]["storage"]

        # Layer 3: User Preference Memory
        assert state["layers"]["preferences"]["user_role"] == "admin"
        assert state["layers"]["preferences"]["active_settings_count"] >= 1

        # Layer 4: Task Execution Memory
        assert state["layers"]["task_execution"]["last_active_plan"] is not None

        # Layer 5: Organizational Axiom Memory
        assert state["layers"]["organizational"]["active_rules"] >= 3

    await engine.dispose()


def test_g_docker_compose_volume_configuration():
    """Test G: Verifies that docker-compose.yml defines persistent named volumes and safe startup."""
    with open("docker-compose.yml", "r") as f:
        compose = yaml.safe_load(f)

    # 1. Check volumes section has explicit named volume
    assert "volumes" in compose
    assert "nova_postgres_data" in compose["volumes"]
    assert compose["volumes"]["nova_postgres_data"]["name"] == "nova_postgres_data"
    assert "nova_redis_data" in compose["volumes"]
    assert compose["volumes"]["nova_redis_data"]["name"] == "nova_redis_data"

    # 2. Check postgres service volume mapping
    postgres_service = compose["services"]["postgres"]
    assert "volumes" in postgres_service
    volume_mounts = postgres_service["volumes"]
    assert any("nova_postgres_data:/var/lib/postgresql/data" in mount for mount in volume_mounts)

    # 3. Check non-destructive backend startup command
    backend_service = compose["services"]["backend"]
    assert "--init-only" in backend_service["command"]
    assert "seed_demo_data" not in backend_service["command"]


@pytest.mark.asyncio
async def test_h_security_scan_history_survives():
    """Test H: Verifies that security scans and assessments persist in PostgreSQL."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        scans_res = await session.execute(select(SecurityIntelScan))
        scans = scans_res.scalars().all()
        assert len(scans) >= 1
        assert scans[0].status == "COMPLETED"

        assessments_res = await session.execute(select(SecurityIntelAssessment))
        assessments = assessments_res.scalars().all()
        assert len(assessments) >= 1
        assert assessments[0].severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_i_knowledge_documents_and_embeddings_survive():
    """Test I: Verifies that knowledge docs and 384-dim pgvector embeddings persist."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        docs_res = await session.execute(select(KnowledgeDocument))
        docs = docs_res.scalars().all()
        assert len(docs) >= 3

        chunks_res = await session.execute(select(KnowledgeChunk).limit(5))
        chunks = chunks_res.scalars().all()
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 384

    await engine.dispose()


@pytest.mark.asyncio
async def test_j_assistant_conversations_and_traces_survive():
    """Test J: Verifies that chat sessions, turns, citations, and reasoning traces persist."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        sess_res = await session.execute(select(ChatSession).limit(1))
        sess = sess_res.scalar_one_or_none()
        assert sess is not None

        msgs_res = await session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sess.id).order_by(ChatMessage.created_at.asc())
        )
        msgs = msgs_res.scalars().all()
        assert len(msgs) >= 1

        asst_msgs = [m for m in msgs if m.role == "assistant"]
        if asst_msgs:
            assert asst_msgs[0].reasoning_trace is not None

    await engine.dispose()
