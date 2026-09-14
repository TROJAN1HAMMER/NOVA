"""
NOVA Architecture Intelligence — Metrics Engine
Calculates defensible coupling metrics (Fan-in, Fan-out, Ca, Ce, Instability, Centrality),
detects circular dependency cycles using Tarjan's SCC algorithm, calculates dependency depth,
and computes class & module cohesion (LCOM4 and God Class/Module heuristic detection).
Strictly separates MEASURED METRIC from HEURISTIC / CANDIDATE.
"""

import ast
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog

from app.services.architecture_intelligence.component_discovery import DiscoveredComponent
from app.services.architecture_intelligence.dependency_extractor import DiscoveredDependency

logger = structlog.get_logger(__name__)


@dataclass
class ComponentMetrics:
    component_id: str
    fan_in: int = 0
    fan_out: int = 0
    afferent_coupling: int = 0  # Ca
    efferent_coupling: int = 0  # Ce
    instability: Optional[float] = None  # I = Ce / (Ca + Ce)
    degree_centrality: float = 0.0
    dependency_depth: int = 0

    # Cohesion
    cohesion_lcom4: Optional[int] = None  # 1 = cohesive, >1 = split candidate, None = not applicable
    cohesion_metric_type: str = "UNAVAILABLE"  # MEASURED METRIC, HEURISTIC, UNAVAILABLE
    is_god_candidate: bool = False
    god_candidate_reasons: List[str] = field(default_factory=list)

    # Circular Dependencies
    in_circular_dependency: bool = False
    circular_cycles: List[List[str]] = field(default_factory=list)


@dataclass
class SystemArchitectureMetrics:
    total_components: int
    total_dependencies: int
    total_circular_cycles: int
    circular_components_count: int
    average_instability: Optional[float]
    max_dependency_depth: int
    god_module_candidates_count: int
    component_metrics: Dict[str, ComponentMetrics] = field(default_factory=dict)
    cycles_detected: List[List[str]] = field(default_factory=list)


class ArchitectureMetricsEngine:
    """Computes coupling, cohesion, circularity, and depth metrics with zero fake data."""

    def compute_all_metrics(
        self,
        components: List[DiscoveredComponent],
        dependencies: List[DiscoveredDependency],
        target_path: str = ".",
    ) -> SystemArchitectureMetrics:
        repo_root = Path(target_path).resolve()
        comp_map = {c.component_id: c for c in components}

        # 1. Build Adjacency Graphs
        outgoing_adj: Dict[str, Set[str]] = defaultdict(set)
        incoming_adj: Dict[str, Set[str]] = defaultdict(set)

        for dep in dependencies:
            if dep.source_id in comp_map and dep.target_id in comp_map:
                outgoing_adj[dep.source_id].add(dep.target_id)
                incoming_adj[dep.target_id].add(dep.source_id)

        # 2. Detect Circular Dependencies (Tarjan's SCC)
        cycles, circular_nodes = self._detect_cycles(outgoing_adj, list(comp_map.keys()))

        # Mark circular dependencies on dependency objects
        cycle_edges = set()
        for cycle in cycles:
            for i in range(len(cycle)):
                u = cycle[i]
                v = cycle[(i + 1) % len(cycle)]
                cycle_edges.add((u, v))

        for dep in dependencies:
            if (dep.source_id, dep.target_id) in cycle_edges:
                dep.is_circular = True

        # 3. Compute Per-Component Coupling & Depth
        results: Dict[str, ComponentMetrics] = {}
        total_comps = len(components)
        depth_memo: Dict[str, int] = {}

        for comp in components:
            cid = comp.component_id
            fan_in = len(incoming_adj[cid])
            fan_out = len(outgoing_adj[cid])

            # Afferent Ca: incoming edges from different files/modules
            ca = sum(
                1 for src_id in incoming_adj[cid]
                if src_id in comp_map and comp_map[src_id].file_path != comp.file_path
            )
            # Efferent Ce: outgoing edges to different files/modules
            ce = sum(
                1 for tgt_id in outgoing_adj[cid]
                if tgt_id in comp_map and comp_map[tgt_id].file_path != comp.file_path
            )

            # Instability I = Ce / (Ca + Ce)
            if (ca + ce) > 0:
                instability = round(ce / (ca + ce), 4)
            else:
                instability = None  # Safely handle isolated components without division errors

            # Degree centrality = (incoming + outgoing) / (2 * (N - 1))
            centrality = (
                round((fan_in + fan_out) / (2 * max(1, total_comps - 1)), 4)
                if total_comps > 1
                else 0.0
            )

            # Node's circular cycles
            node_cycles = [c for c in cycles if cid in c]

            # Dependency depth from this component (max outgoing chain)
            depth = self._compute_depth_from_node(cid, outgoing_adj, memo=depth_memo)

            # Cohesion Analysis (LCOM4 and God Class / Module heuristics)
            lcom, m_type, is_god, god_reasons = self._analyze_cohesion(comp, repo_root, fan_out, ce)

            results[cid] = ComponentMetrics(
                component_id=cid,
                fan_in=fan_in,
                fan_out=fan_out,
                afferent_coupling=ca,
                efferent_coupling=ce,
                instability=instability,
                degree_centrality=centrality,
                dependency_depth=depth,
                cohesion_lcom4=lcom,
                cohesion_metric_type=m_type,
                is_god_candidate=is_god,
                god_candidate_reasons=god_reasons,
                in_circular_dependency=(cid in circular_nodes),
                circular_cycles=node_cycles,
            )

        # 4. System-Wide Aggregates
        valid_instabilities = [m.instability for m in results.values() if m.instability is not None]
        avg_instability = (
            round(sum(valid_instabilities) / len(valid_instabilities), 4)
            if valid_instabilities
            else None
        )
        max_depth = max((m.dependency_depth for m in results.values()), default=0)
        god_count = sum(1 for m in results.values() if m.is_god_candidate)

        return SystemArchitectureMetrics(
            total_components=total_comps,
            total_dependencies=len(dependencies),
            total_circular_cycles=len(cycles),
            circular_components_count=len(circular_nodes),
            average_instability=avg_instability,
            max_dependency_depth=max_depth,
            god_module_candidates_count=god_count,
            component_metrics=results,
            cycles_detected=cycles,
        )

    def _detect_cycles(
        self, adj: Dict[str, Set[str]], nodes: List[str]
    ) -> Tuple[List[List[str]], Set[str]]:
        """Tarjan's strongly connected components algorithm to identify circular cycles (SCCs of size >= 2)."""
        idx = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Set[str] = set()
        stack: List[str] = []
        sccs: List[List[str]] = []

        def strongconnect(v: str):
            nonlocal idx
            indices[v] = idx
            lowlinks[v] = idx
            idx += 1
            stack.append(v)
            on_stack.add(v)

            for w in adj.get(v, set()):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(list(reversed(scc)))

        for node in nodes:
            if node not in indices:
                strongconnect(node)

        circular_nodes = set()
        for scc in sccs:
            circular_nodes.update(scc)

        return sccs, circular_nodes

    def _compute_depth_from_node(
        self,
        start_id: str,
        adj: Dict[str, Set[str]],
        visiting: Optional[Set[str]] = None,
        memo: Optional[Dict[str, int]] = None,
    ) -> int:
        if memo is None:
            memo = {}
        if visiting is None:
            visiting = set()

        if start_id in memo:
            return memo[start_id]
        if start_id in visiting:
            return 0  # avoid infinite loop on circular dependency cycles
        visiting.add(start_id)

        max_child_depth = 0
        for child in adj.get(start_id, set()):
            child_depth = 1 + self._compute_depth_from_node(child, adj, visiting, memo)
            max_child_depth = max(max_child_depth, child_depth)

        visiting.remove(start_id)
        memo[start_id] = max_child_depth
        return max_child_depth

    def _analyze_cohesion(
        self,
        comp: DiscoveredComponent,
        repo_root: Path,
        fan_out: int,
        ce: int,
    ) -> Tuple[Optional[int], str, bool, List[str]]:
        """Computes LCOM4 for classes where AST is available, and identifies God Module/Class candidates."""
        file_path = repo_root / comp.file_path
        if not file_path.is_file():
            return None, "UNAVAILABLE", False, []

        is_god_candidate = False
        god_reasons: List[str] = []

        # 1. Class Cohesion (LCOM4) via Python AST
        if comp.component_type in ("CLASS", "SERVICE", "DATABASE") and comp.language == "python":
            lcom = self._compute_python_class_lcom4(file_path, comp.name)
            metric_type = "MEASURED METRIC" if lcom is not None else "UNAVAILABLE"

            # Check God Class Candidate (Heuristic)
            method_count = comp.attributes.get("method_count", len(comp.members))
            if method_count > 15:
                is_god_candidate = True
                god_reasons.append(f"Excessive method count ({method_count} methods > 15 threshold)")
            if lcom is not None and lcom >= 3:
                is_god_candidate = True
                god_reasons.append(f"High LCOM4 ({lcom} disconnected method groups >= 3)")
            if ce > 10:
                is_god_candidate = True
                god_reasons.append(f"High efferent coupling ({ce} cross-module dependencies)")

            return lcom, metric_type, is_god_candidate, god_reasons

        # 2. Module / File Cohesion Heuristic
        elif comp.component_type in ("MODULE", "PACKAGE"):
            size_bytes = comp.attributes.get("size_bytes", 0)
            # Check God Module Candidate (Heuristic)
            if size_bytes > 30000:  # ~750 lines
                is_god_candidate = True
                god_reasons.append(f"Very large module size ({size_bytes // 1024} KB > 30 KB threshold)")
            if fan_out > 20:
                is_god_candidate = True
                god_reasons.append(f"Excessive outgoing dependencies ({fan_out} > 20 threshold)")

            return None, "HEURISTIC", is_god_candidate, god_reasons

        return None, "UNAVAILABLE", False, []

    def _compute_python_class_lcom4(self, file_path: Path, class_name: str) -> Optional[int]:
        """Calculates LCOM4: number of connected components in the method-attribute access graph."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return None

        target_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                target_class = node
                break

        if not target_class:
            return None

        methods = [
            m for m in target_class.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__")
        ]

        if len(methods) <= 1:
            return 1  # 1 or 0 methods is trivially cohesive

        # Find instance attributes accessed by each method (self.attr)
        method_attrs: Dict[str, Set[str]] = {}
        for m in methods:
            attrs = set()
            for subnode in ast.walk(m):
                if isinstance(subnode, ast.Attribute) and isinstance(subnode.value, ast.Name) and subnode.value.id == "self":
                    attrs.add(subnode.attr)
            method_attrs[m.name] = attrs

        # Build method-method sharing graph
        graph: Dict[str, Set[str]] = {m.name: set() for m in methods}
        method_names = list(graph.keys())
        for i in range(len(method_names)):
            for j in range(i + 1, len(method_names)):
                m1 = method_names[i]
                m2 = method_names[j]
                if method_attrs[m1] & method_attrs[m2]:
                    graph[m1].add(m2)
                    graph[m2].add(m1)

        # Count connected components in graph
        visited = set()
        components_count = 0
        for m in method_names:
            if m not in visited:
                components_count += 1
                queue = deque([m])
                visited.add(m)
                while queue:
                    curr = queue.popleft()
                    for neighbor in graph[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

        return components_count


architecture_metrics_engine = ArchitectureMetricsEngine()
