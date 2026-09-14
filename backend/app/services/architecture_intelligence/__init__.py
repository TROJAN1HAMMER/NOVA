"""
NOVA Architecture Intelligence Subsystem
Provides static-only component discovery, dependency graph extraction,
coupling & cohesion metrics, circular dependency analysis, architecture hotspots,
blast radius, unified traceability, and architecture drift tracking.
"""

from app.services.architecture_intelligence.architecture_orchestrator import (
    architecture_orchestrator,
    ArchitectureIntelligenceOrchestrator,
)
from app.services.architecture_intelligence.component_discovery import (
    component_discovery_service,
    DiscoveredComponent,
)
from app.services.architecture_intelligence.dependency_extractor import (
    dependency_extractor_service,
    DiscoveredDependency,
)
from app.services.architecture_intelligence.metrics_engine import (
    architecture_metrics_engine,
    ComponentMetrics,
    SystemArchitectureMetrics,
)
from app.services.architecture_intelligence.hotspot_analyzer import (
    hotspot_analyzer_service,
    ArchitectureHotspot,
)
from app.services.architecture_intelligence.blast_radius_engine import (
    blast_radius_engine,
    BlastRadiusReport,
)
from app.services.architecture_intelligence.traceability_engine import (
    traceability_engine,
    TraceabilityChain,
)
from app.services.architecture_intelligence.drift_engine import (
    architecture_drift_engine,
    ArchitectureDriftReport,
)
from app.services.architecture_intelligence.change_impact_engine import (
    change_impact_engine,
    ChangeImpactReport,
)
from app.services.architecture_intelligence.remediation_impact_engine import (
    remediation_impact_engine,
    RemediationImpactReport,
)

__all__ = [
    "architecture_orchestrator",
    "ArchitectureIntelligenceOrchestrator",
    "component_discovery_service",
    "DiscoveredComponent",
    "dependency_extractor_service",
    "DiscoveredDependency",
    "architecture_metrics_engine",
    "ComponentMetrics",
    "SystemArchitectureMetrics",
    "hotspot_analyzer_service",
    "ArchitectureHotspot",
    "blast_radius_engine",
    "BlastRadiusReport",
    "traceability_engine",
    "TraceabilityChain",
    "architecture_drift_engine",
    "ArchitectureDriftReport",
    "change_impact_engine",
    "ChangeImpactReport",
    "remediation_impact_engine",
    "RemediationImpactReport",
]
