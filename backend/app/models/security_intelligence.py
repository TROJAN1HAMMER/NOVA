"""
NOVA — Independent Security Intelligence Database Models
Asset-centric, Observation-centric, Context-aware Database Entities
Completely isolated from legacy scanner Finding / ScanJob models.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SecurityIntelAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_intel_assets"

    asset_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # REPOSITORY, APPLICATION, SERVICE, API, ENDPOINT, DATABASE, MODULE
    criticality: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    observations: Mapped[List["SecurityIntelObservation"]] = relationship("SecurityIntelObservation", back_populates="asset", cascade="all, delete-orphan")
    controls: Mapped[List["SecurityIntelControl"]] = relationship("SecurityIntelControl", back_populates="asset", cascade="all, delete-orphan")
    scenarios: Mapped[List["SecurityIntelRiskScenario"]] = relationship("SecurityIntelRiskScenario", back_populates="asset", cascade="all, delete-orphan")
    assessments: Mapped[List["SecurityIntelAssessment"]] = relationship("SecurityIntelAssessment", back_populates="asset", cascade="all, delete-orphan")


class SecurityIntelObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_intel_observations"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_intel_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # PUBLIC_ENDPOINT, USER_CONTROLLED_INPUT, DATABASE_ACCESS, SECRET_USAGE, etc.
    location: Mapped[str] = mapped_column(String(1024), nullable=False)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    evidence_span: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.90)
    provenance: Mapped[str] = mapped_column(String(128), nullable=False, default="code_ast_fact")

    asset: Mapped["SecurityIntelAsset"] = relationship("SecurityIntelAsset", back_populates="observations")


class SecurityIntelControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_intel_controls"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_intel_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    control_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # AUTHENTICATION, AUTHORIZATION, INPUT_VALIDATION, ENCRYPTION, RATE_LIMITING
    scope: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")  # PRESENT, ABSENT, PARTIAL, BYPASSED, UNKNOWN
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    asset: Mapped["SecurityIntelAsset"] = relationship("SecurityIntelAsset", back_populates="controls")


class SecurityIntelRiskScenario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_intel_risk_scenarios"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_intel_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # SQL_INJECTION_RISK, PRIVILEGE_ESCALATION_RISK, DATA_LEAK_RISK
    trust_boundary_crossed: Mapped[str] = mapped_column(String(128), nullable=False)  # INTERNET -> DATABASE
    attack_path: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    exposure_signal: Mapped[str] = mapped_column(String(255), nullable=False)
    control_status: Mapped[str] = mapped_column(String(255), nullable=False)
    potential_impact: Mapped[str] = mapped_column(Text, nullable=False)
    verification_state: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE")  # CANDIDATE, SUPPORTED, VERIFIED, INCONCLUSIVE, DISMISSED

    asset: Mapped["SecurityIntelAsset"] = relationship("SecurityIntelAsset", back_populates="scenarios")


class SecurityIntelAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "security_intel_assessments"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("security_intel_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    risk_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.90)
    affected_scope: Mapped[str] = mapped_column(String(512), nullable=False)
    evidence_chain: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    attack_path: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    controls_evaluated: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")  # OPEN, VERIFIED_FIXED, DISMISSED
    commit_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    asset: Mapped["SecurityIntelAsset"] = relationship("SecurityIntelAsset", back_populates="assessments")
