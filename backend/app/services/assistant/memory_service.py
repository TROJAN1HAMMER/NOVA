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

    async def save_turn(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_message: str,
        assistant_response: str,
        citations: list = None,
        confidence_vector: dict = None,
        calibrated_trust_score: float = None,
        reasoning_trace: dict = None,
        consensus_matrix: dict = None,
    ) -> None:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            return

        # Auto-update session title from first user query
        if session.title == "New Chat":
            session.title = user_message[:30] + ("..." if len(user_message) > 30 else "")

        user_msg = ChatMessage(session_id=session.id, role="user", content=user_message)
        asst_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_response,
            citations=citations or [],
            confidence_vector=confidence_vector or {},
            calibrated_trust_score=calibrated_trust_score,
            reasoning_trace=reasoning_trace or {},
            consensus_matrix=consensus_matrix or {},
        )
        db.add_all([user_msg, asst_msg])
        await db.commit()
        logger.info("memory_service.turn_saved", session_id=str(session_id))


memory_service = MemoryService()
