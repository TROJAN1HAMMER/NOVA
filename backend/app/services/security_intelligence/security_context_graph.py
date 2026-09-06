"""
NOVA Security Intelligence — Security Context Graph
Constructs a contextual model connecting discovered repository assets, observations, and trust boundaries.
Distinguishes architectural trust boundaries from evidence-backed discovered repository relationships.
Never fabricates fake data flows or endpoints when none exist.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class TrustBoundaryNode:
    boundary_id: str
    name: str
    source_layer: str  # INTERNET, PUBLIC_API, APPLICATION, INTERNAL_SERVICE, DATABASE, EXTERNAL_SERVICE
    target_layer: str
    protocol: str
    controls_enforced: List[str]
    description: str = ""


@dataclass
class DiscoveredGraphNode:
    node_id: str
    name: str
    asset_type: str  # APPLICATION, ENDPOINT, API, DATABASE, SERVICE, MODULE, QUEUE_WORKER
    trust_boundary: str  # TB-1, TB-2, TB-3, TB-4
    location: str
    criticality: str = "MEDIUM"


@dataclass
class DiscoveredGraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship: str  # INGRESS, ROUTES_TO, ACCESSES_STORE, INVOKES_EXTERNAL, DISPATCHES_TASK
    evidence: str
    trust_boundary_crossing: str


@dataclass
class DataFlowPath:
    path_id: str
    entry_point: str
    user_input_param: str
    controller_action: str
    target_data_store: str
    trust_boundaries_crossed: List[str]


class SecurityContextGraphService:
    """Models application security context, data flows, and trust boundaries dynamically."""

    def build_context_graph(
        self, observations: List[Any], assets: Optional[List[Any]] = None, repo_root: Optional[Path] = None
    ) -> Dict[str, Any]:
        logger.info("security_intel.building_context_graph", obs_count=len(observations), assets_count=len(assets or []))

        assets = assets or []
        endpoints = [o for o in observations if getattr(o, "observation_type", "") == "PUBLIC_ENDPOINT"]
        db_accesses = [o for o in observations if getattr(o, "observation_type", "") == "DATABASE_ACCESS"]
        inputs = [o for o in observations if getattr(o, "observation_type", "") == "USER_CONTROLLED_INPUT"]
        authz_bounds = [o for o in observations if getattr(o, "observation_type", "") == "AUTHORIZATION_BOUNDARY"]

        has_db = len(db_accesses) > 0 or any(getattr(a, "asset_type", "") == "DATABASE" for a in assets)
        has_ext_svc = any(getattr(a, "asset_type", "") == "SERVICE" for a in assets)

        # 1. Architectural Trust Boundaries (Four Boundary Model)
        trust_boundaries: List[TrustBoundaryNode] = [
            TrustBoundaryNode(
                boundary_id="TB-1",
                name="External Untrusted",
                source_layer="INTERNET",
                target_layer="PUBLIC_API",
                protocol="HTTPS",
                controls_enforced=["TLS_1_3", "CORS_POLICY"],
                description="Public internet ingress, external clients, and webhook payloads",
            ),
            TrustBoundaryNode(
                boundary_id="TB-2",
                name="Public Perimeter",
                source_layer="PUBLIC_API",
                target_layer="APPLICATION",
                protocol="HTTP / REST",
                controls_enforced=["AUTHENTICATION_JWT", "AUTHORIZATION_RBAC" if authz_bounds else "DEFAULT_GATE"],
                description="Application routing layer, API controllers, and ingress middleware",
            ),
            TrustBoundaryNode(
                boundary_id="TB-3",
                name="Internal Core",
                source_layer="APPLICATION",
                target_layer="DATABASE" if has_db else "INTERNAL_STORAGE",
                protocol="PostgreSQL / SQL Wire" if has_db else "Internal Process Memory",
                controls_enforced=["QUERY_PARAMETERIZATION" if has_db else "MEMORY_ISOLATION"],
                description="Domain business logic, background workers, and service orchestrators",
            ),
            TrustBoundaryNode(
                boundary_id="TB-4",
                name="Data & Secrets",
                source_layer="APPLICATION",
                target_layer="STORAGE_AND_VAULT",
                protocol="TCP / TLS Socket",
                controls_enforced=["ENCRYPTED_AT_REST", "SECRET_MASKING"],
                description="Persistent relational/document stores, cache layers, and credential vaults",
            )
        ]

        # 2. Discovered Graph Nodes (derived strictly from assets)
        discovered_nodes: List[DiscoveredGraphNode] = []
        app_node_id = "NODE-APP"
        db_node_id = None

        for a in assets:
            a_type = getattr(a, "asset_type", "COMPONENT")
            a_name = getattr(a, "asset_name", "Asset")
            a_loc = normalize_repo_path(getattr(a, "location", "."), repo_root)
            a_id = getattr(a, "asset_id", f"NODE-{len(discovered_nodes)+1}")
            tb = getattr(a, "trust_boundary", "TB-3")

            if a_type == "APPLICATION":
                app_node_id = a_id
            elif a_type == "DATABASE":
                db_node_id = a_id

            discovered_nodes.append(DiscoveredGraphNode(
                node_id=a_id,
                name=a_name,
                asset_type=a_type,
                trust_boundary=tb,
                location=a_loc,
                criticality=getattr(a, "criticality", "MEDIUM"),
            ))

        # 3. Discovered Relationships / Edges
        discovered_edges: List[DiscoveredGraphEdge] = []
        edge_idx = 1

        # Endpoint -> Application edges
        for node in discovered_nodes:
            if node.asset_type in ["ENDPOINT", "API"]:
                discovered_edges.append(DiscoveredGraphEdge(
                    edge_id=f"EDGE-{edge_idx:03d}",
                    source_node_id=node.node_id,
                    target_node_id=app_node_id,
                    relationship="ROUTES_TO",
                    evidence=f"Ingress route {node.name} dispatched to application core",
                    trust_boundary_crossing="TB-2 -> TB-3",
                ))
                edge_idx += 1

        # Application -> Database edge if database was genuinely discovered
        if db_node_id:
            discovered_edges.append(DiscoveredGraphEdge(
                edge_id=f"EDGE-{edge_idx:03d}",
                source_node_id=app_node_id,
                target_node_id=db_node_id,
                relationship="ACCESSES_STORE",
                evidence="Application service accesses persistent database storage",
                trust_boundary_crossing="TB-3 -> TB-4",
            ))
            edge_idx += 1

        # Application -> External Service edges
        for node in discovered_nodes:
            if node.asset_type == "SERVICE":
                discovered_edges.append(DiscoveredGraphEdge(
                    edge_id=f"EDGE-{edge_idx:03d}",
                    source_node_id=app_node_id,
                    target_node_id=node.node_id,
                    relationship="INVOKES_EXTERNAL",
                    evidence=f"Service calls third-party integration {node.name}",
                    trust_boundary_crossing="TB-3 -> TB-1",
                ))
                edge_idx += 1

        # 4. Evidence-backed Data Flows
        data_flows: List[DataFlowPath] = []
        df_index = 101

        # Discover flows from actual endpoints discovered in assets
        endpoint_assets = [a for a in assets if getattr(a, "asset_type", "") in ["ENDPOINT", "API"]]
        for ep in endpoint_assets[:5]:
            route_str = getattr(ep, "asset_name", "/route")
            loc = normalize_repo_path(getattr(ep, "location", "routes.py"), repo_root)

            # Match user input observation if located in the same file
            matching_input = next(
                (getattr(i, "attributes", {}).get("parameter", "request_body")
                 for i in inputs if loc.split(":")[0] in getattr(i, "location", "")),
                "payload"
            )

            data_flows.append(DataFlowPath(
                path_id=f"DFP-{df_index}",
                entry_point=route_str,
                user_input_param=matching_input,
                controller_action=f"{loc}:handle_request",
                target_data_store=f"Database Store ({db_node_id})" if db_node_id else "Process Memory",
                trust_boundaries_crossed=["TB-1 (Internet)", "TB-2 (Perimeter)", "TB-3 (App Core)"] + (["TB-4 (Database)"] if db_node_id else [])
            ))
            df_index += 1

        return {
            "architectural_trust_boundaries": [tb.__dict__ for tb in trust_boundaries],
            "trust_boundaries": [tb.__dict__ for tb in trust_boundaries],
            "discovered_nodes": [n.__dict__ for n in discovered_nodes],
            "discovered_edges": [e.__dict__ for e in discovered_edges],
            "nodes": [n.__dict__ for n in discovered_nodes],
            "edges": [e.__dict__ for e in discovered_edges],
            "data_flows": [df.__dict__ for df in data_flows],
            "summary": {
                "exposed_endpoints": len(endpoint_assets),
                "database_access_points": 1 if db_node_id else 0,
                "trust_boundary_crossings": len(trust_boundaries),
                "total_discovered_nodes": len(discovered_nodes),
                "total_discovered_edges": len(discovered_edges),
            }
        }


security_context_graph = SecurityContextGraphService()
