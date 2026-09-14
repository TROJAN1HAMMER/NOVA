"""
NOVA Architecture Intelligence — Remediation Impact Engine
Estimates architectural and security blast radius reduction for proposed remediations.
Strictly labels all predicted posture improvements as ESTIMATE.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

from app.services.architecture_intelligence.blast_radius_engine import blast_radius_engine
from app.services.architecture_intelligence.component_discovery import DiscoveredComponent
from app.services.architecture_intelligence.dependency_extractor import DiscoveredDependency

logger = structlog.get_logger(__name__)


@dataclass
class RemediationImpactReport:
    target_component_id: str
    target_component_name: str
    proposed_remediation: str
    metric_label: str  # Strictly "ESTIMATE"
    estimated_posture_delta: float
    affected_components_count: int
    affected_components: List[Dict[str, Any]]
    strengthened_controls: List[Dict[str, Any]]
    mitigated_risk_scenarios: List[Dict[str, Any]]
    remaining_hotspot_status: str
    disclaimer: str
    direct_dependents_count: int = 0
    max_impact_depth: int = 0


class RemediationImpactEngine:
    """Estimates the ripple benefit of remediating a security or architectural flaw."""

    def estimate_remediation_impact(
        self,
        component_id: str,
        proposed_remediation: str,
        components: List[DiscoveredComponent],
        dependencies: List[DiscoveredDependency],
        security_data: Optional[Dict[str, Any]] = None,
    ) -> RemediationImpactReport:
        security_data = security_data or {}
        comp_map = {c.component_id: c for c in components}
        target_comp = comp_map.get(component_id)
        comp_name = target_comp.name if target_comp else component_id

        # Compute blast radius of the component to see what benefits from the fix
        blast = blast_radius_engine.compute_blast_radius(
            target_component_id=component_id,
            components=components,
            dependencies=dependencies,
            security_data=security_data,
        )

        # Estimate posture delta based on mitigated findings and scenarios
        mitigated_scenarios = blast.affected_scenarios
        mitigated_findings = blast.affected_findings

        est_delta = 0.0
        for f in mitigated_findings:
            sev = f.get("severity", "MEDIUM")
            if sev == "CRITICAL":
                est_delta += 8.0
            elif sev == "HIGH":
                est_delta += 4.0
            elif sev == "MEDIUM":
                est_delta += 2.0
            else:
                est_delta += 1.0

        est_delta = min(25.0, round(est_delta, 1))

        strengthened = [
            {
                "control_name": c.get("control_name") or c.get("control_type") or "Security Control",
                "scope": c.get("scope", ""),
                "state": c.get("state", "PASS"),
            }
            for c in blast.affected_controls
        ]

        formatted_scenarios = []
        for sc in mitigated_scenarios[:5]:
            if isinstance(sc, dict):
                formatted_scenarios.append({
                    "scenario_id": sc.get("id") or sc.get("scenario_id", ""),
                    "title": sc.get("title") or sc.get("name") or "Risk Scenario",
                    "severity": sc.get("severity", "MEDIUM"),
                })
            else:
                formatted_scenarios.append({"title": str(sc)})

        return RemediationImpactReport(
            target_component_id=component_id,
            target_component_name=comp_name,
            proposed_remediation=proposed_remediation,
            metric_label="ESTIMATE",
            estimated_posture_delta=est_delta,
            affected_components_count=blast.transitive_dependents_count,
            affected_components=blast.transitive_dependents[:10],
            strengthened_controls=strengthened,
            mitigated_risk_scenarios=formatted_scenarios,
            remaining_hotspot_status="HOTSPOT_RESOLVED" if est_delta >= 8.0 else "HOTSPOT_ATTENUATED",
            disclaimer="ESTIMATE: Modeled architectural improvement based on graph reachability. Not an authoritative posture measurement until confirmed by a fresh scan.",
            direct_dependents_count=blast.direct_dependents_count,
            max_impact_depth=blast.max_impact_depth,
        )


remediation_impact_engine = RemediationImpactEngine()
