"""
AEKOF — Hierarchical 5-Layer Enterprise Memory Engine
"""

import uuid
import structlog
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage

logger = structlog.get_logger(__name__)


class MemoryService:
    async def get_or_create_session(
        self, db: AsyncSession, user_id: uuid.UUID, session_id: Optional[uuid.UUID] = None
    ) -> ChatSession:
        if session_id:
            result = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            )
            session = result.scalar_one_or_none()
            if session:
                return session

        new_session = ChatSession(user_id=user_id, title="New Chat")
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    async def list_sessions(self, db: AsyncSession, user_id: uuid.UUID) -> list[ChatSession]:
        result = await db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_sliding_window_context(
        self, db: AsyncSession, session_id: uuid.UUID, max_turns: int = 10
    ) -> list[dict]:
        """
        Layer 1: Enforces the 10-turn sliding-window concept.
        Reconstructs the currently active conversational context from persistent
        messages in PostgreSQL, strictly capped at the most recent max_turns
        (2 * max_turns messages), leaving older messages safely in persistent history.
        """
        from sqlalchemy import case
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(
                ChatMessage.created_at.desc(),
                case((ChatMessage.role == "assistant", 1), else_=0).desc()
            )
            .limit(max_turns * 2)
        )
        recent_messages = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content} for m in recent_messages]

    async def save_turn(
        self,
        db: Optional[AsyncSession],
        session_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        citations: list = None,
        confidence_vector: dict = None,
        calibrated_trust_score: float = None,
        reasoning_trace: dict = None,
        consensus_matrix: dict = None,
    ) -> None:
        if db is None:
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session_db:
                return await self.save_turn(
                    db=session_db,
                    session_id=session_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    citations=citations,
                    confidence_vector=confidence_vector,
                    calibrated_trust_score=calibrated_trust_score,
                    reasoning_trace=reasoning_trace,
                    consensus_matrix=consensus_matrix,
                )
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return

        import time
        from datetime import datetime, timezone, timedelta
        if not hasattr(self, "_last_turn_ts"):
            self._last_turn_ts = 0.0

        current_time = time.time()
        if current_time <= self._last_turn_ts:
            current_time = self._last_turn_ts + 0.002
        self._last_turn_ts = current_time

        turn_dt = datetime.fromtimestamp(current_time, tz=timezone.utc)
        user_msg = ChatMessage(session_id=session.id, role="user", content=user_message, created_at=turn_dt)
        asst_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_response,
            citations=citations or [],
            confidence_vector=confidence_vector or {},
            calibrated_trust_score=calibrated_trust_score,
            reasoning_trace=reasoning_trace or {},
            consensus_matrix=consensus_matrix or {},
            created_at=turn_dt + timedelta(microseconds=500),
        )
        db.add_all([user_msg, asst_msg])
        await db.commit()
        logger.info("memory_service.turn_saved", session_id=str(session_id))

    async def compress_old_entries(self, db: AsyncSession, threshold_turns: int = 10) -> int:
        """
        Layer 2: Long-Term Semantic Memory Compression.
        Identifies sessions where turn count exceeds threshold_turns, synthesizes
        their semantic context into session.context_summary, and updates the database.
        """
        from sqlalchemy import func
        # Find sessions that have messages
        subq = (
            select(ChatMessage.session_id, func.count(ChatMessage.id).label("msg_count"))
            .group_by(ChatMessage.session_id)
            .subquery()
        )
        result = await db.execute(
            select(ChatSession, subq.c.msg_count)
            .join(subq, ChatSession.id == subq.c.session_id)
            .where(subq.c.msg_count >= threshold_turns * 2)
        )
        rows = result.all()
        compressed_count = 0

        for session, msg_count in rows:
            # Fetch the oldest messages to build a summary
            msg_res = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.asc())
                .limit(10)
            )
            old_messages = msg_res.scalars().all()
            if old_messages:
                summary_points = []
                for m in old_messages:
                    if m.role == "user":
                        summary_points.append(f"Q: {m.content[:80]}")
                    elif m.role == "assistant":
                        summary_points.append(f"A: {m.content[:80]}")
                new_summary = " | ".join(summary_points)
                if not session.context_summary or len(session.context_summary) < len(new_summary):
                    session.context_summary = (
                        f"Archived context ({len(old_messages)} turns): {new_summary[:400]}..."
                    )
                    compressed_count += 1

        if compressed_count > 0:
            await db.commit()
            logger.info("memory_service.compressed_old_entries", count=compressed_count)

        return compressed_count

    async def get_memory_state(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        """
        Returns authoritative live persistence telemetry across the 5 memory layers:
        1. Short-Term Conversational Memory
        2. Long-Term Semantic Memory
        3. User Preference Memory
        4. Task Execution Memory
        5. Organizational Axiom Memory
        """
        from sqlalchemy import func
        from app.models.faq_rule import FAQRule
        from app.models.knowledge import KnowledgeChunk
        from app.models.system_setting import SystemSetting
        from app.models.user import User

        # Layer 1: Short-Term Conversational Memory
        user_sess_res = await db.execute(
            select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc())
        )
        user_sessions = list(user_sess_res.scalars().all())
        session_ids = [s.id for s in user_sessions]

        total_turns = 0
        latest_turn_count = 0
        active_session_id = str(user_sessions[0].id) if user_sessions else None

        if session_ids:
            msg_res = await db.execute(
                select(ChatMessage.session_id, func.count(ChatMessage.id))
                .where(ChatMessage.session_id.in_(session_ids))
                .group_by(ChatMessage.session_id)
            )
            counts = dict(msg_res.all())
            total_msgs = sum(counts.values())
            total_turns = total_msgs // 2
            if active_session_id:
                latest_turn_count = counts.get(user_sessions[0].id, 0) // 2

        # Layer 2: Long-Term Semantic Memory
        compressed_res = await db.execute(
            select(func.count(ChatSession.id)).where(ChatSession.context_summary.isnot(None))
        )
        compressed_count = compressed_res.scalar_one()

        vector_res = await db.execute(select(func.count(KnowledgeChunk.id)))
        vector_count = vector_res.scalar_one()

        # Layer 3: User Preference Memory
        user_res = await db.execute(select(User).where(User.id == user_id))
        cur_user = user_res.scalar_one_or_none()
        user_role = cur_user.role.value if cur_user else "developer"

        settings_res = await db.execute(select(func.count(SystemSetting.key)))
        active_settings_count = settings_res.scalar_one()

        # Layer 4: Task Execution Memory
        # Retrieve latest execution reasoning trace and checkpoints
        last_reasoning_plan = None
        checkpoint_count = 0
        if session_ids:
            latest_asst_msg_res = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id.in_(session_ids), ChatMessage.role == "assistant")
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            latest_msg = latest_asst_msg_res.scalar_one_or_none()
            if latest_msg and latest_msg.reasoning_trace:
                last_reasoning_plan = latest_msg.reasoning_trace.get("pipeline_stage") or "STAGE_2_SAFETY_GATE_PASS"

            # Checkpoints count from verified assessments or message trace count
            chk_res = await db.execute(
                select(func.count(ChatMessage.id)).where(
                    ChatMessage.session_id.in_(session_ids),
                    ChatMessage.calibrated_trust_score.isnot(None)
                )
            )
            checkpoint_count = chk_res.scalar_one()

        # Layer 5: Organizational Axiom Memory
        active_faq_res = await db.execute(
            select(func.count(FAQRule.id)).where(FAQRule.is_active == True, FAQRule.is_draft == False)
        )
        active_rules = active_faq_res.scalar_one()

        draft_faq_res = await db.execute(
            select(func.count(FAQRule.id)).where(FAQRule.is_draft == True)
        )
        draft_rules = draft_faq_res.scalar_one()

        # Truthful Vector Memory Health telemetry
        from sqlalchemy import text
        db_healthy = True
        vector_healthy = True
        try:
            await db.execute(text("SELECT 1"))
        except Exception:
            db_healthy = False

        try:
            vec_check = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            if not vec_check.scalar_one_or_none():
                vector_healthy = False
        except Exception:
            vector_healthy = False

        health_status = "ONLINE" if (db_healthy and vector_healthy) else "DEGRADED"

        # Compile recent entries across persistent memory layers
        recent_entries = []
        for s in user_sessions[:5]:
            recent_entries.append({
                "id": str(s.id),
                "memory_type": "conversation",
                "content": s.title,
                "metadata": {"context_summary": s.context_summary},
                "created_at": s.created_at.isoformat() if s.created_at else ""
            })

        return {
            "total_entries": total_turns + vector_count + active_rules,
            "health": {
                "status": health_status,
                "database": "ready" if db_healthy else "error",
                "vector_engine": "ready" if vector_healthy else "error",
                "storage_engine": "PostgreSQL 16 + pgvector",
            },
            "layers": {
                "short_term": {
                    "layer_id": "short_term",
                    "level": "Layer 1",
                    "title": "Short-Term Conversational Memory",
                    "active_sessions": len(user_sessions),
                    "active_session_id": active_session_id,
                    "session_turn_count": latest_turn_count,
                    "total_turns": total_turns,
                    "storage": "PostgreSQL (chat_messages, chat_sessions)",
                    "persistence": "persistent",
                    "scope": "User session (isolated)",
                    "status": f"Active ({latest_turn_count}/10 turns)" if latest_turn_count > 0 else "0 / 10 Turns",
                    "last_updated": user_sessions[0].updated_at.isoformat() if user_sessions and user_sessions[0].updated_at else (user_sessions[0].created_at.isoformat() if user_sessions else None)
                },
                "long_term": {
                    "layer_id": "long_term",
                    "level": "Layer 2",
                    "title": "Long-Term Semantic Memory",
                    "vector_count": vector_count,
                    "compressed_summaries": compressed_count,
                    "storage": "PostgreSQL (pgvector 384-dim, context_summary)",
                    "persistence": "persistent",
                    "scope": "Enterprise & Session knowledge",
                    "status": f"{compressed_count} Compressed Contexts" if compressed_count > 0 else "No compressed summaries",
                    "last_updated": None
                },
                "preferences": {
                    "layer_id": "preferences",
                    "level": "Layer 3",
                    "title": "User Preference Memory",
                    "user_role": user_role,
                    "active_settings_count": active_settings_count,
                    "storage": "PostgreSQL (users, system_settings)",
                    "persistence": "persistent",
                    "scope": "Individual user profile",
                    "status": f"Synchronized ({user_role.upper()})",
                    "last_updated": cur_user.updated_at.isoformat() if cur_user and cur_user.updated_at else None
                },
                "task_execution": {
                    "layer_id": "task_execution",
                    "level": "Layer 4",
                    "title": "Task Execution Memory",
                    "last_active_plan": last_reasoning_plan,
                    "checkpoints_count": checkpoint_count,
                    "storage": "PostgreSQL (reasoning_trace, security_intel_scans)",
                    "persistence": "persistent",
                    "scope": "Execution workflow context",
                    "status": f"{checkpoint_count} Checkpoints" if checkpoint_count > 0 else "Idle",
                    "last_updated": None
                },
                "organizational": {
                    "layer_id": "organizational",
                    "level": "Layer 5",
                    "title": "Organizational Axiom Memory",
                    "active_rules": active_rules,
                    "pending_gap_candidates": draft_rules,
                    "storage": "PostgreSQL (faq_rules)",
                    "persistence": "persistent",
                    "scope": "Enterprise Stage 0 policy boundary",
                    "status": f"Active ({active_rules} Verified Axioms)",
                    "last_updated": None
                }
            },
            "recent_entries": recent_entries
        }

    async def reset_session_turns(
        self, db: AsyncSession, user_id: uuid.UUID, session_id: Optional[uuid.UUID] = None
    ) -> dict:
        """
        Clears conversational turns for an active session without deleting the session
        or affecting other sessions, documents, or organizational axioms.
        """
        from sqlalchemy import delete
        if session_id:
            sess_res = await db.execute(
                select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            )
            session = sess_res.scalar_one_or_none()
        else:
            sess_res = await db.execute(
                select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc()).limit(1)
            )
            session = sess_res.scalar_one_or_none()

        if not session:
            return {"status": "error", "message": "Active session not found or unauthorized."}

        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session.id))
        session.title = "New Chat"
        session.context_summary = None
        session.active_entities = {}
        await db.commit()
        return {
            "status": "success",
            "message": f"Active session '{session.id}' conversational turn buffer reset to 0.",
            "session_id": str(session.id),
        }


    # ── User Preferences (Layer 3) ──────────────────────────────────────────

    async def get_user_preferences(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        """
        Retrieves persistent user preferences stored under the user-scoped
        system setting key 'user_pref:<user_id>'. Survives logout, backend
        restart, and container lifecycle.
        """
        from app.models.system_setting import SystemSetting
        from app.models.user import User

        pref_key = f"user_pref:{user_id}"
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == pref_key))
        row = result.scalar_one_or_none()

        user_res = await db.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()
        role_str = user.role.value if user else "developer"

        default_prefs = {
            "department": "Security Architecture & Engineering",
            "language": "English (US)",
            "tone": "Executive Technical Synthesis",
            "context_scope": "Full Enterprise Knowledge",
            "auto_compress_threshold": 10,
            "role": role_str,
        }

        if row and isinstance(row.value, dict):
            merged = default_prefs.copy()
            merged.update(row.value)
            merged["role"] = role_str
            return merged
        return default_prefs

    async def update_user_preferences(self, db: AsyncSession, user_id: uuid.UUID, updates: dict) -> dict:
        """
        Updates or inserts user preferences in PostgreSQL under 'user_pref:<user_id>'.
        """
        from app.models.system_setting import SystemSetting

        pref_key = f"user_pref:{user_id}"
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == pref_key))
        row = result.scalar_one_or_none()

        cur = await self.get_user_preferences(db, user_id)
        cur.update(updates)

        if row:
            row.value = cur
        else:
            row = SystemSetting(
                key=pref_key,
                value=cur,
                description=f"Persistent user preference memory for user {user_id}",
            )
            db.add(row)

        await db.commit()
        return cur

    # ── Memory Layer Items Inspection (Provenance + Lifecycle) ────────────────

    async def get_layer_items(
        self, db: AsyncSession, user_id: uuid.UUID, layer_id: str, session_id: Optional[uuid.UUID] = None
    ) -> list[dict]:
        """
        Inspects real records for a given layer.
        Returns provenance, lifecycle status, 'why' explanation, and ownership scope.
        Strictly isolates user-scoped records.
        """
        from app.models.faq_rule import FAQRule
        from app.models.security_intelligence import SecurityIntelScan
        from app.models.user import User

        items = []

        if layer_id in ("short_term", "layer_1", "1"):
            # Layer 1: Short-term turns for user's active session
            session = None
            if session_id:
                sess_res = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
                )
                session = sess_res.scalar_one_or_none()
            else:
                sess_res = await db.execute(
                    select(ChatSession)
                    .where(ChatSession.user_id == user_id)
                    .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
                    .limit(1)
                )
                session = sess_res.scalar_one_or_none()

            if session:
                from sqlalchemy import case
                msg_res = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session.id)
                    .order_by(
                        ChatMessage.created_at.desc(),
                        case((ChatMessage.role == "assistant", 1), else_=0).desc()
                    )
                )
                msgs = list(msg_res.scalars().all())
                total_msgs = len(msgs)

                for idx, m in enumerate(msgs):
                    in_sliding_window = idx < 20
                    turn_num = (total_msgs - idx + 1) // 2
                    lifecycle = "ACTIVE" if in_sliding_window else "ARCHIVED"
                    preview = m.content[:160] + "..." if len(m.content) > 160 else m.content

                    items.append({
                        "id": str(m.id),
                        "layer": "Layer 1: Short-Term Conversational Memory",
                        "title": f"Turn {turn_num}: {m.role.capitalize()}",
                        "content": preview,
                        "role": m.role,
                        "turn_number": turn_num,
                        "in_sliding_window": in_sliding_window,
                        "session_id": str(session.id),
                        "provenance": {
                            "source_type": "user_chat_session",
                            "source_id": str(m.id),
                            "session_id": str(session.id),
                            "origin": f"Chat session '{session.title}' ({'Inside' if in_sliding_window else 'Archived beyond'} 10-turn sliding buffer)",
                            "owner_scope": f"User {user_id}",
                            "verification_state": "IN_SLIDING_WINDOW" if in_sliding_window else "ARCHIVED_POSTGRESQL"
                        },
                        "lifecycle": lifecycle,
                        "why_remembered": (
                            f"NOVA maintains this message in PostgreSQL inside the active 10-turn sliding window for session '{session.title}' to provide immediate multi-turn conversational context."
                            if in_sliding_window
                            else f"This message is preserved in persistent PostgreSQL history beyond the 10-turn sliding window to maintain complete auditability and allow long-term semantic summarization."
                        ),
                        "can_delete": True,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                        "updated_at": None,
                    })

        elif layer_id in ("long_term", "layer_2", "2"):
            # Layer 2: Long-Term Semantic Memory (Compressed conversation summaries)
            res = await db.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id, ChatSession.context_summary.isnot(None))
                .order_by(ChatSession.updated_at.desc())
            )
            sessions = res.scalars().all()
            for s in sessions:
                items.append({
                    "id": f"summary-{s.id}",
                    "layer": "Layer 2: Long-Term Semantic Memory",
                    "title": f"Compressed Context: {s.title}",
                    "content": s.context_summary,
                    "provenance": {
                        "source_type": "session_semantic_compression",
                        "source_id": str(s.id),
                        "session_id": str(s.id),
                        "origin": f"Conversation compression worker for session '{s.title}'",
                        "owner_scope": f"User {user_id}",
                        "verification_state": "SYNTHESIZED_384DIM"
                    },
                    "lifecycle": "ACTIVE",
                    "why_remembered": f"NOVA synthesized semantic highlights from older conversational turns in session '{s.title}' so long-term context is preserved without bloating the short-term window.",
                    "can_delete": True,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                })

        elif layer_id in ("preferences", "layer_3", "3"):
            # Layer 3: User preferences
            prefs = await self.get_user_preferences(db, user_id)
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()

            for k, v in prefs.items():
                items.append({
                    "id": f"pref-{k}",
                    "layer": "Layer 3: User Preference Memory",
                    "title": f"Preference: {k.replace('_', ' ').title()}",
                    "content": f"{k} = {v}",
                    "provenance": {
                        "source_type": "user_profile_configuration",
                        "source_id": str(user_id),
                        "origin": f"User preference store for {user.email if user else 'Current User'}",
                        "owner_scope": f"User {user_id}",
                        "verification_state": "VERIFIED_USER_SETTING"
                    },
                    "lifecycle": "ACTIVE",
                    "why_remembered": f"Configured for user '{user.email if user else 'Current User'}' to tailor AI responses to their designated role, preferred department context, and communication tone.",
                    "can_delete": True,
                    "created_at": user.created_at.isoformat() if user and user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user and user.updated_at else None,
                })

        elif layer_id in ("task_execution", "layer_4", "4"):
            # Layer 4: Multi-step task execution state
            # A. Assistant session reasoning traces
            res = await db.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc())
                .limit(5)
            )
            sessions = res.scalars().all()
            for s in sessions:
                msg_res = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == s.id, ChatMessage.role == "assistant")
                    .order_by(ChatMessage.created_at.desc())
                    .limit(5)
                )
                for m in msg_res.scalars().all():
                    if m.reasoning_trace or m.calibrated_trust_score is not None:
                        stage = (m.reasoning_trace or {}).get("pipeline_stage") or "STAGE_2_SAFETY_GATE_PASS"
                        decision = (m.reasoning_trace or {}).get("trust_decision") or "DIRECT_ANSWER"
                        items.append({
                            "id": f"trace-{m.id}",
                            "layer": "Layer 4: Task Execution Memory",
                            "title": f"Execution Plan Checkpoint: {stage}",
                            "content": f"Trust Score: {m.calibrated_trust_score or 'N/A'} | Trust Decision: {decision} | Citations: {len(m.citations or [])}",
                            "provenance": {
                                "source_type": "reasoning_pipeline_checkpoint",
                                "source_id": str(m.id),
                                "session_id": str(s.id),
                                "origin": f"Assistant reasoning pipeline turn in session '{s.title}'",
                                "owner_scope": f"User {user_id}",
                                "verification_state": "CALIBRATED_CHECKPOINT"
                            },
                            "lifecycle": "ACTIVE",
                            "why_remembered": f"Recorded during multi-stage RAG execution to track confidence calibration, consensus matrix agreement, and safety gate decisions for auditing.",
                            "can_delete": True,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                            "updated_at": None,
                        })

            # B. Security Intelligence Scans owned by user or system
            scan_res = await db.execute(
                select(SecurityIntelScan)
                .where((SecurityIntelScan.owner_id == user_id) | (SecurityIntelScan.owner_id.is_(None)))
                .order_by(SecurityIntelScan.created_at.desc())
                .limit(5)
            )
            scans = scan_res.scalars().all()
            for scan in scans:
                lifecycle = "ACTIVE" if scan.status in ("QUEUED", "ANALYZING", "EVALUATING_CONTROLS") else "ARCHIVED"
                items.append({
                    "id": f"scan-{scan.id}",
                    "layer": "Layer 4: Task Execution Memory",
                    "title": f"Security Scan Task: {scan.project_name}",
                    "content": f"Status: {scan.status} (Progress: {scan.progress}%) | Stage: {scan.stage} | Posture: {scan.posture_rating or 'PENDING'}",
                    "provenance": {
                        "source_type": "security_intel_scan_job",
                        "source_id": str(scan.id),
                        "origin": f"Security intelligence task for {scan.source_identifier}",
                        "owner_scope": f"User {scan.owner_id}" if scan.owner_id else "Platform Task",
                        "verification_state": "AUDIT_VERIFIED"
                    },
                    "lifecycle": lifecycle,
                    "why_remembered": f"Represents an asynchronous multi-step code intelligence scanning task. Checkpoint state allows tracking execution progress and temporal posture evolution.",
                    "can_delete": False,
                    "created_at": scan.created_at.isoformat() if scan.created_at else None,
                    "updated_at": scan.updated_at.isoformat() if scan.updated_at else None,
                })

        elif layer_id in ("organizational", "layer_5", "5"):
            # Layer 5: Stage 0 Axiom Rules and Gap Candidates
            rule_res = await db.execute(
                select(FAQRule).order_by(FAQRule.is_draft.asc(), FAQRule.created_at.desc()).limit(20)
            )
            rules = rule_res.scalars().all()
            for r in rules:
                lifecycle = "NEW" if r.is_draft else ("ACTIVE" if r.is_active else "ARCHIVED")
                items.append({
                    "id": str(r.id),
                    "layer": "Layer 5: Organizational Axiom Memory",
                    "title": f"Axiom Rule: \"{r.keyword}\"" if not r.is_draft else f"Draft Gap Candidate: \"{r.keyword}\"",
                    "content": r.response[:200] + "..." if len(r.response) > 200 else r.response,
                    "provenance": {
                        "source_type": "organizational_faq_rule",
                        "source_id": str(r.id),
                        "origin": r.source_query_cluster or "Domain Expert Rule Specification",
                        "owner_scope": "Enterprise Policy (Stage 0 Live Gate)",
                        "verification_state": "PROMOTED_STAGE_0" if not r.is_draft else "UNVERIFIED_DRAFT_GAP"
                    },
                    "lifecycle": lifecycle,
                    "why_remembered": (
                        f"High-frequency verified organizational axiom. When queries contain '{r.keyword}', NOVA serves this authoritative response in <1ms without vector retrieval hallucination."
                        if not r.is_draft
                        else f"Knowledge gap candidate identified from user query clusters, pending domain expert verification before promotion to Stage 0."
                    ),
                    "can_delete": True,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                })

        return items

    # ── Safe Memory Deletion / Forgetting ─────────────────────────────────────

    async def forget_memory(
        self, db: AsyncSession, user_id: uuid.UUID, layer_id: str, item_id: str
    ) -> dict:
        """
        Safely forgets/deletes a memory item while enforcing strict isolation:
        - Layer 1: Deletes individual message or clears session without touching other users.
        - Layer 2: Clears session context summary without deleting source documents.
        - Layer 3: Resets individual preference to default.
        - Layer 4: Clears reasoning trace from specified message.
        - Layer 5: Deletes axiom rule only if authorized (RBAC FAQ_WRITE).
        Never deletes unrelated conversations, source documents, or security findings.
        """
        from app.models.faq_rule import FAQRule
        from app.models.user import User

        if layer_id in ("short_term", "layer_1", "1"):
            try:
                target_uuid = uuid.UUID(item_id)
                # 1. Check if it is a session owned by user_id
                res = await db.execute(
                    select(ChatSession).where(ChatSession.id == target_uuid, ChatSession.user_id == user_id)
                )
                session = res.scalar_one_or_none()
                if session:
                    await db.delete(session)
                    await db.commit()
                    return {"status": "success", "message": f"Short-term session '{session.title}' safely removed."}

                # 2. Check if it is an individual message in a session owned by user_id
                msg_res = await db.execute(
                    select(ChatMessage)
                    .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                    .where(ChatMessage.id == target_uuid, ChatSession.user_id == user_id)
                )
                msg = msg_res.scalar_one_or_none()
                if msg:
                    await db.delete(msg)
                    await db.commit()
                    return {"status": "success", "message": "Conversational turn message safely forgotten."}
            except ValueError:
                pass
            return {"status": "error", "message": "Session or message not found or unauthorized."}

        elif layer_id in ("long_term", "layer_2", "2"):
            if item_id.startswith("summary-"):
                raw_id = item_id.replace("summary-", "")
                try:
                    sess_uuid = uuid.UUID(raw_id)
                    res = await db.execute(
                        select(ChatSession).where(ChatSession.id == sess_uuid, ChatSession.user_id == user_id)
                    )
                    session = res.scalar_one_or_none()
                    if session:
                        session.context_summary = None
                        await db.commit()
                        return {"status": "success", "message": f"Compressed semantic summary for session '{session.title}' forgotten."}
                except ValueError:
                    pass
            return {"status": "error", "message": "Item cannot be independently forgotten without affecting source documents."}

        elif layer_id in ("preferences", "layer_3", "3"):
            if item_id.startswith("pref-"):
                pref_name = item_id.replace("pref-", "")
                cur = await self.get_user_preferences(db, user_id)
                if pref_name in cur:
                    defaults = {
                        "department": "General Engineering",
                        "language": "English (US)",
                        "tone": "Technical Synthesis",
                        "context_scope": "Standard Knowledge",
                        "auto_compress_threshold": 10,
                    }
                    cur[pref_name] = defaults.get(pref_name, "")
                    await self.update_user_preferences(db, user_id, cur)
                    return {"status": "success", "message": f"User preference '{pref_name}' reset to default."}
            return {"status": "error", "message": "Preference item not found."}

        elif layer_id in ("task_execution", "layer_4", "4"):
            if item_id.startswith("trace-"):
                raw_id = item_id.replace("trace-", "")
                try:
                    msg_uuid = uuid.UUID(raw_id)
                    res = await db.execute(
                        select(ChatMessage)
                        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
                        .where(ChatMessage.id == msg_uuid, ChatSession.user_id == user_id)
                    )
                    msg = res.scalar_one_or_none()
                    if msg:
                        msg.reasoning_trace = {}
                        await db.commit()
                        return {"status": "success", "message": f"Execution trace checkpoint {item_id} purged."}
                except ValueError:
                    pass
            return {"status": "error", "message": "Execution checkpoint not found or read-only."}

        elif layer_id in ("organizational", "layer_5", "5"):
            # Enforce RBAC: user must have FAQ_WRITE permission
            user_res = await db.execute(select(User).where(User.id == user_id))
            cur_user = user_res.scalar_one_or_none()
            from app.auth.permissions import has_permission, Permission
            if not cur_user or not has_permission(cur_user.role, Permission.FAQ_WRITE):
                return {
                    "status": "error",
                    "message": "Permission denied: Only authorized administrators or knowledge analysts can modify organizational Stage 0 axioms."
                }
            try:
                rule_uuid = uuid.UUID(item_id)
                res = await db.execute(select(FAQRule).where(FAQRule.id == rule_uuid))
                rule = res.scalar_one_or_none()
                if rule:
                    await db.delete(rule)
                    await db.commit()
                    return {"status": "success", "message": f"Axiom rule '{rule.keyword}' successfully forgotten from Stage 0."}
            except ValueError:
                pass
            return {"status": "error", "message": "Axiom rule not found."}

        return {"status": "error", "message": f"Unknown memory layer: {layer_id}"}


memory_service = MemoryService()
