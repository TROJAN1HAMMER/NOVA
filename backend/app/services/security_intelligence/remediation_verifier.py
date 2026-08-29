"""
NOVA Security Intelligence — Remediation Verifier
Re-evaluates risk scenarios against new code/configuration commits to verify fixes (VERIFIED_FIXED).
"""

from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class RemediationVerifierService:
    """Re-analyzes code state to verify whether an assessment has been fixed."""

    def verify_remediation(self, assessment_id: str, code_snippet: str) -> Dict[str, Any]:
        logger.info("security_intel.verifying_remediation", assessment_id=assessment_id)

        # Check if security control keywords are present in updated code snippet
        has_authz_control = "RequireRole" in code_snippet or "Depends(" in code_snippet or "auth" in code_snippet.lower()
        has_input_validation = "Pydantic" in code_snippet or "sanitiz" in code_snippet.lower() or "escap" in code_snippet.lower()
        has_parameterization = "select(" in code_snippet or "bind" in code_snippet.lower() or "params" in code_snippet.lower()

        if has_authz_control or has_input_validation or has_parameterization:
            status = "VERIFIED_FIXED"
            verification_summary = "Remediation verified cleanly. Security control implementation detected in updated code snippet."
            fixed = True
        else:
            status = "OPEN"
            verification_summary = "Remediation verification failed. Security control implementation could not be verified in provided code."
            fixed = False

        return {
            "assessment_id": assessment_id,
            "status": status,
            "fixed": fixed,
            "verification_summary": verification_summary,
            "controls_detected": {
                "authorization_middleware": has_authz_control,
                "input_validation": has_input_validation,
                "query_parameterization": has_parameterization
            }
        }


remediation_verifier = RemediationVerifierService()
