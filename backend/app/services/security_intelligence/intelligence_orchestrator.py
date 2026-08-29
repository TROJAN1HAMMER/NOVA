"""
NOVA Security Intelligence — Intelligence Orchestrator
Orchestrates full Security Intelligence analysis pipeline:
  Asset Discovery -> Observations -> Security Context Graph -> Control Analysis -> Risk Scenarios -> Verification -> Assessment
"""

from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.asset_discovery_service import asset_discovery_service
from app.services.security_intelligence.observation_collector import observation_collector
from app.services.security_intelligence.security_context_graph import security_context_graph
from app.services.security_intelligence.control_analyzer import control_analyzer
from app.services.security_intelligence.risk_scenario_engine import risk_scenario_engine
from app.services.security_intelligence.scenario_verifier import scenario_verifier
from app.services.security_intelligence.explanation_engine import explanation_engine

logger = structlog.get_logger(__name__)


class SecurityIntelligenceOrchestrator:
    """Orchestrates asset discovery, security observations, scenario inference, and assessment verification."""

    def run_full_analysis(self, target_path: str = ".") -> Dict[str, Any]:
        logger.info("security_intel.orchestrator_started", target_path=target_path)

        # 1. Asset Discovery
        assets = asset_discovery_service.discover_assets(target_path)

        all_observations = []
        all_controls = []
        all_scenarios = []
        all_assessments = []

        for asset in assets:
            # 2. Observations
            obs = observation_collector.collect_observations(asset.asset_name, asset.location)
            all_observations.extend(obs)

            # 3. Control Analysis
            ctrls = control_analyzer.evaluate_controls(asset.asset_name, asset.location)
            all_controls.extend(ctrls)

            # 4. Risk Scenario Inference
            scenarios = risk_scenario_engine.infer_scenarios(asset.asset_name, obs, ctrls)
            all_scenarios.extend(scenarios)

            # 5. Verification Gate & Assessments
            verified = scenario_verifier.verify_scenarios(asset.asset_name, asset.location, scenarios, ctrls)
            all_assessments.extend(verified)

        # 6. Security Context Graph
        context_graph = security_context_graph.build_context_graph(all_observations)

        # 7. Security Posture Summary
        posture = self.compute_posture_summary(assets, all_observations, all_controls, all_assessments)

        logger.info("security_intel.orchestrator_completed", assets=len(assets), assessments=len(all_assessments))

        return {
            "status": "COMPLETED",
            "assets": [a.__dict__ for a in assets],
            "observations_count": len(all_observations),
            "controls_count": len(all_controls),
            "risk_scenarios_count": len(all_scenarios),
            "assessments": [a.__dict__ for a in all_assessments],
            "context_graph": context_graph,
            "posture": posture
        }

    def compute_posture_summary(
        self, assets: List[Any], observations: List[Any], controls: List[Any], assessments: List[Any]
    ) -> Dict[str, Any]:
        total_assets = len(assets)
        critical_assets = sum(1 for a in assets if a.criticality == "CRITICAL")
        high_severity_risks = sum(1 for a in assessments if a.severity in ["CRITICAL", "HIGH"])

        present_controls = sum(1 for c in controls if c.state == "PRESENT")
        absent_controls = sum(1 for c in controls if c.state in ["ABSENT", "PARTIAL"])

        posture_score = round(max(100.0 - (high_severity_risks * 15.0) - (absent_controls * 5.0), 40.0), 1)

        return {
            "posture_score": posture_score,
            "posture_rating": "STRONG" if posture_score >= 80 else ("MODERATE" if posture_score >= 60 else "NEEDS_ATTENTION"),
            "total_assets": total_assets,
            "critical_assets": critical_assets,
            "control_coverage": {
                "present_controls": present_controls,
                "absent_or_partial_controls": absent_controls,
                "coverage_percentage": round((present_controls / max(len(controls), 1)) * 100.0, 1)
            },
            "unresolved_risks_count": len(assessments),
            "security_trend": "IMPROVING"
        }


security_intelligence_orchestrator = SecurityIntelligenceOrchestrator()
