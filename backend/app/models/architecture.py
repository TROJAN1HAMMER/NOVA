"""
NOVA — Architecture Intelligence Database Models
Models for software components, dependencies, coupling/cohesion metrics,
architecture hotspots, blast radius, and unified traceability.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ArchitectureSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "architecture_snapshots"

    scan_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default Project", index=True)
    target_scope: Mapped[str] = mapped_column(String(512), nullable=False, default=".", index=True)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    total_components: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_dependencies: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    circular_dependency_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_instability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    summary_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    components: Mapped[List["ArchitectureComponent"]] = relationship(
        "ArchitectureComponent", back_populates="snapshot", cascade="all, delete-orphan"
    )
    dependencies: Mapped[List["ArchitectureDependency"]] = relationship(
        "ArchitectureDependency", back_populates="snapshot", cascade="all, delete-orphan"
    )
    traceability_links: Mapped[List["ArchitectureTraceabilityLink"]] = relationship(
        "ArchitectureTraceabilityLink", back_populates="snapshot", cascade="all, delete-orphan"
    )


class ArchitectureComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "architecture_components"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("architecture_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    component_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Coupling Metrics
    fan_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fan_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    afferent_coupling: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    efferent_coupling: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    instability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Cohesion Metrics
    cohesion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cohesion_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_god_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Hotspot Classification
    is_hotspot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    hotspot_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hotspot_reasons: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Blast Radius
    blast_radius_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Metadata / AST attributes
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    snapshot: Mapped["ArchitectureSnapshot"] = relationship("ArchitectureSnapshot", back_populates="components")


class ArchitectureDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "architecture_dependencies"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("architecture_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_circular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    snapshot: Mapped["ArchitectureSnapshot"] = relationship("ArchitectureSnapshot", back_populates="dependencies")


class ArchitectureTraceabilityLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "architecture_traceability_links"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("architecture_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requirement_doc_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    knowledge_chunk_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    graph_entity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    control_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    finding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_scenario_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    snapshot: Mapped["ArchitectureSnapshot"] = relationship("ArchitectureSnapshot", back_populates="traceability_links")
