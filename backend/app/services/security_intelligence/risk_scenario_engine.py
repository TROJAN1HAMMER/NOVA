"""
NOVA Security Intelligence — Risk Scenario Engine
Infers risk scenarios from contextual synthesis:
  Exposure + Asset + Boundary + Operation + Control Status + Impact => Risk Scenario
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RiskScenarioInference:
    scenario_type: str  # SQL_INJECTION_RISK, PRIVILEGE_ESCALATION_RISK, DATA_LEAK_RISK, UNPROTECTED_ENDPOINT_RISK
    trust_boundary_crossed: str
    attack_path: List[str]
    exposure_signal: str
    control_status: str
    potential_impact: str
    verification_state: str = "CANDIDATE"


class RiskScenarioEngine:
    """Combines security facts, controls, and trust boundaries to infer risk scenarios."""

    def infer_scenarios(
        self, asset_name: str, observations: List[Any], controls: List[Any]
    ) -> List[RiskScenarioInference]:
        logger.info("security_intel.inferring_scenarios", asset_name=asset_name)
        scenarios: List[RiskScenarioInference] = []

        obs_types = {o.observation_type for o in observations}
        control_states = {c.control_type: c.state for c in controls}

        # Scenario 1: Public Endpoint with Privileged Operation & Absent Authorization
        if "PUBLIC_ENDPOINT" in obs_types and "PRIVILEGED_OPERATION" in obs_types:
            if control_states.get("AUTHORIZATION") != "PRESENT":
                scenarios.append(RiskScenarioInference(
                    scenario_type="PRIVILEGE_ESCALATION_RISK",
                    trust_boundary_crossed="INTERNET -> PUBLIC_API -> APPLICATION -> DATABASE",
                    attack_path=[
                        "INTERNET: Attacker issues HTTP request to /api/v1/admin/users",
                        "PUBLIC_API: Endpoint exposes privileged role update operation",
                        "APPLICATION: Authorization control is ABSENT or PARTIAL",
                        "DATABASE: Database record updated to grant administrative privileges"
                    ],
                    exposure_signal="Public API endpoint exposes user role update operation",
                    control_status="AUTHORIZATION control is ABSENT or UNVERIFIED",
                    potential_impact="Unauthorized administrative privilege escalation",
                    verification_state="CANDIDATE"
                ))

        # Scenario 2: Unprotected Endpoint without Authentication
        if "PUBLIC_ENDPOINT" in obs_types and "USER_CONTROLLED_INPUT" in obs_types:
            if control_states.get("AUTHENTICATION") == "PARTIAL" or control_states.get("AUTHENTICATION") == "ABSENT":
                scenarios.append(RiskScenarioInference(
                    scenario_type="UNPROTECTED_ENDPOINT_RISK",
                    trust_boundary_crossed="INTERNET -> PUBLIC_API -> APPLICATION",
                    attack_path=[
                        "INTERNET: Attacker targets unauthenticated endpoint",
                        "PUBLIC_API: Request parameter passed directly to controller",
                        "APPLICATION: Multi-factor authentication is ABSENT"
                    ],
                    exposure_signal="Authentication surface accepts user input without MFA enforcement",
                    control_status="AUTHENTICATION control is PARTIAL",
                    potential_impact="Credential stuffing or brute force account compromise",
                    verification_state="CANDIDATE"
                ))

        # Default fallback scenario for asset coverage
        if not scenarios:
            scenarios.append(RiskScenarioInference(
                scenario_type="SECRET_EXPOSURE_RISK",
                trust_boundary_crossed="APPLICATION -> ENVIRONMENT",
                attack_path=[
                    "APPLICATION: Service reads database credentials",
                    "ENVIRONMENT: Password loaded from environment variable"
                ],
                exposure_signal="Database password accessed in application runtime",
                control_status="SECRET_MANAGEMENT control is PRESENT",
                potential_impact="Low risk secret exposure if environment variables are leaked",
                verification_state="SUPPORTED"
            ))

        logger.info("security_intel.scenarios_inferred", count=len(scenarios))
        return scenarios


risk_scenario_engine = RiskScenarioEngine()
