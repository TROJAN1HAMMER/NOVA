"""
AEKOF — Multi-Dimensional Confidence Calibrator (8-Vector Model)
"""

import math
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


class ConfidenceCalibrator:
    """
    Computes an 8-dimensional confidence vector:
      C = [C_retrieval, C_agreement, C_citation, C_reasoning, C_freshness, C_hallucination, C_reliability, C_feedback]
    and applies Platt scaling calibration into a trust probability P(Correct | C) in [0, 1].
    """

    def calibrate(
        self,
        retrieval_score: float,
        agreement_score: float = 1.0,
        citation_coverage: float = 1.0,
        reasoning_score: float = 0.9,
        freshness_score: float = 1.0,
        hallucination_risk: float = 0.05,
        source_reliability: float = 0.95,
        user_feedback_score: float = 0.5,
    ) -> tuple[float, dict[str, float]]:
        c_vector = {
            "C_retrieval": round(min(max(retrieval_score, 0.0), 1.0), 4),
            "C_agreement": round(min(max(agreement_score, 0.0), 1.0), 4),
            "C_citation": round(min(max(citation_coverage, 0.0), 1.0), 4),
            "C_reasoning": round(min(max(reasoning_score, 0.0), 1.0), 4),
            "C_freshness": round(min(max(freshness_score, 0.0), 1.0), 4),
            "C_hallucination_risk": round(min(max(hallucination_risk, 0.0), 1.0), 4),
            "C_source_reliability": round(min(max(source_reliability, 0.0), 1.0), 4),
            "C_user_feedback": round(min(max(user_feedback_score, 0.0), 1.0), 4),
        }

        # Weighted logistic combination (Platt scaling)
        logit = (
            2.5 * c_vector["C_retrieval"]
            + 2.0 * c_vector["C_agreement"]
            + 1.5 * c_vector["C_citation"]
            + 1.0 * c_vector["C_reasoning"]
            + 1.0 * c_vector["C_freshness"]
            - 3.0 * c_vector["C_hallucination_risk"]
            + 1.0 * c_vector["C_source_reliability"]
            + 0.5 * c_vector["C_user_feedback"]
            - 2.8
        )
        trust_score = round(1.0 / (1.0 + math.exp(-logit)), 4)
        logger.info("calibrator.computed", trust_score=trust_score, retrieval_score=retrieval_score)
        return trust_score, c_vector


confidence_calibrator = ConfidenceCalibrator()
