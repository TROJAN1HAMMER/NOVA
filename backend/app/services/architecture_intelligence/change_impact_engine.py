"""
NOVA Architecture Intelligence — Change Impact Engine
Evaluates structural, dependency, and security impact of changed files / git commits.
Non-mandatory: repositories without git metadata scan successfully with a graceful "Git metadata unavailable" response.
"""

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import structlog

from app.services.architecture_intelligence.blast_radius_engine import blast_radius_engine
from app.services.architecture_intelligence.component_discovery import DiscoveredComponent
from app.services.architecture_intelligence.dependency_extractor import DiscoveredDependency

logger = structlog.get_logger(__name__)


@dataclass
class ChangeImpactReport:
    git_available: bool
    commit_ref: Optional[str] = None
    changed_files: List[str] = field(default_factory=list)
    changed_components: List[Dict[str, Any]] = field(default_factory=list)
    impacted_components_count: int = 0
    impacted_components: List[Dict[str, Any]] = field(default_factory=list)
    affected_endpoints: List[Dict[str, Any]] = field(default_factory=list)
    affected_services: List[Dict[str, Any]] = field(default_factory=list)
    affected_findings: List[Dict[str, Any]] = field(default_factory=list)
    affected_controls: List[Dict[str, Any]] = field(default_factory=list)
    affected_scenarios: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""


class ChangeImpactEngine:
    """Analyzes impact of modified files across the architecture graph."""

    def analyze_change_impact(
        self,
        target_path: str = ".",
        changed_files: Optional[List[str]] = None,
        commit_ref: Optional[str] = None,
        components: Optional[List[DiscoveredComponent]] = None,
        dependencies: Optional[List[DiscoveredDependency]] = None,
        security_data: Optional[Dict[str, Any]] = None,
    ) -> ChangeImpactReport:
        components = components or []
        dependencies = dependencies or []
        repo_root = Path(target_path).resolve()

        # 1. Resolve Changed Files
        resolved_files = list(changed_files) if changed_files else []
        git_available = True

        if not resolved_files:
            try:
                # Check if repo_root is a git repository
                if (repo_root / ".git").exists():
                    res = subprocess.run(
                        ["git", "diff", "--name-only", "HEAD~1"],
                        cwd=str(repo_root),
                        capture_output=True,
                        text=True,
                        timeout=5.0,
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        resolved_files = [f.strip() for f in res.stdout.strip().splitlines() if f.strip()]
                    else:
                        # Fallback to status (uncommitted changes)
                        st_res = subprocess.run(
                            ["git", "status", "--porcelain"],
                            cwd=str(repo_root),
                            capture_output=True,
                            text=True,
                            timeout=5.0,
                        )
                        if st_res.returncode == 0:
                            for line in st_res.stdout.strip().splitlines():
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    resolved_files.append(parts[-1])
                else:
                    git_available = False
            except Exception:
                git_available = False

        if not git_available and not resolved_files:
            return ChangeImpactReport(
                git_available=False,
                message="Git metadata unavailable for this workspace. File-level change impact cannot be determined.",
            )

        if not resolved_files:
            return ChangeImpactReport(
                git_available=True,
                commit_ref=commit_ref or "HEAD",
                changed_files=[],
                message="No modified files detected in the current commit or working tree.",
            )

        # 2. Map Changed Files to Components
        comp_map = {c.component_id: c for c in components}
        changed_comps: List[DiscoveredComponent] = []

        for f in resolved_files:
            f_norm = f.strip("./")
            for c in components:
                if c.file_path.strip("./") == f_norm:
                    changed_comps.append(c)

        # 3. Compute Downstream Blast Radius for each changed component
        aggregated_impacted_ids: Set[str] = set()
        affected_endpoints: List[Dict[str, Any]] = []
        affected_services: List[Dict[str, Any]] = []
        affected_findings: List[Dict[str, Any]] = []
        affected_controls: List[Dict[str, Any]] = []
        affected_scenarios: List[Dict[str, Any]] = []

        for cc in changed_comps:
            report = blast_radius_engine.compute_blast_radius(
                target_component_id=cc.component_id,
                components=components,
                dependencies=dependencies,
                security_data=security_data,
            )
            for td in report.transitive_dependents:
                aggregated_impacted_ids.add(td["component_id"])
            affected_endpoints.extend(report.affected_endpoints)
            affected_services.extend(report.affected_services)
            affected_findings.extend(report.affected_findings)
            affected_controls.extend(report.affected_controls)
            affected_scenarios.extend(report.affected_scenarios)

        impacted_comps_list = [
            {
                "component_id": cid,
                "name": comp_map[cid].name,
                "type": comp_map[cid].component_type,
                "file_path": comp_map[cid].file_path,
            }
            for cid in aggregated_impacted_ids
            if cid in comp_map
        ]

        return ChangeImpactReport(
            git_available=True,
            commit_ref=commit_ref or "HEAD",
            changed_files=resolved_files,
            changed_components=[
                {"component_id": c.component_id, "name": c.name, "file_path": c.file_path}
                for c in changed_comps
            ],
            impacted_components_count=len(impacted_comps_list),
            impacted_components=impacted_comps_list,
            affected_endpoints=affected_endpoints,
            affected_services=affected_services,
            affected_findings=affected_findings,
            affected_controls=affected_controls,
            affected_scenarios=affected_scenarios,
            message=f"Change impacts {len(changed_comps)} component(s) and ripples to {len(impacted_comps_list)} downstream dependent(s).",
        )


change_impact_engine = ChangeImpactEngine()
