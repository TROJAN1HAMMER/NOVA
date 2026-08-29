"""
NOVA Canonical Demonstration Workflow Test Suite
Location: backend/tests/test_canonical_demo_workflow.py

Verifies the complete end-to-end demo lifecycle:
  Reset -> Vulnerable Analysis -> Contradiction Detection -> Safety Gate Refusal ->
  Remediation Verification -> Temporal Posture Delta -> Clean State Transition
"""

import pytest
from app.demo.orchestrator import demo_orchestrator, DEMO_SCOPE


class TestCanonicalDemoWorkflow:
    """Verifies end-to-end execution of NOVA's canonical demonstration orchestrator."""

    def test_demo_reset_environment(self):
        """Verify resetting demo environment clears history and returns clean baseline."""
        result = demo_orchestrator.reset_demo_environment()
        assert result["status"] == "RESET_SUCCESSFUL"
        assert result["demo_state"] == "STATE_A_VULNERABLE"
        assert result["target_scope"] == DEMO_SCOPE
        assert "vulnerable_analysis" in result

    def test_demo_vulnerable_analysis(self):
        """Verify Security Intelligence analysis on vulnerable demo repository fixture."""
        result = demo_orchestrator.run_vulnerable_analysis()
        assert result["demo_state"] == "STATE_A_VULNERABLE"
        assert len(result["assessments"]) > 0

        assessment = result["assessments"][0]
        assert assessment["risk_type"] == "PRIVILEGE_ESCALATION_RISK"
        assert assessment["severity"] == "HIGH"
        assert assessment["status"] == "OPEN"
        assert "RequireRole" in assessment["remediation"]

    def test_demo_contradiction_detection_and_safety_gate(self):
        """Verify contradictory evidence pair triggers NLI CONTRADICTS and Safety Gate FALLBACK_WEB."""
        pair = demo_orchestrator.get_contradiction_evidence_pair()

        assert pair["evidence_a"]["metadata"]["state"] == "VULNERABLE"
        assert pair["evidence_b"]["metadata"]["state"] == "SAFE"
        assert pair["nli_relationship"]["relationship"] == "CONTRADICTS"
        assert pair["agreement_score"] <= 0.20
        assert pair["policy_trigger"] == "CRITICAL_CONTRADICTION"
        assert pair["decision"] == "FALLBACK_WEB"

        explanation = pair["safety_explanation"]
        assert explanation["policy_trigger"] == "CRITICAL_CONTRADICTION"
        assert explanation["evidence_relationship"] == "CONTRADICTS"

    def test_demo_remediation_verification_and_posture_delta(self):
        """Verify RemediationVerifier patches flaw and updates temporal posture score delta."""
        # Step 1: Baseline vulnerable scan
        demo_orchestrator.run_vulnerable_analysis()

        # Step 2: Apply remediation patch
        remediation = demo_orchestrator.apply_remediation()
        assert remediation["status"] == "REMEDIATION_APPLIED"
        assert remediation["verification_result"]["fixed"] is True
        assert remediation["verification_result"]["status"] == "VERIFIED_FIXED"
        assert remediation["demo_state"] == "STATE_B_REMEDIATED"

        assessment = remediation["assessments"][0]
        assert assessment["status"] == "VERIFIED_FIXED"
        assert assessment["severity"] == "LOW"

        posture = remediation["posture"]
        assert posture["posture_score"] >= 80.0
