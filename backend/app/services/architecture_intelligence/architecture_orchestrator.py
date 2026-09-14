"""
NOVA Architecture Intelligence — Subsystem Orchestrator
Coordinates component discovery, dependency extraction, coupling/cohesion calculation,
hotspot classification, security correlation, blast radius, traceability, and drift analysis.
Integrates read-only with existing Security Intelligence data without modifying its authoritative formulas.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.security_intelligence.intelligence_orchestrator import (
    security_intelligence_orchestrator,
)

logger = structlog.get_logger(__name__)


class ArchitectureIntelligenceOrchestrator:
    """Master orchestrator for Architecture & Connectivity Intelligence."""

    def __init__(self):
        # In-memory snapshot history store keyed by target scope
        self._snapshot_history: Dict[str, List[Dict[str, Any]]] = {}
        self._last_analysis: Dict[str, Dict[str, Any]] = {}
        self._scan_cache: Dict[str, Dict[str, Any]] = {}

    def get_cache_key(self, scan_id: str) -> str:
        """Cache keys MUST include the scan identity: architecture_graph:<scan_id>."""
        return f"architecture_graph:{scan_id}"

    def get_analysis_for_scan(
        self,
        scan_id: str,
        target_path: Optional[str] = None,
        project_name: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Returns architecture intelligence strictly scoped to the specified scan_id."""
        cache_key = self.get_cache_key(scan_id)
        if not force_refresh and cache_key in self._scan_cache:
            return self._scan_cache[cache_key]

        path_to_use = target_path or "."
        res = self.run_architecture_analysis(
            target_path=path_to_use,
            project_name=project_name or f"Scan {scan_id[:8]}",
            scan_id=scan_id,
            force_refresh=True,
        )
        res["scan_id"] = scan_id
        self._scan_cache[cache_key] = res
        return res

    def run_architecture_analysis(
        self,
        target_path: str = ".",
        project_name: str = "NOVA Core",
        scan_id: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        analysis_id = scan_id or str(uuid.uuid4())
        repo_root = Path(target_path).resolve()
        scope_key = str(repo_root)

        if not force_refresh and scan_id is None and scope_key in self._last_analysis:
            return self._last_analysis[scope_key]

        logger.info("architecture_intel.analysis_started", target_path=target_path, analysis_id=analysis_id)

        # 1. Component Discovery
        components = component_discovery_service.discover_components(str(repo_root))

        # 2. Dependency Extraction
        dependencies = dependency_extractor_service.extract_dependencies(components, str(repo_root))

        # 3. Compute Coupling, Cohesion & Circular Metrics
        metrics = architecture_metrics_engine.compute_all_metrics(components, dependencies, str(repo_root))

        # 4. Safe Read-Only Fetch of Existing Security Intelligence Data
        security_data: Dict[str, Any] = {}
        try:
            sec_analysis = security_intelligence_orchestrator.run_full_analysis(str(repo_root), force_refresh=False)
            security_data = {
                "assets": sec_analysis.get("assets", []),
                "assessments": sec_analysis.get("assessments", []),
                "controls": sec_analysis.get("controls", []),
                "scenarios": sec_analysis.get("scenarios", []),
            }
        except Exception as exc:
            logger.warning("architecture_intel.security_correlation_skipped", error=str(exc))

        # 5. Architecture Hotspots Classification
        hotspots = hotspot_analyzer_service.analyze_hotspots(components, metrics.component_metrics, security_data)

        # 6. Unified Traceability Links
        traceability_chains = traceability_engine.build_traceability(components, security_data)

        # 7. Format Serializable Output
        formatted_components = []
        for c in components:
            cm = metrics.component_metrics.get(c.component_id)
            formatted_components.append({
                "component_id": c.component_id,
                "name": c.name,
                "component_type": c.component_type,
                "file_path": c.file_path,
                "line_number": c.line_number,
                "language": c.language,
                "fan_in": cm.fan_in if cm else 0,
                "fan_out": cm.fan_out if cm else 0,
                "ca": cm.afferent_coupling if cm else 0,
                "ce": cm.efferent_coupling if cm else 0,
                "instability": cm.instability if cm else None,
                "lcom4": cm.cohesion_lcom4 if cm else None,
                "cohesion_metric_type": cm.cohesion_metric_type if cm else "UNAVAILABLE",
                "is_god_candidate": cm.is_god_candidate if cm else False,
                "in_circular_dependency": cm.in_circular_dependency if cm else False,
                "circular_cycles": cm.circular_cycles if cm else [],
                "dependency_depth": cm.dependency_depth if cm else 0,
                "attributes": c.attributes,
            })

        formatted_dependencies = [
            {
                "source_id": d.source_id,
                "target_id": d.target_id,
                "relation_type": d.relation_type,
                "file_path": d.file_path,
                "line_number": d.line_number,
                "evidence": d.evidence,
                "is_circular": d.is_circular,
            }
            for d in dependencies
        ]

        formatted_hotspots = [
            {
                "component_id": h.component_id,
                "component_name": h.component_name,
                "component_type": h.component_type,
                "file_path": h.file_path,
                "hotspot_score": h.hotspot_score,
                "hotspot_level": h.hotspot_level,
                "reasons": h.reasons,
                "constituent_scores": h.constituent_scores,
                "raw_metrics": h.raw_metrics,
                "correlated_security": h.correlated_security,
            }
            for h in hotspots
        ]

        formatted_traceability = [
            {
                "chain_id": t.chain_id,
                "component_id": t.component_id,
                "component_name": t.component_name,
                "file_path": t.file_path,
                "line_number": t.line_number,
                "requirement_doc_name": t.requirement_doc_name,
                "graph_entity_name": t.graph_entity_name,
                "control_name": t.control_name,
                "control_state": t.control_state,
                "finding_title": t.finding_title,
                "finding_severity": t.finding_severity,
                "risk_scenario_title": t.risk_scenario_title,
                "provenance": t.provenance,
            }
            for t in traceability_chains
        ]

        result_payload = {
            "snapshot_id": analysis_id,
            "scan_id": scan_id,
            "project_name": project_name,
            "target_scope": str(repo_root),
            "summary": {
                "total_components": metrics.total_components,
                "total_dependencies": metrics.total_dependencies,
                "total_circular_cycles": metrics.total_circular_cycles,
                "circular_components_count": metrics.circular_components_count,
                "average_instability": metrics.average_instability,
                "max_dependency_depth": metrics.max_dependency_depth,
                "god_module_candidates_count": metrics.god_module_candidates_count,
                "hotspots_count": len(formatted_hotspots),
                "traceability_chains_count": len(formatted_traceability),
            },
            "cycles_detected": metrics.cycles_detected,
            "components": formatted_components,
            "dependencies": formatted_dependencies,
            "hotspots": formatted_hotspots,
            "traceability": formatted_traceability,
            "metrics": {
                "average_instability": metrics.average_instability,
                "max_depth": metrics.max_dependency_depth,
                "component_metrics": {
                    cid: {
                        "fan_in": cm.fan_in,
                        "fan_out": cm.fan_out,
                        "ca": cm.afferent_coupling,
                        "ce": cm.efferent_coupling,
                        "instability": cm.instability,
                        "lcom4": cm.cohesion_lcom4,
                        "is_god_candidate": cm.is_god_candidate,
                        "in_circular_dependency": cm.in_circular_dependency,
                    }
                    for cid, cm in metrics.component_metrics.items()
                },
            },
        }

        # Save to snapshot history
        history = self._snapshot_history.setdefault(scope_key, [])
        history.append(result_payload)
        self._last_analysis[scope_key] = result_payload

        logger.info(
            "architecture_intel.analysis_completed",
            components=len(components),
            dependencies=len(dependencies),
            hotspots=len(hotspots),
        )
        return result_payload

    def get_latest_analysis(self, target_path: str = ".") -> Dict[str, Any]:
        repo_root = Path(target_path).resolve()
        scope_key = str(repo_root)
        if scope_key in self._last_analysis:
            return self._last_analysis[scope_key]
        return self.run_architecture_analysis(target_path=target_path)

    def compute_blast_radius(
        self,
        component_id: str,
        target_path: str = ".",
        scan_id: Optional[str] = None,
    ) -> BlastRadiusReport:
        if scan_id:
            analysis = self.get_analysis_for_scan(scan_id=scan_id, target_path=target_path)
        else:
            analysis = self.get_latest_analysis(target_path)
        comps = [
            DiscoveredComponent(
                component_id=c["component_id"],
                name=c["name"],
                component_type=c["component_type"],
                file_path=c["file_path"],
                line_number=c.get("line_number"),
            )
            for c in analysis["components"]
        ]
        deps = [
            DiscoveredDependency(
                source_id=d["source_id"],
                target_id=d["target_id"],
                relation_type=d["relation_type"],
                file_path=d.get("file_path", ""),
            )
            for d in analysis["dependencies"]
        ]
        sec_data = {}
        try:
            sec_analysis = security_intelligence_orchestrator.run_full_analysis(target_path, force_refresh=False)
            sec_data = {
                "assessments": sec_analysis.get("assessments", []),
                "controls": sec_analysis.get("controls", []),
                "scenarios": sec_analysis.get("scenarios", []),
                "assets": sec_analysis.get("assets", []),
            }
        except Exception:
            pass

        return blast_radius_engine.compute_blast_radius(component_id, comps, deps, sec_data)

    def get_architecture_drift(
        self,
        target_path: str = ".",
        scan_id: Optional[str] = None,
    ) -> ArchitectureDriftReport:
        repo_root = Path(target_path).resolve()
        scope_key = str(repo_root)
        history = self._snapshot_history.get(scope_key, [])

        if len(history) < 2:
            return architecture_drift_engine.compare_snapshots(
                current_data=history[-1] if history else {},
                previous_data=None,
            )
        return architecture_drift_engine.compare_snapshots(
            current_data=history[-1],
            previous_data=history[-2],
        )

    def analyze_change_impact(
        self,
        target_path: str = ".",
        changed_files: Optional[List[str]] = None,
        scan_id: Optional[str] = None,
    ) -> ChangeImpactReport:
        if scan_id:
            analysis = self.get_analysis_for_scan(scan_id=scan_id, target_path=target_path)
        else:
            analysis = self.get_latest_analysis(target_path)
        comps = [
            DiscoveredComponent(
                component_id=c["component_id"],
                name=c["name"],
                component_type=c["component_type"],
                file_path=c["file_path"],
                line_number=c.get("line_number"),
            )
            for c in analysis["components"]
        ]
        deps = [
            DiscoveredDependency(
                source_id=d["source_id"],
                target_id=d["target_id"],
                relation_type=d["relation_type"],
                file_path=d.get("file_path", ""),
            )
            for d in analysis["dependencies"]
        ]
        return change_impact_engine.analyze_change_impact(
            target_path=target_path,
            changed_files=changed_files,
            components=comps,
            dependencies=deps,
        )

    def estimate_remediation_impact(
        self,
        component_id: str,
        proposed_remediation: str,
        target_path: str = ".",
        scan_id: Optional[str] = None,
    ) -> RemediationImpactReport:
        if scan_id:
            analysis = self.get_analysis_for_scan(scan_id=scan_id, target_path=target_path)
        else:
            analysis = self.get_latest_analysis(target_path)
        comps = [
            DiscoveredComponent(
                component_id=c["component_id"],
                name=c["name"],
                component_type=c["component_type"],
                file_path=c["file_path"],
                line_number=c.get("line_number"),
            )
            for c in analysis["components"]
        ]
        deps = [
            DiscoveredDependency(
                source_id=d["source_id"],
                target_id=d["target_id"],
                relation_type=d["relation_type"],
                file_path=d.get("file_path", ""),
            )
            for d in analysis["dependencies"]
        ]
        sec_data = {}
        try:
            sec_analysis = security_intelligence_orchestrator.run_full_analysis(target_path, force_refresh=False)
            sec_data = {
                "assessments": sec_analysis.get("assessments", []),
                "controls": sec_analysis.get("controls", []),
                "scenarios": sec_analysis.get("scenarios", []),
                "assets": sec_analysis.get("assets", []),
            }
        except Exception:
            pass

        return remediation_impact_engine.estimate_remediation_impact(
            component_id=component_id,
            proposed_remediation=proposed_remediation,
            components=comps,
            dependencies=deps,
            security_data=sec_data,
        )


architecture_orchestrator = ArchitectureIntelligenceOrchestrator()
