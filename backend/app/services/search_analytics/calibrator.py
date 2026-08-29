"""
AEKOF — Multi-Dimensional Confidence Calibrator (8-Vector Model)
"""

import math
import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = structlog.get_logger(__name__)

SOURCE_RELIABILITY_WEIGHTS: Dict[str, float] = {
    "faq_axiom": 1.0,
    "security_finding": 0.95,
    "official_doc": 0.95,
    "knowledge_doc": 0.85,
    "user_doc": 0.80,
    "web_search": 0.70,
}


class ConfidenceCalibrator:
    """
    Computes an 8-dimensional confidence vector:
      C = [C_retrieval, C_agreement, C_citation, C_reasoning, C_freshness, C_hallucination, C_reliability, C_feedback]
    and applies Platt scaling calibration into a trust probability P(Correct | C) in [0, 1].
    """

    def compute_freshness(self, dates: List[Optional[datetime]], lambda_decay: float = 0.005) -> float:
        """Calculates exponential time-decay freshness: C_freshness = exp(-lambda * age_days)."""
        valid_dates = [d for d in dates if d is not None]
        if not valid_dates:
            return 0.75  # Neutral prior if no timestamps present

        now = datetime.now(timezone.utc)
        scores = []
        for dt in valid_dates:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max((now - dt).total_seconds() / 86400.0, 0.0)
            scores.append(math.exp(-lambda_decay * age_days))
        return float(sum(scores) / len(scores))

    def compute_source_reliability(self, source_types: List[str]) -> float:
        """Calculates weighted average reliability based on metadata source types."""
        if not source_types:
            return 0.85
        weights = [SOURCE_RELIABILITY_WEIGHTS.get(st.lower(), 0.80) for st in source_types]
        return float(sum(weights) / len(weights))

    def compute_reasoning_score(self, candidate_count: int, top_k: int = 5, plan_complexity: str = "standard") -> float:
        """Computes structural evidence completeness and reasoning support score."""
        if candidate_count == 0:
            return 0.0
        coverage_ratio = min(candidate_count / max(top_k, 1), 1.0)
        complexity_bonus = 0.1 if plan_complexity in {"complex", "deep_analysis"} else 0.05
        return round(min(0.60 + (0.30 * coverage_ratio) + complexity_bonus, 1.0), 4)

    def compute_hallucination_risk(self, retrieval_score: float, agreement_score: float, citation_coverage: float) -> float:
        """Computes evidence support mismatch risk score (lower support -> higher risk)."""
        support_level = (0.5 * retrieval_score) + (0.3 * agreement_score) + (0.2 * citation_coverage)
        return round(min(max(1.0 - support_level, 0.0), 1.0), 4)

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
    ) -> Tuple[float, Dict[str, float]]:
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

    def evaluate_trust_decision(
        self,
        trust_score: float,
        c_vector: Dict[str, float],
        min_thresh: float = 0.70,
        enable_web_fallback: bool = True,
        is_security_query: bool = False,
    ) -> Dict[str, Any]:
        """Evaluates decision gate and produces explainable rationale list with two-stage security safety policy."""
        reasons: List[str] = []

        effective_thresh = max(min_thresh, 0.75) if is_security_query else min_thresh

        if c_vector.get("C_retrieval", 0.0) < 0.35:
            reasons.append("Low retrieval similarity score from vector store.")
        if c_vector.get("C_agreement", 1.0) < 0.50:
            reasons.append("Retrieved evidence chunks exhibit low semantic agreement.")
        if c_vector.get("C_hallucination_risk", 0.0) > 0.40:
            reasons.append("Elevated hallucination risk due to weak evidence alignment.")
        if c_vector.get("C_freshness", 1.0) < 0.50:
            reasons.append("Retrieved source material is aged.")
        if is_security_query and trust_score < effective_thresh:
            reasons.append("Security query evidence confidence below threshold; preventing unverified vulnerability assertion.")

        # Hard Safety Policy Gate for Critical Evidence Contradiction
        has_critical_contradiction = c_vector.get("C_agreement", 1.0) <= 0.20
        if has_critical_contradiction:
            reasons.append("Critical evidence contradiction detected by NLI consensus engine; triggering web search fallback for safety.")

        if trust_score >= effective_thresh and not has_critical_contradiction:
            decision = "GENERATE"
            if reasons:
                decision = "GENERATE_WITH_WARNING"
        elif enable_web_fallback:
            decision = "FALLBACK_WEB"
        else:
            decision = "ABSTAIN"

        return {
            "trust_score": trust_score,
            "confidence_vector": c_vector,
            "decision": decision,
            "reasons": reasons if reasons else ["High confidence evidence alignment confirmed."],
        }


confidence_calibrator = ConfidenceCalibrator()
