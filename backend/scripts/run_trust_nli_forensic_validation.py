"""
NOVA — Trust Gate & NLI Forensic Validation Runner
Generates complete empirical measurements for NOVA_TRUST_NLI_VALIDATION.md
"""

import sys
import os
import json
import time
import math
from typing import Dict, List, Any
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai.nli_engine import nli_engine
from app.services.ai.consensus_engine import consensus_engine
from app.services.search_analytics.calibrator import confidence_calibrator


def run_trust_monotonicity() -> List[Dict[str, Any]]:
    agreements = [1.0, 0.9, 0.8, 0.7, 0.5, 0.3, 0.1, 0.0]
    res = []
    for ag in agreements:
        score, c_vec = confidence_calibrator.calibrate(
            retrieval_score=0.85,
            agreement_score=ag,
            citation_coverage=0.85,
            reasoning_score=0.80,
            freshness_score=0.90,
            hallucination_risk=round(1.0 - (0.5*0.85 + 0.3*ag + 0.2*0.85), 4),
            source_reliability=0.95,
            user_feedback_score=0.5,
        )
        dec = confidence_calibrator.evaluate_trust_decision(score, c_vec, min_thresh=0.70, enable_web_fallback=True, is_security_query=True)
        res.append({
            "agreement": ag,
            "hallucination_risk": c_vec["C_hallucination_risk"],
            "trust_score": score,
            "decision": dec["decision"],
        })
    return res


def run_signal_contributions() -> Dict[str, float]:
    c_vec = {
        "C_retrieval": 0.85,
        "C_agreement": 0.90,
        "C_citation": 0.85,
        "C_reasoning": 0.80,
        "C_freshness": 0.90,
        "C_hallucination_risk": 0.10,
        "C_source_reliability": 0.95,
        "C_user_feedback": 0.50,
    }
    contributions = {
        "C_retrieval (w=2.5)": 2.5 * c_vec["C_retrieval"],
        "C_agreement (w=2.0)": 2.0 * c_vec["C_agreement"],
        "C_citation (w=1.5)": 1.5 * c_vec["C_citation"],
        "C_reasoning (w=1.0)": 1.0 * c_vec["C_reasoning"],
        "C_freshness (w=1.0)": 1.0 * c_vec["C_freshness"],
        "C_hallucination_risk (w=-3.0)": -3.0 * c_vec["C_hallucination_risk"],
        "C_source_reliability (w=1.0)": 1.0 * c_vec["C_source_reliability"],
        "C_user_feedback (w=0.5)": 0.5 * c_vec["C_user_feedback"],
        "Bias (w=-2.8)": -2.8,
    }
    contributions["Total_Logit"] = round(sum(contributions.values()), 4)
    contributions["Sigmoid_TrustScore"] = round(1.0 / (1.0 + math.exp(-contributions["Total_Logit"])), 4)
    return contributions


def run_controlled_cases() -> List[Dict[str, Any]]:
    cases = [
        ("1. Strong Support", 0.90, 0.85, 0.85, 0.90, 0.90, 0.05, 0.95, 0.50, True),
        ("2. Weak Support", 0.85, 0.50, 0.50, 0.60, 0.70, 0.30, 0.85, 0.50, False),
        ("3. No Evidence", 0.00, 0.00, 0.00, 0.00, 0.75, 1.00, 0.85, 0.50, False),
        ("4. Unrelated Evidence", 0.85, 0.85, 0.85, 0.80, 0.90, 0.10, 0.95, 0.50, False),
        ("5. Single Contradiction", 0.80, 0.10, 0.70, 0.80, 0.90, 0.40, 0.90, 0.50, False),
        ("6. Multiple Contradictions", 0.80, 0.05, 0.60, 0.80, 0.90, 0.50, 0.90, 0.50, False),
        ("7. Critical Security Contradiction", 0.85, 0.10, 0.85, 0.90, 0.95, 0.40, 0.95, 0.50, True),
        ("8. Mixed Support + Contradiction", 0.85, 0.10, 0.85, 0.90, 0.95, 0.40, 0.95, 0.50, True),
    ]

    out = []
    for name, c_ret, c_agr, c_cit, c_rea, c_fre, c_hal, c_rel, c_fee, is_sec in cases:
        score, c_vec = confidence_calibrator.calibrate(
            retrieval_score=c_ret,
            agreement_score=c_agr,
            citation_coverage=c_cit,
            reasoning_score=c_rea,
            freshness_score=c_fre,
            hallucination_risk=c_hal,
            source_reliability=c_rel,
            user_feedback_score=c_fee,
        )
        dec = confidence_calibrator.evaluate_trust_decision(score, c_vec, min_thresh=0.70, enable_web_fallback=True, is_security_query=is_sec)
        out.append({
            "case": name,
            "c_retrieval": c_ret,
            "c_agreement": c_agr,
            "c_citation": c_cit,
            "c_reasoning": c_rea,
            "c_freshness": c_fre,
            "c_hallucination": c_hal,
            "c_reliability": c_rel,
            "c_feedback": c_fee,
            "trust_score": score,
            "decision": dec["decision"],
            "reasons": dec["reasons"],
        })
    return out


def main():
    print(json.dumps({
        "monotonicity": run_trust_monotonicity(),
        "contributions": run_signal_contributions(),
        "controlled_cases": run_controlled_cases(),
    }, indent=2))


if __name__ == "__main__":
    main()
