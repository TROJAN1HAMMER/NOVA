"""
NOVA Security Intelligence — Risk Scenario Engine
Infers risk scenarios strictly from contextual synthesis of actual observations, findings, and controls:
  ASSET -> OBSERVATION -> CONTROL WEAKNESS -> RISK SCENARIO -> IMPACT
Never generates synthetic or fallback scenarios when code is clean.
"""

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class RiskScenarioInference:
    scenario_id: str
    title: str
    scenario_type: str  # SQL_INJECTION_RISK, PRIVILEGE_ESCALATION_RISK, DATA_LEAK_RISK, UNPROTECTED_ENDPOINT_RISK, SECRET_EXPOSURE_RISK, COMMAND_INJECTION_RISK, INSECURE_CONFIGURATION_RISK
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    source_assets: List[str]
    triggering_finding: str
    control_weakness: str
    attack_path: List[str]
    potential_impact: str
    evidence_references: List[str]
    confidence: float
    remediation: str
    trust_boundary_crossed: str
    exposure_signal: str
    control_status: str
    scenario_chain: Dict[str, str] = field(default_factory=dict)
    verification_state: str = "CANDIDATE"
    lifecycle_state: str = "RISK_CANDIDATE"
    parent_control_ids: List[str] = field(default_factory=list)
    parent_observation_ids: List[str] = field(default_factory=list)
    inference_timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    provenance_chain: List[str] = field(default_factory=lambda: ["code_ast_parser", "control_evaluator", "risk_scenario_engine"])
    finding_ref: Optional[Any] = None


class RiskScenarioEngine:
    """Combines security facts, controls, and trust boundaries to infer evidence-grounded risk scenarios."""

    def infer_scenarios(
        self, asset_name: str, observations: List[Any], controls: List[Any]
    ) -> List[RiskScenarioInference]:
        logger.info("security_intel.inferring_scenarios", asset_name=asset_name)
        scenarios: List[RiskScenarioInference] = []

        obs_types = {getattr(o, "observation_type", "") for o in observations}
        control_states = {getattr(c, "control_type", ""): getattr(c, "state", "UNKNOWN") for c in controls}

        # Extract direct static findings
        findings = []
        for o in observations:
            fd = getattr(o, "finding_data", None)
            if not fd and isinstance(getattr(o, "attributes", None), dict):
                fd = o.attributes.get("finding_data")
            if fd:
                findings.append(fd)

        scenario_idx = 1

        # 1. Scenarios from Direct Static Security Findings
        for f in findings:
            cat = getattr(f, "category", "")
            title = getattr(f, "title", "Security Finding")
            raw_loc = getattr(f, "file_path", "source")
            line = getattr(f, "line_number", 1)
            loc = normalize_repo_path(raw_loc)
            rule_id = getattr(f, "rule_id", "")
            finding_severity = getattr(f, "severity", "HIGH")
            ev_ref = f"{loc}:{line}"

            if cat == "SECRET_EXPOSURE":
                scenarios.append(RiskScenarioInference(
                    scenario_id=f"SCN-SEC-{scenario_idx:03d}",
                    title=f"Hardcoded Secret Exposure ({title})",
                    scenario_type="SECRET_EXPOSURE_RISK",
                    severity=finding_severity,
                    source_assets=[asset_name],
                    triggering_finding=f"{title} detected in {ev_ref}",
                    control_weakness="Secrets Management control is COMPROMISED (plaintext credentials in code)",
                    trust_boundary_crossed="APPLICATION -> CLOUD_PROVIDER / REPOSITORY",
                    attack_path=[
                        f"SOURCE: Plaintext credential committed in {ev_ref}",
                        "REPOSITORY: Exposed in source code / version control history",
                        "CLOUD_INFRASTRUCTURE: Attacker leverages leaked credential to authenticate directly to downstream services"
                    ],
                    exposure_signal=f"Plaintext secret discovered in {ev_ref}",
                    control_status="SECRET_MANAGEMENT control is COMPROMISED",
                    potential_impact="Unauthorized access to database, cloud infrastructure, or external APIs",
                    evidence_references=[ev_ref],
                    confidence=getattr(f, "confidence", 0.95),
                    remediation=getattr(f, "remediation", "Remove hardcoded credentials and rotate exposed keys."),
                    scenario_chain={
                        "asset": asset_name,
                        "observation": f"Credential pattern in {ev_ref}",
                        "control_weakness": "SECM-001 is ABSENT",
                        "risk_scenario": "Exposed Credential Authentication Hijacking",
                        "impact": "Account takeover and cloud infrastructure compromise"
                    },
                    verification_state="VERIFIED",
                    finding_ref=f,
                ))
                scenario_idx += 1

            elif cat == "INJECTION":
                is_sql = "SQL" in title or "SQL" in rule_id
                sc_type = "SQL_INJECTION_RISK" if is_sql else "COMMAND_INJECTION_RISK"
                sc_title = "Unparameterized SQL Injection" if is_sql else "OS Command Injection via Shell Execution"
                scenarios.append(RiskScenarioInference(
                    scenario_id=f"SCN-INJ-{scenario_idx:03d}",
                    title=sc_title,
                    scenario_type=sc_type,
                    severity=finding_severity,
                    source_assets=[asset_name],
                    triggering_finding=f"{title} detected in {ev_ref}",
                    control_weakness="Input Validation control is ABSENT or PARTIAL",
                    trust_boundary_crossed="INTERNET -> PUBLIC_API -> APPLICATION -> DATABASE / HOST",
                    attack_path=[
                        f"INTERNET: Attacker submits crafted injection payload to endpoint in {loc}",
                        "PUBLIC_API: Request parameter passed directly to interpreter without sanitization",
                        "APPLICATION: Dynamic concatenation executes malicious payload in process context"
                    ],
                    exposure_signal=f"Unparameterized query / dynamic command execution in {ev_ref}",
                    control_status="INPUT_VALIDATION control is ABSENT or PARTIAL",
                    potential_impact="Arbitrary SQL query execution, full database exfiltration, or remote code execution",
                    evidence_references=[ev_ref],
                    confidence=getattr(f, "confidence", 0.92),
                    remediation=getattr(f, "remediation", "Use parameterized queries or pass subprocess arguments as a list."),
                    scenario_chain={
                        "asset": asset_name,
                        "observation": f"Dynamic concatenation in {ev_ref}",
                        "control_weakness": "INPJ-001 is ABSENT",
                        "risk_scenario": sc_title,
                        "impact": "Full database breach or remote system compromise"
                    },
                    verification_state="VERIFIED",
                    finding_ref=f,
                ))
                scenario_idx += 1

            elif cat == "AUTHENTICATION_AUTHORIZATION":
                scenarios.append(RiskScenarioInference(
                    scenario_id=f"SCN-AUTH-{scenario_idx:03d}",
                    title="Administrative Route Authorization Bypass",
                    scenario_type="PRIVILEGE_ESCALATION_RISK",
                    severity=finding_severity,
                    source_assets=[asset_name],
                    triggering_finding=f"{title} detected in {ev_ref}",
                    control_weakness="Authorization control is ABSENT on privileged route",
                    trust_boundary_crossed="INTERNET -> PUBLIC_API -> APPLICATION -> DATABASE",
                    attack_path=[
                        f"INTERNET: Attacker issues HTTP request to {ev_ref}",
                        "PUBLIC_API: Endpoint exposes privileged administrative operation",
                        "APPLICATION: Authorization guard is ABSENT on route handler",
                        "DATABASE: Target records modified granting unauthorized permissions"
                    ],
                    exposure_signal=f"Privileged route lacking RBAC enforcement in {ev_ref}",
                    control_status="AUTHORIZATION control is ABSENT",
                    potential_impact="Unauthorized administrative access and privilege escalation",
                    evidence_references=[ev_ref],
                    confidence=getattr(f, "confidence", 0.90),
                    remediation=getattr(f, "remediation", "Enforce RequireRole or permission dependency on route."),
                    scenario_chain={
                        "asset": asset_name,
                        "observation": f"Unprotected administrative route in {ev_ref}",
                        "control_weakness": "AUTHZ-001 is ABSENT",
                        "risk_scenario": "Administrative Route Authorization Bypass",
                        "impact": "Privilege escalation and unauthorized data manipulation"
                    },
                    verification_state="VERIFIED",
                    finding_ref=f,
                ))
                scenario_idx += 1

            elif cat == "CONFIGURATION":
                scenarios.append(RiskScenarioInference(
                    scenario_id=f"SCN-CFG-{scenario_idx:03d}",
                    title=f"Insecure Security Configuration ({title})",
                    scenario_type="INSECURE_CONFIGURATION_RISK",
                    severity=finding_severity,
                    source_assets=[asset_name],
                    triggering_finding=f"{title} detected in {ev_ref}",
                    control_weakness="Secure Configuration control is ABSENT or DEGRADED",
                    trust_boundary_crossed="INTERNET -> PUBLIC_PERIMETER",
                    attack_path=[
                        f"INTERNET: Attacker probes perimeter configuration for {loc}",
                        "PERIMETER: Permissive CORS or debug mode exposes internal metadata",
                        "INTERNAL: Internal endpoints accessible across origins without restriction"
                    ],
                    exposure_signal=f"Insecure configuration pattern in {ev_ref}",
                    control_status="SECURE_CONFIGURATION control is DEGRADED",
                    potential_impact="Cross-origin data leakage or sensitive debug traceback exposure",
                    evidence_references=[ev_ref],
                    confidence=getattr(f, "confidence", 0.88),
                    remediation=getattr(f, "remediation", "Restrict CORS origins and disable debug mode in production."),
                    scenario_chain={
                        "asset": asset_name,
                        "observation": f"Configuration weakness in {ev_ref}",
                        "control_weakness": "CONF-001 is ABSENT",
                        "risk_scenario": "Insecure Security Configuration",
                        "impact": "Cross-origin information disclosure"
                    },
                    verification_state="VERIFIED",
                    finding_ref=f,
                ))
                scenario_idx += 1

        if not scenarios and ("PRIVILEGED_OPERATION" in obs_types or "ADMIN" in asset_name.upper()):
            if control_states.get("AUTHORIZATION") != "PRESENT":
                sc_loc = observations[0].location if observations else "source"
                scenarios.append(RiskScenarioInference(
                    scenario_id=f"SCN-CAND-{scenario_idx:03d}",
                    title=f"Candidate: Administrative Route Authorization Boundary ({asset_name})",
                    scenario_type="PRIVILEGE_ESCALATION_RISK",
                    severity="LOW",
                    source_assets=[asset_name],
                    triggering_finding=f"Candidate inference: Administrative surface observed in {sc_loc}; authorization controls require empirical verification",
                    control_weakness="AUTHORIZATION control state is UNVERIFIED (No authorization evidence detected)",
                    trust_boundary_crossed="INTERNET -> PUBLIC_API -> APPLICATION -> DATABASE",
                    attack_path=[
                        f"INTERNET: Attacker targets administrative interface {sc_loc}",
                        "PUBLIC_API: Endpoint exposes administrative operations",
                        "APPLICATION: Authorization controls require empirical runtime or code verification",
                        "DATABASE: Sensitive data access potential depending on unverified controls"
                    ],
                    exposure_signal=f"Unverified administrative interface in {sc_loc}",
                    control_status="AUTHORIZATION control is UNVERIFIED",
                    potential_impact="Potential privilege escalation if authorization is absent (requires verification)",
                    evidence_references=[sc_loc],
                    confidence=0.70,
                    remediation="Audit administrative route dependencies to ensure RequireRole is actively enforced.",
                    scenario_chain={
                        "asset": asset_name,
                        "observation": f"Administrative surface in {sc_loc}",
                        "control_weakness": "AUTHZ-001 is UNVERIFIED",
                        "risk_scenario": "Candidate Authorization Boundary Review",
                        "impact": "Unverified administrative access"
                    },
                    verification_state="CANDIDATE",
                    finding_ref=None,
                ))
                scenario_idx += 1

        # Return inferred scenarios
        logger.info("security_intel.scenarios_inferred", count=len(scenarios))
        return scenarios


risk_scenario_engine = RiskScenarioEngine()
