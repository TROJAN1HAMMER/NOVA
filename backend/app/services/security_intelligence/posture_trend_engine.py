"""
NOVA Security Intelligence — Posture Trend & Delta Engine
Computes deterministic posture score deltas, risk evolution trajectories,
and persists posture snapshots without ML non-determinism.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)


class PostureTrendEngine:
    """Computes deterministic posture deltas, classifies risk evolution, and manages posture history."""

    def compute_delta_and_trend(
        self, current_score: float, previous_score: Optional[float]
    ) -> Tuple[Optional[float], str]:
        """
        Computes delta = current - previous.
        Deterministic classification threshold:
          delta > +1.0  -> IMPROVED
          delta < -1.0  -> DEGRADED
          otherwise     -> UNCHANGED
        If no previous score exists, returns (None, 'FIRST_RUN').
        """
        if previous_score is None:
            return None, "FIRST_RUN"

        delta = round(current_score - previous_score, 1)

        if delta > 1.0:
            trend = "IMPROVED"
        elif delta < -1.0:
            trend = "DEGRADED"
        else:
            trend = "UNCHANGED"

        return delta, trend

    def compute_risk_evolution(
        self, current_assessments: List[Any], previous_assessments: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Classifies risk evolution between consecutive analysis runs:
          NEW_RISK        : Present in current run, missing in previous.
          RESOLVED_RISK   : Present in previous run, missing or marked VERIFIED_FIXED in current.
          PERSISTENT_RISK : Present in both runs with OPEN status.
        """
        if previous_assessments is None:
            return {
                "status": "FIRST_RUN",
                "new_risks_count": len(current_assessments),
                "resolved_risks_count": 0,
                "persistent_risks_count": 0,
                "new_risks": [
                    {
                        "risk_type": getattr(a, "risk_type", "UNKNOWN"),
                        "affected_scope": getattr(a, "affected_scope", "N/A"),
                        "severity": getattr(a, "severity", "MEDIUM"),
                    }
                    for a in current_assessments
                ],
                "resolved_risks": [],
                "persistent_risks": [],
            }

        def _key(a: Any) -> str:
            r_type = getattr(a, "risk_type", "") if not isinstance(a, dict) else a.get("risk_type", "")
            scope = getattr(a, "affected_scope", "") if not isinstance(a, dict) else a.get("affected_scope", "")
            return f"{r_type}::{scope}"

        curr_map = {_key(a): a for a in current_assessments if getattr(a, "status", "OPEN") == "OPEN"}
        prev_map = {_key(a): a for a in previous_assessments if getattr(a, "status", "OPEN") == "OPEN"}

        curr_keys = set(curr_map.keys())
        prev_keys = set(prev_map.keys())

        new_keys = curr_keys - prev_keys
        resolved_keys = prev_keys - curr_keys
        persistent_keys = curr_keys & prev_keys

        def _fmt(a: Any) -> Dict[str, str]:
            if isinstance(a, dict):
                return {
                    "risk_type": a.get("risk_type", "UNKNOWN"),
                    "affected_scope": a.get("affected_scope", "N/A"),
                    "severity": a.get("severity", "MEDIUM"),
                }
            return {
                "risk_type": getattr(a, "risk_type", "UNKNOWN"),
                "affected_scope": getattr(a, "affected_scope", "N/A"),
                "severity": getattr(a, "severity", "MEDIUM"),
            }

        new_risks = [_fmt(curr_map[k]) for k in new_keys]
        resolved_risks = [_fmt(prev_map[k]) for k in resolved_keys]
        persistent_risks = [_fmt(curr_map[k]) for k in persistent_keys]

        return {
            "status": "EVALUATED",
            "new_risks_count": len(new_risks),
            "resolved_risks_count": len(resolved_risks),
            "persistent_risks_count": len(persistent_risks),
            "new_risks": new_risks,
            "resolved_risks": resolved_risks,
            "persistent_risks": persistent_risks,
        }

    def generate_snapshot_record(
        self,
        analysis_run_id: str,
        target_scope: str,
        assets: List[Any],
        controls: List[Any],
        assessments: List[Any],
        previous_snapshot: Optional[Dict[str, Any]] = None,
        previous_assessments: Optional[List[Any]] = None,
        commit_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates a complete posture snapshot dictionary incorporating delta and risk evolution."""
        total_assets = len(assets)
        unresolved_risks = [a for a in assessments if getattr(a, "status", "OPEN") == "OPEN"]

        critical_count = sum(1 for a in unresolved_risks if getattr(a, "severity", "") == "CRITICAL")
        high_count = sum(1 for a in unresolved_risks if getattr(a, "severity", "") == "HIGH")
        medium_count = sum(1 for a in unresolved_risks if getattr(a, "severity", "") == "MEDIUM")
        low_count = sum(1 for a in unresolved_risks if getattr(a, "severity", "") == "LOW")
        verified_fixed_count = sum(1 for a in assessments if getattr(a, "status", "") == "VERIFIED_FIXED")

        present_controls = sum(1 for c in controls if getattr(c, "state", "") == "PRESENT")
        coverage_pct = round((present_controls / max(len(controls), 1)) * 100.0, 1)

        posture_score = round(max(100.0 - (high_count * 15.0) - (critical_count * 25.0) - ((len(controls) - present_controls) * 5.0), 40.0), 1)
        posture_rating = "STRONG" if posture_score >= 80 else ("MODERATE" if posture_score >= 60 else "NEEDS_ATTENTION")

        prev_score = previous_snapshot.get("posture_score") if previous_snapshot else None
        delta_score, trend_direction = self.compute_delta_and_trend(posture_score, prev_score)
        risk_evolution = self.compute_risk_evolution(assessments, previous_assessments)

        snapshot_data = {
            "id": str(uuid.uuid4()),
            "analysis_run_id": analysis_run_id,
            "target_scope": target_scope,
            "commit_hash": commit_hash,
            "posture_score": posture_score,
            "posture_rating": posture_rating,
            "control_coverage_pct": coverage_pct,
            "total_assets_count": total_assets,
            "unresolved_risks_count": len(unresolved_risks),
            "critical_risks_count": critical_count,
            "high_risks_count": high_count,
            "medium_risks_count": medium_count,
            "low_risks_count": low_count,
            "verified_fixed_count": verified_fixed_count,
            "delta_score": delta_score,
            "trend_direction": trend_direction,
            "risk_evolution_summary": risk_evolution,
        }

        logger.info(
            "posture_trend_engine.snapshot_generated",
            analysis_run_id=analysis_run_id,
            posture_score=posture_score,
            delta_score=delta_score,
            trend=trend_direction,
        )
        return snapshot_data


posture_trend_engine = PostureTrendEngine()
