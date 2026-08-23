"""
NOVA — ScanResult Model
Stores the computed outcome of a scan job: BRS score, attack surface exposure, summary metrics, and compliance snapshot.
"""

import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.scan_job import ScanJob


class ScanResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_results"

    scan_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    total_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brs_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    brs_risk_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    attack_surface_exposure_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attack_surface_exposure_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    summary: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    compliance_summary: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationship
    scan_job: Mapped["ScanJob"] = relationship("ScanJob", back_populates="result")
