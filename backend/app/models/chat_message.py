import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence_vector: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    calibrated_trust_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reasoning_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    consensus_matrix: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
