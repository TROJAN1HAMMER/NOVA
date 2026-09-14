"""
NOVA Architecture Intelligence — Blast Radius / Impact Analysis Engine
Calculates direct dependents, transitive reachable dependents, dependency depth,
and downstream affected services, endpoints, security findings, controls, risks, and critical assets.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog

from app.services.architecture_intelligence.component_discovery import DiscoveredComponent
from app.services.architecture_intelligence.dependency_extractor import DiscoveredDependency

logger = structlog.get_logger(__name__)


@dataclass
class BlastRadiusReport:
    target_component_id: str
    target_component_name: str
    direct_dependents_count: int
    direct_dependents: List[Dict[str, Any]]
    transitive_dependents_count: int
    transitive_dependents: List[Dict[str, Any]]
    max_impact_depth: int
    affected_endpoints: List[Dict[str, Any]]
    affected_services: List[Dict[str, Any]]
    affected_findings: List[Dict[str, Any]]
    affected_controls: List[Dict[str, Any]]
    affected_scenarios: List[Dict[str, Any]]
    affected_assets: List[Dict[str, Any]]
    risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW


class BlastRadiusEngine:
    """Computes exact dependency blast radius and security propagation."""

    def compute_blast_radius(
        self,
        target_component_id: str,
        components: List[DiscoveredComponent],
        dependencies: List[DiscoveredDependency],
        security_data: Optional[Dict[str, Any]] = None,
    ) -> BlastRadiusReport:
        security_data = security_data or {}
        assessments = security_data.get("assessments", [])
        controls = security_data.get("controls", [])
        assets = security_data.get("assets", [])
        scenarios = security_data.get("scenarios", [])

        comp_map = {c.component_id: c for c in components}
        target_comp = comp_map.get(target_component_id)
        target_name = target_comp.name if target_comp else target_component_id

        # Build reverse dependency graph (incoming edges: who depends on target)
        # If A -> B (A depends on B), then changing B impacts A.
        reverse_adj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for d in dependencies:
            if d.source_id in comp_map and d.target_id in comp_map:
                reverse_adj[d.target_id].append((d.source_id, d.relation_type))

        # 1. Direct Dependents
        direct_entries = reverse_adj.get(target_component_id, [])
        direct_ids = {src_id for src_id, _ in direct_entries}
        direct_dependents: List[Dict[str, Any]] = []
        for src_id, rel in direct_entries:
            c = comp_map[src_id]
            direct_dependents.append({
                "component_id": c.component_id,
                "name": c.name,
                "component_type": c.component_type,
                "file_path": c.file_path,
                "relation_type": rel,
                "relationship": "Direct dependent",
                "hop_depth": 1,
                "path": f"{target_name} -> {c.name}",
            })

        # 2. Transitive Dependents (BFS Traversal)
        transitive_dependents: List[Dict[str, Any]] = []
        visited: Dict[str, int] = {target_component_id: 0}  # node -> hop depth
        paths: Dict[str, List[str]] = {target_component_id: [target_name]}
        queue = deque([(target_component_id, 0)])

        while queue:
            curr_id, curr_depth = queue.popleft()
            for neighbor_id, rel in reverse_adj.get(curr_id, []):
                if neighbor_id not in visited:
                    visited[neighbor_id] = curr_depth + 1
                    c = comp_map.get(neighbor_id)
                    neighbor_name = c.name if c else neighbor_id
                    paths[neighbor_id] = paths[curr_id] + [neighbor_name]
                    if c:
                        transitive_dependents.append({
                            "component_id": c.component_id,
                            "name": c.name,
                            "component_type": c.component_type,
                            "file_path": c.file_path,
                            "hop_depth": curr_depth + 1,
                            "relationship": "Direct dependent" if curr_depth == 0 else "Transitive dependent",
                            "path": " -> ".join(paths[neighbor_id]),
                            "relation_type": rel,
                        })
                    queue.append((neighbor_id, curr_depth + 1))

        max_depth = max(visited.values()) if visited else 0
        all_impacted_ids = set(visited.keys())
        all_impacted_files = {
            comp_map[cid].file_path.strip("./")
            for cid in all_impacted_ids
            if cid in comp_map
        }

        # 3. Categorize Affected Structural Entities
        affected_endpoints: List[Dict[str, Any]] = []
        affected_services: List[Dict[str, Any]] = []

        for cid in all_impacted_ids:
            if cid == target_component_id:
                continue
            c = comp_map.get(cid)
            if not c:
                continue
            if c.component_type == "ENDPOINT":
                affected_endpoints.append({
                    "component_id": c.component_id,
                    "name": c.name,
                    "file_path": c.file_path,
                    "hop_depth": visited[cid],
                })
            elif c.component_type in ("SERVICE", "DATABASE"):
                affected_services.append({
                    "component_id": c.component_id,
                    "name": c.name,
                    "type": c.component_type,
                    "file_path": c.file_path,
                    "hop_depth": visited[cid],
                })

        # 4. Correlate Affected Security Entities
        affected_findings = [
            a for a in assessments
            if any(f in str(a.get("affected_scope", "")).strip("./") for f in all_impacted_files)
        ]
        affected_controls = [
            c for c in controls
            if any(f in str(c.get("scope", "")).strip("./") for f in all_impacted_files)
        ]
        affected_scenarios = [
            sc for sc in scenarios
            if any(any(f in str(ev).strip("./") for f in all_impacted_files) for ev in sc.get("evidence_references", []))
        ]
        affected_assets = [
            ast for ast in assets
            if any(f in str(ast.get("location", "")).strip("./") for f in all_impacted_files)
        ]

        # Determine Risk Level
        total_impact = len(transitive_dependents)
        has_crit_findings = any(f.get("severity") == "CRITICAL" for f in affected_findings)
        has_crit_assets = any(a.get("criticality") == "CRITICAL" for a in affected_assets)

        if has_crit_findings or (total_impact >= 10 and has_crit_assets):
            risk_level = "CRITICAL"
        elif total_impact >= 5 or len(affected_findings) > 0:
            risk_level = "HIGH"
        elif total_impact >= 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return BlastRadiusReport(
            target_component_id=target_component_id,
            target_component_name=target_name,
            direct_dependents_count=len(direct_dependents),
            direct_dependents=direct_dependents,
            transitive_dependents_count=len(transitive_dependents),
            transitive_dependents=transitive_dependents,
            max_impact_depth=max_depth,
            affected_endpoints=affected_endpoints,
            affected_services=affected_services,
            affected_findings=affected_findings,
            affected_controls=affected_controls,
            affected_scenarios=affected_scenarios,
            affected_assets=affected_assets,
            risk_level=risk_level,
        )


blast_radius_engine = BlastRadiusEngine()
