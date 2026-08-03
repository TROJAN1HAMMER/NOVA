import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage
    from app.models.user import User


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="New Chat")
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_entities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    user: Mapped["User"] = relationship()
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
