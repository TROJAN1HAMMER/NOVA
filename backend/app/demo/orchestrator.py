"""
NOVA Canonical Demonstration Orchestrator
Location: backend/app/demo/orchestrator.py

Orchestrates the canonical, deterministic end-to-end demonstration lifecycle for NOVA:
  Vulnerable Target -> AST Discovery -> Security Observations -> Control Deficit ->
  Risk Scenario -> Verification -> Evidence Fusion -> Pairwise NLI Contradiction ->
  Safety Policy Override -> Remediation Verification -> Posture Delta (ΔS) -> Executive Radar
"""

import os
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
from app.services.security_intelligence.remediation_verifier import remediation_verifier
from app.services.security_intelligence.evidence_provider import SecurityEvidenceProvider
from app.services.ai.nli_engine import NLIEngine
from app.services.search_analytics.calibrator import ConfidenceCalibrator

logger = structlog.get_logger(__name__)

DEMO_SCOPE = "data/demo_repo"
DEMO_VULNERABLE_FILE = "data/demo_repo/admin_transactions.py"
DEMO_REMEDIATED_FILE = "data/demo_repo/remediated_admin_transactions.py"


class CanonicalDemoOrchestrator:
    """Manages resettable demo environment state and orchestrates end-to-end pipeline execution."""

    def __init__(self):
        self._demo_state = "RESET"
        self._current_assessments: List[Dict[str, Any]] = []
        self._latest_posture: Dict[str, Any] = {}
        self._contradiction_active = False

    def reset_demo_environment(self) -> Dict[str, Any]:
        """Resets demo environment records and restores baseline state."""
        logger.info("demo_orchestrator.resetting_environment")

        # Clear demo history in Security Intelligence orchestrator
        if DEMO_SCOPE in security_intelligence_orchestrator._history_store:
            security_intelligence_orchestrator._history_store[DEMO_SCOPE] = []
        if DEMO_SCOPE in security_intelligence_orchestrator._last_assessments:
            security_intelligence_orchestrator._last_assessments[DEMO_SCOPE] = []

        self._demo_state = "STATE_A_VULNERABLE"
        self._contradiction_active = False
        self._current_assessments = []

        # Run initial vulnerable analysis
        vulnerable_result = self.run_vulnerable_analysis()

        return {
            "status": "RESET_SUCCESSFUL",
            "message": "Demo environment reset to baseline vulnerable state.",
            "demo_state": self._demo_state,
            "target_scope": DEMO_SCOPE,
            "vulnerable_analysis": vulnerable_result
        }

    def run_vulnerable_analysis(self) -> Dict[str, Any]:
        """Executes Security Intelligence analysis on the vulnerable demo repository fixture."""
        logger.info("demo_orchestrator.running_vulnerable_analysis")

        # Read vulnerable code snippet
        snippet = ""
        if os.path.exists(DEMO_VULNERABLE_FILE):
            with open(DEMO_VULNERABLE_FILE, "r") as f:
                snippet = f.read()

        # Run Security Intelligence Analysis
        intel_result = security_intelligence_orchestrator.run_full_analysis(DEMO_SCOPE)

        # Inject dedicated demo assessment for admin transaction authorization deficit
        demo_assessment = {
            "id": "DEMO-SEC-001",
            "asset_name": "NOVA Demo Banking API (/admin/transactions)",
            "risk_type": "PRIVILEGE_ESCALATION_RISK",
            "severity": "HIGH",
            "confidence": 0.94,
            "affected_scope": "data/demo_repo/admin_transactions.py:42",
            "evidence_chain": [
                {"type": "observation", "description": "POST /admin/transactions exposes privileged transaction export operation"},
                {"type": "control", "description": "AUTHORIZATION control is ABSENT or UNVERIFIED"}
            ],
            "attack_path": [
                "INTERNET: Attacker issues POST request to /admin/transactions",
                "PUBLIC_API: Endpoint returns customer transaction records",
                "APPLICATION: Authorization middleware RequireRole('admin') is ABSENT",
                "DATABASE: Privileged transaction logs returned without role verification"
            ],
            "controls_evaluated": [{"control": "AUTHORIZATION", "state": "ABSENT"}],
            "reasoning": "Verified privilege escalation risk on /admin/transactions. Endpoint exposes administrative transaction export operation without verified RequireRole('admin') authorization middleware.",
            "remediation": "Enforce RequireRole('admin') dependency on route in data/demo_repo/admin_transactions.py.",
            "status": "OPEN"
        }

        self._current_assessments = [demo_assessment]
        self._demo_state = "STATE_A_VULNERABLE"
        self._latest_posture = intel_result.get("posture", {})

        return {
            "demo_state": self._demo_state,
            "target_scope": DEMO_SCOPE,
            "assessments": self._current_assessments,
            "posture_score": self._latest_posture.get("posture_score", 75.0),
            "posture_rating": "VULNERABLE",
            "security_trend": "FIRST_RUN"
        }

    def get_contradiction_evidence_pair(self) -> Dict[str, Any]:
        """Generates deterministic contradictory evidence pair (Evidence A vs Evidence B)."""
        evidence_a = {
            "source_id": "DEMO-SEC-001",
            "document_id": "DEMO-SEC-001",
            "source_type": "security_finding",
            "title": "Verified Risk Assessment: PRIVILEGE_ESCALATION_RISK",
            "content": "Verified privilege escalation risk on /admin/transactions. POST /admin/transactions does not verify administrator authorization before returning transaction records.",
            "excerpt": "POST /admin/transactions does not verify administrator authorization before returning transaction records.",
            "file_path": "data/demo_repo/admin_transactions.py:42",
            "cwe_id": "CWE-285",
            "score": 0.94,
            "reliability_weight": 0.95,
            "metadata": {
                "provider": "security_intelligence_service",
                "severity": "HIGH",
                "confidence": 0.94,
                "status": "OPEN",
                "security_property": "AUTHORIZATION",
                "state": "VULNERABLE"
            }
        }

        evidence_b = {
            "source_id": "DEMO-KNOW-002",
            "document_id": "DEMO-KNOW-002",
            "source_type": "knowledge_chunk",
            "title": "Banking API Security Architecture Documentation",
            "content": "POST /admin/transactions requires administrator authorization before returning transaction records.",
            "excerpt": "POST /admin/transactions requires administrator authorization before returning transaction records.",
            "file_path": "docs/security_architecture.md:105",
            "cwe_id": "CWE-285",
            "score": 0.92,
            "reliability_weight": 0.90,
            "metadata": {
                "provider": "knowledge_base",
                "security_property": "AUTHORIZATION",
                "state": "SAFE"
            }
        }

        # Evaluate NLI Relationship
        nli_engine = NLIEngine()
        rel = nli_engine.analyze_pair(evidence_a, evidence_b)

        # Evaluate Calibrator & Safety Gate
        calibrator = ConfidenceCalibrator()
        agreement_score = 0.10  # Critical contradiction drops agreement
        trust_score, c_vector = calibrator.calibrate(
            retrieval_score=0.93,
            agreement_score=agreement_score,
            citation_coverage=0.85,
            reasoning_score=0.70,
            freshness_score=0.95,
            hallucination_risk=0.90,
            source_reliability=0.95,
            user_feedback_score=0.50
        )
        trust_eval = {
            "trust_score": trust_score,
            "decision": "FALLBACK_WEB"
        }
        consensus_mat = {
            "contradiction_count": 1,
            "relationships": [
                {
                    "item_a_id": "DEMO-SEC-001",
                    "item_b_id": "DEMO-KNOW-002",
                    "relationship": "CONTRADICTS",
                    "confidence": rel.confidence
                }
            ]
        }

        explanation = calibrator.build_safety_explanation(
            trust_eval=trust_eval,
            c_vector=c_vector,
            consensus_mat=consensus_mat,
            citations=[evidence_a, evidence_b],
            is_security_query=True
        )

        self._contradiction_active = True

        return {
            "evidence_a": evidence_a,
            "evidence_b": evidence_b,
            "nli_relationship": rel.to_dict(),
            "agreement_score": agreement_score,
            "trust_score": trust_eval["trust_score"],
            "policy_trigger": "CRITICAL_CONTRADICTION",
            "decision": "FALLBACK_WEB",
            "safety_explanation": explanation
        }

    def apply_remediation(self) -> Dict[str, Any]:
        """Applies patched authorization snippet and verifies remediation via RemediationVerifierService."""
        logger.info("demo_orchestrator.applying_remediation")

        # Read remediated code snippet
        snippet = ""
        if os.path.exists(DEMO_REMEDIATED_FILE):
            with open(DEMO_REMEDIATED_FILE, "r") as f:
                snippet = f.read()

        # Run Remediation Verifier
        verif_result = remediation_verifier.verify_remediation("DEMO-SEC-001", snippet)

        if verif_result["fixed"]:
            for ass in self._current_assessments:
                if ass["id"] == "DEMO-SEC-001":
                    ass["status"] = "VERIFIED_FIXED"
                    ass["severity"] = "LOW"
                    ass["reasoning"] = "Remediation verified cleanly. RequireRole('admin') authorization dependency detected."

        # Re-run Security Intelligence analysis for state B snapshot
        intel_result_remediated = security_intelligence_orchestrator.run_full_analysis(DEMO_SCOPE)

        self._demo_state = "STATE_B_REMEDIATED"

        return {
            "status": "REMEDIATION_APPLIED",
            "verification_result": verif_result,
            "demo_state": self._demo_state,
            "assessments": self._current_assessments,
            "posture": intel_result_remediated.get("posture", {}),
            "snapshot": intel_result_remediated.get("snapshot", {})
        }

    def get_demo_state_summary(self) -> Dict[str, Any]:
        """Returns current demo environment state summary."""
        return {
            "demo_state": self._demo_state,
            "target_scope": DEMO_SCOPE,
            "contradiction_active": self._contradiction_active,
            "assessments": self._current_assessments,
            "latest_posture": self._latest_posture
        }


demo_orchestrator = CanonicalDemoOrchestrator()
