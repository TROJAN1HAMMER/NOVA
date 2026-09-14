"""
NOVA Architecture Intelligence — Architecture Drift Engine
Compares current architecture snapshot with a previous baseline snapshot to detect:
added dependencies, removed dependencies, new circular dependencies, coupling/cohesion deltas,
and architectural boundary violations.
Strictly requires real baseline; if only one scan exists, returns "Baseline unavailable".
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ArchitectureDriftReport:
    baseline_available: bool
    message: str
    status: str  # NO_PREVIOUS_SNAPSHOT, STABLE, DEGRADED, IMPROVED
    previous_snapshot_id: Optional[str] = None
    current_snapshot_id: Optional[str] = None
    added_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    removed_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    new_circular_cycles: List[List[str]] = field(default_factory=list)
    resolved_circular_cycles: List[List[str]] = field(default_factory=list)
    increased_coupling_components: List[Dict[str, Any]] = field(default_factory=list)
    new_god_candidates: List[str] = field(default_factory=list)
    boundary_violations: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


class ArchitectureDriftEngine:
    """Detects structural and architectural drift between real snapshots."""

    def compare_snapshots(
        self,
        current_data: Dict[str, Any],
        previous_data: Optional[Dict[str, Any]] = None,
    ) -> ArchitectureDriftReport:
        if not previous_data:
            return ArchitectureDriftReport(
                baseline_available=False,
                message="Baseline unavailable",
                status="NO_PREVIOUS_SNAPSHOT",
            )

        curr_id = current_data.get("snapshot_id") or current_data.get("scan_id", "current")
        prev_id = previous_data.get("snapshot_id") or previous_data.get("scan_id", "previous")

        curr_deps = current_data.get("dependencies", [])
        prev_deps = previous_data.get("dependencies", [])

        curr_dep_set = {
            (d.get("source_id"), d.get("target_id"), d.get("relation_type")) for d in curr_deps
        }
        prev_dep_set = {
            (d.get("source_id"), d.get("target_id"), d.get("relation_type")) for d in prev_deps
        }

        # 1. Added & Removed Dependencies
        added_edges = curr_dep_set - prev_dep_set
        removed_edges = prev_dep_set - curr_dep_set

        added_dependencies = [
            {"source_id": s, "target_id": t, "relation_type": r} for s, t, r in added_edges
        ]
        removed_dependencies = [
            {"source_id": s, "target_id": t, "relation_type": r} for s, t, r in removed_edges
        ]

        # 2. Circular Dependencies Delta
        curr_cycles = [tuple(c) for c in current_data.get("cycles_detected", [])]
        prev_cycles = [tuple(c) for c in previous_data.get("cycles_detected", [])]

        new_cycles = [list(c) for c in (set(curr_cycles) - set(prev_cycles))]
        resolved_cycles = [list(c) for c in (set(prev_cycles) - set(curr_cycles))]

        # 3. Coupling & Cohesion Deltas
        curr_metrics = current_data.get("metrics", {}).get("component_metrics", {})
        prev_metrics = previous_data.get("metrics", {}).get("component_metrics", {})

        increased_coupling: List[Dict[str, Any]] = []
        new_god_candidates: List[str] = []

        for cid, cm in curr_metrics.items():
            pm = prev_metrics.get(cid)
            if pm:
                curr_ce = cm.get("efferent_coupling", 0)
                prev_ce = pm.get("efferent_coupling", 0)
                if curr_ce > prev_ce:
                    increased_coupling.append({
                        "component_id": cid,
                        "previous_ce": prev_ce,
                        "current_ce": curr_ce,
                        "delta_ce": curr_ce - prev_ce,
                    })

                if cm.get("is_god_candidate") and not pm.get("is_god_candidate"):
                    new_god_candidates.append(cid)

        # 4. Architectural Boundary Violations
        # e.g. An endpoint or frontend component directly accessing a database bypassing services
        boundary_violations: List[Dict[str, Any]] = []
        for s, t, r in added_edges:
            s_lower = str(s).lower()
            t_lower = str(t).lower()
            if ("ep-" in s_lower or "endpoint" in s_lower or "view" in s_lower) and ("database" in t_lower or "db-" in t_lower):
                boundary_violations.append({
                    "type": "PRESENTATION_TO_DATABASE_BYPASS",
                    "source": s,
                    "target": t,
                    "description": "Endpoint directly accesses database without intervening domain service.",
                })

        # Overall Status
        if new_cycles or boundary_violations or len(new_god_candidates) > 0:
            status = "DEGRADED"
            msg = f"Architecture drift detected: {len(new_cycles)} new circular cycle(s), {len(added_dependencies)} added edge(s)."
        elif resolved_cycles and not new_cycles:
            status = "IMPROVED"
            msg = f"Architecture improved: {len(resolved_cycles)} circular cycle(s) eliminated."
        else:
            status = "STABLE"
            msg = f"Architecture stable with {len(added_dependencies)} added and {len(removed_dependencies)} removed dependency edges."

        return ArchitectureDriftReport(
            baseline_available=True,
            message=msg,
            status=status,
            previous_snapshot_id=str(prev_id),
            current_snapshot_id=str(curr_id),
            added_dependencies=added_dependencies,
            removed_dependencies=removed_dependencies,
            new_circular_cycles=new_cycles,
            resolved_circular_cycles=resolved_cycles,
            increased_coupling_components=increased_coupling,
            new_god_candidates=new_god_candidates,
            boundary_violations=boundary_violations,
            summary={
                "added_dependencies_count": len(added_dependencies),
                "removed_dependencies_count": len(removed_dependencies),
                "new_circular_cycles_count": len(new_cycles),
                "resolved_circular_cycles_count": len(resolved_cycles),
                "increased_coupling_count": len(increased_coupling),
                "boundary_violations_count": len(boundary_violations),
            },
        )


architecture_drift_engine = ArchitectureDriftEngine()
