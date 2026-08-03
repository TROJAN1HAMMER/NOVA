import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User

settings = get_settings()

DOCUMENT_TYPE_MAX_LENGTH = 16
DOCUMENT_STATUS_MAX_LENGTH = 16


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    document_type: Mapped[str] = mapped_column(String(DOCUMENT_TYPE_MAX_LENGTH), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    document_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    is_latest: Mapped[bool] = mapped_column(nullable=False, default=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(DOCUMENT_STATUS_MAX_LENGTH), nullable=False, default="pending")
    health_status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active, stale, duplicate
    freshness_decay_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    uploaded_by: Mapped[Optional["User"]] = relationship()
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    heading: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    section_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    embedding: Mapped[list[float]] = mapped_column(Vector(settings.knowledge_embedding_dim), nullable=False)

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")


class KnowledgeEntity(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_entities"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KnowledgeRelation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_relations"

    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


SEARCH_ANALYTICS_FEATURE_MAX_LENGTH = 32


class SearchAnalyticsLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_analytics_logs"

    feature: Mapped[str] = mapped_column(String(SEARCH_ANALYTICS_FEATURE_MAX_LENGTH), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fallback_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


FEEDBACK_FEATURE_MAX_LENGTH = 32


class Feedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "feedback_entries"

    feature: Mapped[str] = mapped_column(String(FEEDBACK_FEATURE_MAX_LENGTH), nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
