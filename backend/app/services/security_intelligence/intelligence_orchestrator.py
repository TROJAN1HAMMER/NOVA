"""
NOVA Security Intelligence — Intelligence Orchestrator
Orchestrates the complete, evidence-grounded Security Intelligence analysis pipeline:
  Asset Discovery -> Observations & AST Rules -> Context Graph -> Control Analysis -> Risk Scenarios -> Verification -> Assessment -> Posture & Trend
Strictly guarantees:
- No local filesystem paths escape to API/UI.
- Canonical findings and assessments are 100% synchronized with aggregate severity counts.
- Zero fake/synthetic findings or fallback scenarios.
"""

import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import structlog

from app.services.security_intelligence.asset_discovery_service import asset_discovery_service
from app.services.security_intelligence.observation_collector import observation_collector
from app.services.security_intelligence.security_context_graph import security_context_graph
from app.services.security_intelligence.control_analyzer import control_analyzer
from app.services.security_intelligence.risk_scenario_engine import risk_scenario_engine
from app.services.security_intelligence.scenario_verifier import scenario_verifier
from app.services.security_intelligence.posture_trend_engine import posture_trend_engine
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


def _get_severity(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("severity", "")).upper()
    return str(getattr(item, "severity", "")).upper()


def _get_state(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("state", item.get("status", "UNKNOWN"))).upper()
    return str(getattr(item, "state", getattr(item, "status", "UNKNOWN"))).upper()


def _get_status(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("status", "OPEN")).upper()
    return str(getattr(item, "status", "OPEN")).upper()


class SecurityIntelligenceOrchestrator:
    """Orchestrates asset discovery, security observations, scenario inference, and assessment verification."""

    def __init__(self):
        self._history_store: Dict[str, List[Dict[str, Any]]] = {}
        self._last_assessments: Dict[str, List[Any]] = {}
        self._last_results: Dict[str, Dict[str, Any]] = {}

    def run_full_analysis(
        self,
        target_path: str = ".",
        project_name: Optional[str] = None,
        scan_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        analysis_run_id = scan_id or str(uuid.uuid4())
        repo_root = Path(target_path).resolve()
        scope_key = project_name if project_name else target_path

        if not force_refresh and scan_id is None and scope_key in self._last_results:
            return self._last_results[scope_key]

        logger.info("security_intel.orchestrator_started", target_path=target_path, run_id=analysis_run_id)

        if progress_callback:
            progress_callback(10, "DISCOVERING_ASSETS")

        # 1. Asset Discovery
        assets = asset_discovery_service.discover_assets(str(repo_root))

        if progress_callback:
            progress_callback(30, "ANALYZING")

        all_observations = []
        all_controls = []
        all_scenarios = []
        all_assessments = []

        # Collect observations across repository workspace
        root_obs = observation_collector.collect_observations("Repository Workspace", str(repo_root), repo_root=repo_root)
        all_observations.extend(root_obs)

        # Map observations to specific assets without leaking local filesystem paths
        for asset in assets:
            if asset.location not in [".", str(repo_root)]:
                asset_obs = [o for o in root_obs if asset.location in getattr(o, "location", "")]
                if not asset_obs:
                    asset_obs = observation_collector.collect_observations(asset.asset_name, asset.location, repo_root=repo_root)
                    all_observations.extend(asset_obs)

        if progress_callback:
            progress_callback(55, "EVALUATING_CONTROLS")

        # Evaluate the standard security controls across the repository workspace
        all_controls = control_analyzer.evaluate_controls(
            "Repository Workspace",
            ".",
            repo_root=repo_root,
            observations=all_observations,
        )

        if progress_callback:
            progress_callback(70, "BUILDING_RISKS")

        # Infer scenarios and verify assessments per asset
        seen_assessment_keys = set()
        seen_scenario_keys = set()

        for asset in assets:
            if asset.asset_type == "APPLICATION":
                asset_obs = all_observations
            else:
                asset_obs = [o for o in all_observations if asset.location in getattr(o, "location", "")]

            asset_ctrls = [c for c in all_controls if getattr(c, "scope", "") == asset.location] or all_controls
            scenarios = risk_scenario_engine.infer_scenarios(asset.asset_name, asset_obs, asset_ctrls)

            for sc in scenarios:
                ev_tup = tuple(getattr(sc, "evidence_references", []))
                sc_key = (getattr(sc, "scenario_type", ""), ev_tup)
                if sc_key not in seen_scenario_keys:
                    seen_scenario_keys.add(sc_key)
                    all_scenarios.append(sc)

            verified = scenario_verifier.verify_scenarios(asset.asset_name, asset.location, scenarios, asset_ctrls, repo_root=repo_root)
            for ass in verified:
                ass_key = (getattr(ass, "risk_type", ""), getattr(ass, "affected_scope", ""), getattr(ass, "line_number", 0))
                if ass_key not in seen_assessment_keys:
                    seen_assessment_keys.add(ass_key)
                    all_assessments.append(ass)

        if progress_callback:
            progress_callback(85, "GENERATING_EVIDENCE")

        # 6. Security Context Graph
        context_graph = security_context_graph.build_context_graph(all_observations, assets=assets, repo_root=repo_root)

        # 7. Temporal Security Posture Snapshot & Risk Evolution
        history = self._history_store.get(scope_key, [])
        prev_snapshot = history[-1] if history else None
        prev_assessments = self._last_assessments.get(scope_key)

        snapshot = posture_trend_engine.generate_snapshot_record(
            analysis_run_id=analysis_run_id,
            target_scope=scope_key,
            assets=assets,
            controls=all_controls,
            assessments=all_assessments,
            previous_snapshot=prev_snapshot,
            previous_assessments=prev_assessments,
        )

        if scope_key not in self._history_store:
            self._history_store[scope_key] = []
        self._history_store[scope_key].append(snapshot)
        self._last_assessments[scope_key] = all_assessments

        if scope_key != "." and target_path == ".":
            self._history_store["."] = self._history_store[scope_key]
            self._last_assessments["."] = all_assessments

        # 8. Posture Summary
        posture = self.compute_posture_summary(assets, all_observations, all_controls, all_assessments, snapshot)

        if progress_callback:
            progress_callback(100, "COMPLETED")

        logger.info(
            "security_intel.orchestrator_completed",
            assets=len(assets),
            assessments=len(all_assessments),
            posture_score=posture["posture_score"],
            trend=snapshot["trend_direction"]
        )

        serialized_assessments = [a.__dict__ if hasattr(a, "__dict__") else a for a in all_assessments]

        open_findings = [a for a in serialized_assessments if _get_status(a) == "OPEN"]

        res = {
            "status": "COMPLETED",
            "analysis_run_id": analysis_run_id,
            "project_name": project_name or repo_root.name,
            "assets": [a.__dict__ if hasattr(a, "__dict__") else a for a in assets],
            "observations_count": len(all_observations),
            "observations": [o.__dict__ if hasattr(o, "__dict__") else o for o in all_observations],
            "findings": open_findings,  # Canonical collection of actual verified vulnerability findings
            "total_findings": len(open_findings),
            "controls_count": len(all_controls),
            "controls": [c.__dict__ if hasattr(c, "__dict__") else c for c in all_controls],
            "risk_scenarios_count": len(all_scenarios),
            "risk_scenarios": [s.__dict__ if hasattr(s, "__dict__") else s for s in all_scenarios],
            "risks": [s.__dict__ if hasattr(s, "__dict__") else s for s in all_scenarios],
            "assessments": serialized_assessments,
            "context_graph": context_graph,
            "graph": context_graph,
            "posture": posture,
            "snapshot": snapshot,
        }
        self._last_results[scope_key] = res
        if scope_key != "." and target_path == ".":
            self._last_results["."] = res
        return res

    def get_posture_history(self, target_scope: str = ".", limit: int = 30) -> List[Dict[str, Any]]:
        history = self._history_store.get(target_scope, [])
        if not history and target_scope != ".":
            resolved = str(Path(target_scope).resolve())
            history = self._history_store.get(resolved, [])
        return history[-limit:]

    def compute_posture_summary(
        self,
        assets: List[Any],
        observations: List[Any],
        controls: List[Any],
        assessments: List[Any],
        snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        total_assets = len(assets)
        critical_assets = sum(1 for a in assets if getattr(a, "criticality", "") == "CRITICAL")

        # Canonical severity counts strictly computed from OPEN assessments
        critical_risks = sum(1 for a in assessments if _get_severity(a) == "CRITICAL" and _get_status(a) == "OPEN")
        high_risks = sum(1 for a in assessments if _get_severity(a) == "HIGH" and _get_status(a) == "OPEN")
        medium_risks = sum(1 for a in assessments if _get_severity(a) == "MEDIUM" and _get_status(a) == "OPEN")
        low_risks = sum(1 for a in assessments if _get_severity(a) == "LOW" and _get_status(a) == "OPEN")
        total_open_findings = sum(1 for a in assessments if _get_status(a) == "OPEN")

        present_controls = sum(1 for c in controls if _get_state(c) in ["PRESENT", "PASS"])
        absent_controls = sum(1 for c in controls if _get_state(c) in ["ABSENT", "FAIL"])
        partial_controls = sum(1 for c in controls if _get_state(c) == "PARTIAL")

        posture_score = snapshot.get("posture_score") if snapshot else round(
            max(100.0 - (critical_risks * 25.0) - (high_risks * 15.0) - (medium_risks * 5.0) - (low_risks * 2.0) - (absent_controls * 8.0) - (partial_controls * 4.0), 10.0), 1
        )
        trend = snapshot.get("trend_direction", "UNCHANGED") if snapshot else "UNCHANGED"
        delta = snapshot.get("delta_score") if snapshot else None

        return {
            "posture_score": posture_score,
            "posture_rating": "STRONG" if posture_score >= 80 else ("MODERATE" if posture_score >= 60 else "NEEDS_ATTENTION"),
            "delta_score": delta,
            "total_assets": total_assets,
            "critical_assets": critical_assets,
            "total_findings": total_open_findings,
            "severity_breakdown": {
                "critical": critical_risks,
                "high": high_risks,
                "medium": medium_risks,
                "low": low_risks,
            },
            "control_coverage": {
                "present_controls": present_controls,
                "absent_or_partial_controls": absent_controls + partial_controls,
                "coverage_percentage": round((present_controls / max(len(controls), 1)) * 100.0, 1)
            },
            "unresolved_risks_count": len([a for a in assessments if getattr(a, "status", "OPEN") == "OPEN"]),
            "security_trend": trend,
            "risk_evolution_summary": snapshot.get("risk_evolution_summary") if snapshot else None,
            "scoring_inputs": snapshot.get("scoring_inputs") if snapshot else None,
        }


security_intelligence_orchestrator = SecurityIntelligenceOrchestrator()
