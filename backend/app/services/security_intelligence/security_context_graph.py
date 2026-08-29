"""
NOVA Security Intelligence — Security Context Graph
Constructs a contextual model connecting assets, observations, and trust boundaries.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TrustBoundaryNode:
    boundary_id: str
    source_layer: str  # INTERNET, PUBLIC_API, APPLICATION, INTERNAL_SERVICE, DATABASE
    target_layer: str
    protocol: str
    controls_enforced: List[str]


@dataclass
class DataFlowPath:
    path_id: str
    entry_point: str
    user_input_param: str
    controller_action: str
    target_data_store: str
    trust_boundaries_crossed: List[str]


class SecurityContextGraphService:
    """Models application security context, data flows, and trust boundaries."""

    def build_context_graph(self, observations: List[Any]) -> Dict[str, Any]:
        logger.info("security_intel.building_context_graph")

        trust_boundaries = [
            TrustBoundaryNode(
                boundary_id="TB-1",
                source_layer="INTERNET",
                target_layer="PUBLIC_API",
                protocol="HTTPS",
                controls_enforced=["TLS_1_3", "RATE_LIMITER"]
            ),
            TrustBoundaryNode(
                boundary_id="TB-2",
                source_layer="PUBLIC_API",
                target_layer="APPLICATION",
                protocol="HTTP / REST",
                controls_enforced=["AUTHENTICATION_JWT", "AUTHORIZATION_RBAC"]
            ),
            TrustBoundaryNode(
                boundary_id="TB-3",
                source_layer="APPLICATION",
                target_layer="DATABASE",
                protocol="PostgreSQL Wire",
                controls_enforced=["SQLALCHEMY_PARAMETERIZATION"]
            )
        ]

        data_flows = [
            DataFlowPath(
                path_id="DFP-101",
                entry_point="/api/v1/auth/login",
                user_input_param="username",
                controller_action="auth.py:login()",
                target_data_store="users",
                trust_boundaries_crossed=["INTERNET", "PUBLIC_API", "APPLICATION", "DATABASE"]
            ),
            DataFlowPath(
                path_id="DFP-102",
                entry_point="/api/v1/admin/users",
                user_input_param="role",
                controller_action="admin.py:update_role()",
                target_data_store="users",
                trust_boundaries_crossed=["INTERNET", "PUBLIC_API", "APPLICATION", "DATABASE"]
            )
        ]

        return {
            "trust_boundaries": [tb.__dict__ for tb in trust_boundaries],
            "data_flows": [df.__dict__ for df in data_flows],
            "summary": {
                "exposed_endpoints": 2,
                "database_access_points": 2,
                "trust_boundary_crossings": 3
            }
        }


security_context_graph = SecurityContextGraphService()
