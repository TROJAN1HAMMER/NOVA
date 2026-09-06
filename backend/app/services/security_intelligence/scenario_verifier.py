"""
NOVA Security Intelligence — Scenario Verifier
Verifies risk scenarios (CANDIDATE -> SUPPORTED -> VERIFIED / DISMISSED)
and produces structured, evidence-grounded Security Assessments.
Never fabricates low-severity secret exposure or fake vulnerability findings when code is secure.
"""

import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class VerifiedAssessmentData:
    asset_name: str
    risk_type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    confidence: float
    affected_scope: str
    evidence_chain: List[Dict[str, Any]]
    attack_path: List[str]
    controls_evaluated: List[Dict[str, Any]]
    reasoning: str
    remediation: str
    status: str = "OPEN"  # OPEN, VERIFIED_FIXED, DISMISSED
    code_snippet: Optional[str] = None
    line_number: Optional[int] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    commit_hash: Optional[str] = "head"
    lifecycle_state: str = "ASSESSMENT"
    parent_scenario_ids: List[str] = field(default_factory=list)
    verification_timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    provenance_chain: List[str] = field(default_factory=lambda: ["code_ast_parser", "control_evaluator", "risk_scenario_engine", "scenario_verifier"])
    transition_condition: str = "CONTROLS_CROSS_REFERENCED_AND_VERIFIED"
    cwe_id: str = "CWE-1000"


class ScenarioVerifierService:
    """Verifies inferred risk scenarios against code facts, controls, and scope context."""

    def verify_scenarios(
        self, asset_name: str, location: str, scenarios: List[Any], controls: List[Any], repo_root: Optional[Path] = None
    ) -> List[VerifiedAssessmentData]:
        logger.info("security_intel.verifying_scenarios", asset_name=asset_name, count=len(scenarios))
        assessments: List[VerifiedAssessmentData] = []
        norm_location = normalize_repo_path(location, repo_root)

        for scenario in scenarios:
            f_ref = getattr(scenario, "finding_ref", None)

            if f_ref:
                raw_file = getattr(f_ref, "file_path", location)
                line_no = getattr(f_ref, "line_number", 1)
                norm_file = normalize_repo_path(raw_file, repo_root)
                scope = f"{norm_file}:line {line_no}" if line_no else norm_file

                assessments.append(VerifiedAssessmentData(
                    id=getattr(f_ref, "finding_id", str(uuid.uuid4())),
                    asset_name=asset_name,
                    risk_type=scenario.scenario_type,
                    severity=getattr(f_ref, "severity", getattr(scenario, "severity", "HIGH")).upper(),
                    confidence=getattr(f_ref, "confidence", getattr(scenario, "confidence", 0.92)),
                    affected_scope=scope,
                    code_snippet=getattr(f_ref, "code_snippet", None),
                    line_number=line_no,
                    evidence_chain=[
                        {"type": "observation", "description": scenario.exposure_signal, "snippet": getattr(f_ref, "code_snippet", "")},
                        {"type": "control", "description": scenario.control_status},
                        {"type": "rule", "rule_id": getattr(f_ref, "rule_id", "SEC000"), "cwe": getattr(f_ref, "cwe_id", "CWE-1000")},
                    ],
                    attack_path=scenario.attack_path,
                    controls_evaluated=[{"control": getattr(c, "control_type", ""), "state": getattr(c, "state", "UNKNOWN")} for c in controls],
                    reasoning=getattr(f_ref, "reasoning", f"Verified security risk on {asset_name}."),
                    remediation=getattr(f_ref, "remediation", "Implement proper security controls."),
                    status="OPEN",
                    cwe_id=getattr(f_ref, "cwe_id", "CWE-1000"),
                ))

            elif scenario.scenario_type == "PRIVILEGE_ESCALATION_RISK":
                # Only create open finding if authorization control is NOT present
                authz_control = next((c for c in controls if getattr(c, "control_type", "") == "AUTHORIZATION"), None)
                authz_state = getattr(authz_control, "state", "UNKNOWN") if authz_control else "UNKNOWN"
                if authz_state != "PRESENT":
                    ev_refs = getattr(scenario, "evidence_references", [norm_location])
                    first_ref = ev_refs[0] if ev_refs else norm_location
                    is_candidate = getattr(scenario, "verification_state", "") == "CANDIDATE"
                    status = "CANDIDATE" if is_candidate else "OPEN"
                    reasoning_text = (
                        f"Candidate inference on {asset_name}: Administrative surface lacks verified authorization evidence. Requires confirmation."
                        if is_candidate else
                        f"Verified privilege escalation risk on {asset_name}. Privileged endpoint lacks authorization guard."
                    )
                    assessments.append(VerifiedAssessmentData(
                        asset_name=asset_name,
                        risk_type=scenario.scenario_type,
                        severity=getattr(scenario, "severity", "LOW" if is_candidate else "HIGH").upper(),
                        confidence=getattr(scenario, "confidence", 0.70 if is_candidate else 0.92),
                        affected_scope=first_ref,
                        evidence_chain=[
                            {"type": "observation", "description": scenario.exposure_signal},
                            {"type": "control", "description": scenario.control_status}
                        ],
                        attack_path=scenario.attack_path,
                        controls_evaluated=[{"control": getattr(c, "control_type", ""), "state": getattr(c, "state", "UNKNOWN")} for c in controls],
                        reasoning=reasoning_text,
                        remediation=getattr(scenario, "remediation", "Enforce RequireRole middleware or permission guard on route."),
                        status=status,
                        cwe_id="CWE-285",
                    ))

            elif scenario.scenario_type == "UNPROTECTED_ENDPOINT_RISK":
                auth_control = next((c for c in controls if getattr(c, "control_type", "") == "AUTHENTICATION"), None)
                auth_state = getattr(auth_control, "state", "UNKNOWN") if auth_control else "UNKNOWN"
                if auth_state in ["ABSENT", "PARTIAL"]:
                    ev_refs = getattr(scenario, "evidence_references", [norm_location])
                    first_ref = ev_refs[0] if ev_refs else norm_location
                    assessments.append(VerifiedAssessmentData(
                        asset_name=asset_name,
                        risk_type=scenario.scenario_type,
                        severity=getattr(scenario, "severity", "MEDIUM").upper(),
                        confidence=0.89,
                        affected_scope=first_ref,
                        evidence_chain=[
                            {"type": "observation", "description": scenario.exposure_signal},
                            {"type": "control", "description": scenario.control_status}
                        ],
                        attack_path=scenario.attack_path,
                        controls_evaluated=[{"control": getattr(c, "control_type", ""), "state": getattr(c, "state", "UNKNOWN")} for c in controls],
                        reasoning=f"Unprotected authentication surface on {asset_name}. Endpoint lacks MFA or credential protection.",
                        remediation="Enable multi-factor authentication or strict credential rate limiting.",
                        status="OPEN",
                        cwe_id="CWE-308",
                    ))

        logger.info("security_intel.scenarios_verified", assessments_count=len(assessments))
        return assessments


scenario_verifier = ScenarioVerifierService()
