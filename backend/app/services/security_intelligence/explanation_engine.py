"""
NOVA Security Intelligence — Explanation Engine
Generates structured, explainable security answers from assessment evidence.
"""

from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class ExplanationEngine:
    """Produces explainable security assessment summaries."""

    def explain_assessment(self, assessment: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("security_intel.explaining_assessment", assessment_id=assessment.get("id"))

        risk_type = assessment.get("risk_type", "SECURITY_RISK")
        asset_name = assessment.get("asset_name", "Application Asset")
        scope = assessment.get("affected_scope", "backend")
        attack_path = assessment.get("attack_path", [])
        reasoning = assessment.get("reasoning", "")
        remediation = assessment.get("remediation", "")

        return {
            "title": f"Security Assessment: {risk_type}",
            "why_identified": reasoning,
            "assets_involved": [asset_name],
            "affected_scope": scope,
            "risk_path": attack_path,
            "missing_or_weak_controls": [
                c.get("control") for c in assessment.get("controls_evaluated", []) if c.get("state") in ["ABSENT", "PARTIAL"]
            ],
            "remediation_guidance": remediation,
            "explanation_summary": (
                f"Risk '{risk_type}' was identified on asset '{asset_name}' ({scope}). "
                f"{reasoning} "
                f"Remediation Guidance: {remediation}"
            )
        }


explanation_engine = ExplanationEngine()
