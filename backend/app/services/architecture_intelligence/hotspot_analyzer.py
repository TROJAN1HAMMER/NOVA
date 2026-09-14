"""
NOVA Architecture Intelligence — Hotspot Analyzer
Evidence-based, deterministic classification of architecture hotspots combining
measured coupling, cohesion, circular dependencies, and correlated security findings/controls/risks.
Fully transparent formula, stored constituent metrics, and explicit threshold explanations.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

from app.services.architecture_intelligence.component_discovery import DiscoveredComponent
from app.services.architecture_intelligence.metrics_engine import ComponentMetrics

logger = structlog.get_logger(__name__)

HOTSPOT_CLASSIFICATION_THRESHOLD = 3.0


@dataclass
class ArchitectureHotspot:
    component_id: str
    component_name: str
    component_type: str
    file_path: str
    hotspot_score: float
    hotspot_level: str  # CRITICAL, HIGH, MEDIUM
    reasons: List[str]
    constituent_scores: Dict[str, float]
    raw_metrics: Dict[str, Any]
    correlated_security: Dict[str, Any] = field(default_factory=dict)


class HotspotAnalyzerService:
    """Analyzes components to detect evidence-grounded architectural hotspots."""

    def analyze_hotspots(
        self,
        components: List[DiscoveredComponent],
        metrics: Dict[str, ComponentMetrics],
        security_data: Optional[Dict[str, Any]] = None,
    ) -> List[ArchitectureHotspot]:
        security_data = security_data or {}
        assessments = security_data.get("assessments", [])
        controls = security_data.get("controls", [])
        assets = security_data.get("assets", [])
        scenarios = security_data.get("scenarios", [])

        hotspots: List[ArchitectureHotspot] = []

        for comp in components:
            cid = comp.component_id
            m = metrics.get(cid, ComponentMetrics(component_id=cid))

            # 1. Correlate Security Findings to this component by file path
            comp_file = comp.file_path.strip("./")
            matched_findings = [
                a for a in assessments
                if comp_file in str(a.get("affected_scope", "")).strip("./")
                or comp_file in str(a.get("file_path", "")).strip("./")
            ]
            matched_controls = [
                c for c in controls
                if comp_file in str(c.get("scope", "")).strip("./")
                or comp_file in str(c.get("primary_location", "")).strip("./")
            ]
            matched_assets = [
                ast for ast in assets
                if comp_file in str(ast.get("location", "")).strip("./")
            ]
            matched_scenarios = [
                sc for sc in scenarios
                if any(comp_file in str(ev).strip("./") for ev in sc.get("evidence_references", []))
            ]

            # 2. Compute Deterministic Constituent Scores
            scores: Dict[str, float] = {}
            reasons: List[str] = []

            # A. Coupling Score
            total_coupling = m.afferent_coupling + m.efferent_coupling
            if total_coupling >= 10:
                scores["coupling"] = 2.0
                reasons.append(f"Excessive architectural coupling (Ca={m.afferent_coupling}, Ce={m.efferent_coupling}, total={total_coupling} >= 10)")
            elif total_coupling >= 5:
                scores["coupling"] = 1.0
                reasons.append(f"Elevated architectural coupling (Ca={m.afferent_coupling}, Ce={m.efferent_coupling}, total={total_coupling} >= 5)")
            else:
                scores["coupling"] = 0.0

            # B. Instability Score
            if m.instability is not None and m.instability >= 0.85 and m.efferent_coupling >= 4:
                scores["instability"] = 0.5
                reasons.append(f"High instability metric (I={m.instability:.2f} >= 0.85 with Ce={m.efferent_coupling})")
            else:
                scores["instability"] = 0.0

            # C. Circular Dependency Score
            if m.in_circular_dependency:
                scores["circularity"] = 2.5
                reasons.append(f"Participates in {len(m.circular_cycles)} circular dependency cycle(s)")
            else:
                scores["circularity"] = 0.0

            # D. Cohesion Score
            cohesion_score = 0.0
            if m.is_god_candidate:
                cohesion_score += 1.5
                reasons.append(f"God component candidate: {', '.join(m.god_candidate_reasons)}")
            if m.cohesion_lcom4 is not None and m.cohesion_lcom4 >= 3:
                cohesion_score += 1.0
                reasons.append(f"Low class cohesion measured (LCOM4={m.cohesion_lcom4} disconnected method clusters)")
            scores["cohesion"] = cohesion_score

            # E. Correlated Security Findings
            sec_score = 0.0
            crit_findings = sum(1 for f in matched_findings if f.get("severity") == "CRITICAL")
            high_findings = sum(1 for f in matched_findings if f.get("severity") == "HIGH")
            med_findings = sum(1 for f in matched_findings if f.get("severity") == "MEDIUM")

            if crit_findings > 0:
                sec_score += crit_findings * 3.0
                reasons.append(f"Contains {crit_findings} CRITICAL security finding(s)")
            if high_findings > 0:
                sec_score += high_findings * 2.0
                reasons.append(f"Contains {high_findings} HIGH security finding(s)")
            if med_findings > 0:
                sec_score += med_findings * 1.0
                reasons.append(f"Contains {med_findings} MEDIUM security finding(s)")
            scores["security_findings"] = sec_score

            # F. Critical Asset Relationship
            asset_score = 0.0
            crit_assets = [a for a in matched_assets if a.get("criticality") == "CRITICAL"]
            if crit_assets:
                asset_score = 1.5
                reasons.append(f"Directly part of CRITICAL asset '{crit_assets[0].get('asset_name')}'")
            scores["critical_asset"] = asset_score

            # G. Failed Security Controls
            failed_controls = [c for c in matched_controls if c.get("state") in ("ABSENT", "BYPASSED", "UNKNOWN")]
            if failed_controls:
                ctrl_score = min(2.0, len(failed_controls) * 0.75)
                scores["failed_controls"] = ctrl_score
                reasons.append(f"Associated with {len(failed_controls)} absent/bypassed security control(s)")
            else:
                scores["failed_controls"] = 0.0

            # H. High-Risk Scenarios
            if matched_scenarios:
                scores["risk_scenarios"] = 1.5
                reasons.append(f"Reachable through {len(matched_scenarios)} verified risk scenario(s)")
            else:
                scores["risk_scenarios"] = 0.0

            # 3. Total Composite Hotspot Score
            total_score = round(sum(scores.values()), 2)

            if total_score >= HOTSPOT_CLASSIFICATION_THRESHOLD:
                level = "CRITICAL" if total_score >= 7.0 else ("HIGH" if total_score >= 5.0 else "MEDIUM")
                hotspots.append(
                    ArchitectureHotspot(
                        component_id=cid,
                        component_name=comp.name,
                        component_type=comp.component_type,
                        file_path=comp.file_path,
                        hotspot_score=total_score,
                        hotspot_level=level,
                        reasons=reasons,
                        constituent_scores=scores,
                        raw_metrics={
                            "fan_in": m.fan_in,
                            "fan_out": m.fan_out,
                            "ca": m.afferent_coupling,
                            "ce": m.efferent_coupling,
                            "instability": m.instability,
                            "lcom4": m.cohesion_lcom4,
                            "is_god_candidate": m.is_god_candidate,
                            "in_circular_dependency": m.in_circular_dependency,
                        },
                        correlated_security={
                            "findings_count": len(matched_findings),
                            "critical_findings": crit_findings,
                            "high_findings": high_findings,
                            "controls_count": len(matched_controls),
                            "failed_controls_count": len(failed_controls),
                            "scenarios_count": len(matched_scenarios),
                        },
                    )
                )

        # Sort descending by hotspot score
        hotspots.sort(key=lambda h: h.hotspot_score, reverse=True)
        return hotspots


hotspot_analyzer_service = HotspotAnalyzerService()
