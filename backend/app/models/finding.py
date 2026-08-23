"""
NOVA — Finding Model
Represents a single detected vulnerability, misconfiguration, secret, or dependency flaw.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.scan_job import ScanJob


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "findings"

    scan_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    sources: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cvss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    brs: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    brs_risk_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    module: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    package: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    package_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cve: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    cwe_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    cwe_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owasp_category: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    owasp_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mitre_technique_ids: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    rbi_clause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pci_clause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    swift_clause: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    ai_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_business_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    scan_job: Mapped[Optional["ScanJob"]] = relationship("ScanJob", back_populates="findings")

    @property
    def compliance(self) -> Optional[dict]:
        if self.rbi_clause or self.pci_clause or self.swift_clause:
            return {
                "rbi_clause": self.rbi_clause,
                "pci_clause": self.pci_clause,
                "swift_clause": self.swift_clause,
            }
        return None
