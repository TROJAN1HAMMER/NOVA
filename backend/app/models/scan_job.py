"""
NOVA — ScanJob Model
Represents a queued, running, or completed security scanning job.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ScanJobPriority, ScanJobStatus

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.repository import Repository
    from app.models.scan_result import ScanResult
    from app.models.user import User


class ScanJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_jobs"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[ScanJobStatus] = mapped_column(
        Enum(
            ScanJobStatus,
            name="scan_job_status",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ScanJobStatus.QUEUED,
        index=True,
    )
    priority: Mapped[ScanJobPriority] = mapped_column(
        Enum(
            ScanJobPriority,
            name="scan_job_priority",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ScanJobPriority.NORMAL,
        index=True,
    )

    ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)

    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="scan_jobs")
    result: Mapped[Optional["ScanResult"]] = relationship(
        "ScanResult", back_populates="scan_job", uselist=False, cascade="all, delete-orphan"
    )
    findings: Mapped[List["Finding"]] = relationship(
        "Finding", back_populates="scan_job", cascade="all, delete-orphan"
    )
