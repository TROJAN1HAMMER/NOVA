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

    def build_safety_explanation(
        self,
        trust_eval: Dict[str, Any],
        c_vector: Dict[str, float],
        consensus_mat: Optional[Dict[str, Any]] = None,
        citations: Optional[List[Any]] = None,
        is_security_query: bool = False,
    ) -> Dict[str, Any]:
        """Generates structured safety gate explanation detailing policy triggers and contradictory evidence."""
        decision = trust_eval.get("decision", "GENERATE")
        trust_score = trust_eval.get("trust_score", 1.0)
        agreement_score = c_vector.get("C_agreement", 1.0)
        retrieval_score = c_vector.get("C_retrieval", 1.0)

        consensus_mat = consensus_mat or {}
        citations = citations or []

        contradiction_count = consensus_mat.get("contradiction_count", 0)
        relationships = consensus_mat.get("relationships", [])

        contradicting_pairs = [r for r in relationships if r.get("relationship") == "CONTRADICTS"]

        # Policy Trigger Identification
        if contradiction_count > 0 or agreement_score <= 0.20:
            policy_trigger = "CRITICAL_CONTRADICTION"
            reason = "Conflicting security evidence detected."
        elif is_security_query and trust_score < 0.75:
            policy_trigger = "SECURITY_QUERY_LOW_CONFIDENCE"
            reason = "Security query evidence confidence below threshold."
        elif retrieval_score < 0.35:
            policy_trigger = "LOW_RETRIEVAL_SIMILARITY"
            reason = "Low retrieval similarity score from vector store."
        elif trust_score < 0.70:
            policy_trigger = "CONFIDENCE_THRESHOLD_OVERRIDE"
            reason = "Overall trust score below minimum safety threshold."
        else:
            policy_trigger = "NORMAL_CONFIRMED"
            reason = "Answer generated from trusted evidence."

        # Map Citations for Quick Evidence Lookup
        cit_map = {}
        for c in citations:
            doc_id = getattr(c, "document_id", None) or getattr(c, "source_id", None) or (c.get("document_id") if isinstance(c, dict) else None)
            if doc_id:
                cit_map[doc_id] = c

        def _format_ev(item: Any, default_id: str, default_excerpt: str = "") -> Dict[str, Any]:
            if isinstance(item, dict):
                src_id = item.get("source_id") or item.get("document_id") or default_id
                src_type = item.get("source_type", "security_finding")
                filename = item.get("filename") or item.get("title") or src_id
                file_path = item.get("file_path")
                line_number = item.get("line_number")
                cwe_id = item.get("cwe_id")
                cve = item.get("cve")
                severity = item.get("severity")
                excerpt = item.get("excerpt") or item.get("content") or default_excerpt
            elif hasattr(item, "document_id"):
                src_id = getattr(item, "document_id", default_id)
                src_type = getattr(item, "source_type", "knowledge_doc")
                filename = getattr(item, "filename", src_id)
                file_path = getattr(item, "file_path", None)
                line_number = getattr(item, "line_number", None)
                cwe_id = getattr(item, "cwe_id", None)
                cve = getattr(item, "cve", None)
                severity = getattr(item, "severity", None)
                excerpt = getattr(item, "excerpt", default_excerpt)
            else:
                src_id = default_id
                src_type = "unknown"
                filename = default_id
                file_path = None
                line_number = None
                cwe_id = None
                cve = None
                severity = None
                excerpt = default_excerpt

            sec_prop = "GENERAL_SECURITY"
            exc_lower = (excerpt or "").lower()
            if "auth" in exc_lower or "login" in exc_lower or "token" in exc_lower:
                sec_prop = "AUTHORIZATION_AUTHENTICATION"
            elif "sql" in exc_lower or "query" in exc_lower or "database" in exc_lower:
                sec_prop = "INPUT_VALIDATION_SQLI"
            elif "crypto" in exc_lower or "cipher" in exc_lower or "key" in exc_lower:
                sec_prop = "CRYPTOGRAPHY"

            return {
                "source_id": src_id,
                "source_type": src_type,
                "filename": filename,
                "file_path": file_path,
                "line_number": line_number,
                "cwe_id": cwe_id,
                "cve": cve,
                "severity": severity,
                "security_property": sec_prop,
                "excerpt": (excerpt[:200] + "...") if len(excerpt) > 200 else excerpt,
            }

        # Build Contradicting Evidence Pair
        contradicting_evidence = []
        evidence_relationship = "RELATED"
        nli_confidence = 0.0

        if contradicting_pairs:
            c_pair = contradicting_pairs[0]
            evidence_relationship = "CONTRADICTS"
            nli_confidence = float(c_pair.get("confidence", 0.85))

            id_a = c_pair.get("item_a_id", "Evidence_A")
            id_b = c_pair.get("item_b_id", "Evidence_B")

            ev_a = cit_map.get(id_a)
            ev_b = cit_map.get(id_b)

            contradicting_evidence.append(_format_ev(ev_a, id_a, c_pair.get("item_a_excerpt", "")))
            contradicting_evidence.append(_format_ev(ev_b, id_b, c_pair.get("item_b_excerpt", "")))

        supporting_evidence = [_format_ev(c, f"doc-{i}") for i, c in enumerate(citations)]

        if policy_trigger == "CRITICAL_CONTRADICTION":
            if len(contradicting_evidence) >= 2:
                e1, e2 = contradicting_evidence[0], contradicting_evidence[1]
                loc1 = f"{e1['file_path']}:{e1['line_number']}" if e1.get("file_path") else e1["filename"]
                loc2 = f"{e2['file_path']}:{e2['line_number']}" if e2.get("file_path") else e2["filename"]
                explanation_text = (
                    f"Two evidence items ({loc1} and {loc2}) assert incompatible security states with NLI confidence {nli_confidence:.2f}. "
                    f"Although retrieval score ({retrieval_score:.2f}) and source reliability are strong, the safety policy overrides "
                    f"generation because the evidence agreement score ({agreement_score:.2f}) fell below the contradiction threshold (0.20)."
                )
            else:
                explanation_text = (
                    f"Conflicting security evidence detected by NLI consensus engine (agreement score {agreement_score:.2f}). "
                    f"The Two-Stage Safety Policy Gate overrode text generation to prevent unverified vulnerability assertions."
                )
        elif policy_trigger == "SECURITY_QUERY_LOW_CONFIDENCE":
            explanation_text = (
                f"Security query evidence confidence ({trust_score:.2f}) fell below the required threshold (0.75). "
                f"Output downgraded to web search fallback to prevent unverified security assertion."
            )
        elif policy_trigger == "LOW_RETRIEVAL_SIMILARITY":
            explanation_text = f"Vector retrieval similarity ({retrieval_score:.2f}) was insufficient to ensure evidence grounding."
        elif policy_trigger == "CONFIDENCE_THRESHOLD_OVERRIDE":
            explanation_text = f"Overall trust score ({trust_score:.2f}) was below the minimum safety policy threshold (0.70)."
        else:
            explanation_text = (
                f"Answer generated from trusted evidence. Evidence agreement ({agreement_score:.2f}) "
                f"and trust score ({trust_score:.2f}) satisfy safety policy constraints."
            )

        return {
            "decision": decision,
            "reason": reason,
            "policy_trigger": policy_trigger,
            "trust_score": trust_score,
            "agreement_score": agreement_score,
            "contradiction_count": contradiction_count,
            "supporting_evidence": supporting_evidence,
            "contradicting_evidence": contradicting_evidence,
            "evidence_relationship": evidence_relationship,
            "nli_confidence": nli_confidence,
            "explanation": explanation_text,
        }


confidence_calibrator = ConfidenceCalibrator()
