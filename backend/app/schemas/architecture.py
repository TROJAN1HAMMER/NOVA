"""
NOVA Architecture Intelligence — Pydantic API Schemas
Defines request and response shapes for architecture discovery, coupling/cohesion,
hotspots, blast radius, drift tracking, and unified traceability.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ArchitectureAnalyzeRequest(BaseModel):
    target_path: str = Field(default=".", description="Target workspace or repository path")
    project_name: Optional[str] = Field(default="NOVA Core", description="Project or application name")
    force_refresh: bool = Field(default=False, description="Force fresh static analysis bypass cache")
    scan_id: Optional[str] = Field(default=None, description="Optional scan ID to refresh or re-scan")


class ComponentSummary(BaseModel):
    component_id: str
    name: str
    component_type: str
    file_path: str
    line_number: Optional[int] = None
    language: str = "generic"
    fan_in: int = 0
    fan_out: int = 0
    ca: int = 0
    ce: int = 0
    instability: Optional[float] = None
    lcom4: Optional[int] = None
    cohesion_metric_type: str = "UNAVAILABLE"
    is_god_candidate: bool = False
    in_circular_dependency: bool = False
    circular_cycles: List[List[str]] = Field(default_factory=list)
    dependency_depth: int = 0
    attributes: Optional[Dict[str, Any]] = None


class DependencyEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    evidence: Optional[str] = None
    is_circular: bool = False


class HotspotItem(BaseModel):
    component_id: str
    component_name: str
    component_type: str
    file_path: str
    hotspot_score: float
    hotspot_level: str
    reasons: List[str]
    constituent_scores: Dict[str, float]
    raw_metrics: Dict[str, Any]
    correlated_security: Dict[str, Any]


class TraceabilityItem(BaseModel):
    chain_id: str
    component_id: str
    component_name: str
    file_path: str
    line_number: Optional[int] = None
    requirement_doc_name: Optional[str] = None
    graph_entity_name: Optional[str] = None
    control_name: Optional[str] = None
    control_state: Optional[str] = None
    finding_title: Optional[str] = None
    finding_severity: Optional[str] = None
    risk_scenario_title: Optional[str] = None
    provenance: Dict[str, Any]


class ArchitectureOverviewResponse(BaseModel):
    snapshot_id: str
    scan_id: Optional[str] = None
    project_name: str
    target_scope: str
    summary: Dict[str, Any]
    cycles_detected: List[List[str]]
    components: List[ComponentSummary]
    dependencies: List[DependencyEdge]
    hotspots: List[HotspotItem]
    traceability: List[TraceabilityItem]
    metrics: Dict[str, Any]


class BlastRadiusResponse(BaseModel):
    target_component_id: str
    target_component_name: str
    direct_dependents_count: int
    direct_dependents: List[Dict[str, Any]]
    transitive_dependents_count: int
    transitive_dependents: List[Dict[str, Any]]
    max_impact_depth: int
    affected_endpoints: List[Dict[str, Any]]
    affected_services: List[Dict[str, Any]]
    affected_findings: List[Dict[str, Any]]
    affected_controls: List[Dict[str, Any]]
    affected_scenarios: List[Dict[str, Any]]
    affected_assets: List[Dict[str, Any]]
    risk_level: str


class ArchitectureDriftResponse(BaseModel):
    baseline_available: bool
    message: str
    status: str
    previous_snapshot_id: Optional[str] = None
    current_snapshot_id: Optional[str] = None
    added_dependencies: List[Dict[str, Any]]
    removed_dependencies: List[Dict[str, Any]]
    new_circular_cycles: List[List[str]]
    resolved_circular_cycles: List[List[str]]
    increased_coupling_components: List[Dict[str, Any]]
    new_god_candidates: List[str]
    boundary_violations: List[Dict[str, Any]]
    summary: Dict[str, Any]


class RemediationImpactRequest(BaseModel):
    component_id: str = Field(..., description="Target component ID to simulate fixing")
    proposed_remediation: str = Field(..., description="Description of proposed architectural or security fix")


class RemediationImpactResponse(BaseModel):
    target_component_id: str
    target_component_name: str
    proposed_remediation: str
    metric_label: str = "ESTIMATE"
    estimated_posture_delta: float
    affected_components_count: int
    affected_components: List[Dict[str, Any]]
    strengthened_controls: List[Dict[str, Any]]
    mitigated_risk_scenarios: List[Dict[str, Any]]
    remaining_hotspot_status: str
    disclaimer: str
