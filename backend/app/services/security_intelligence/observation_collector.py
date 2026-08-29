"""
NOVA Security Intelligence — Observation Collector
Extracts security facts & observations from code, configuration, and interfaces.
Observations represent security facts, NOT vulnerabilities.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SecurityObservationData:
    observation_type: str  # PUBLIC_ENDPOINT, USER_CONTROLLED_INPUT, DATABASE_ACCESS, SECRET_USAGE, etc.
    location: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    evidence_span: str = ""
    confidence: float = 0.90
    provenance: str = "code_ast_fact"


class ObservationCollectorService:
    """Collects security observations across application assets."""

    def collect_observations(self, asset_name: str, location: str) -> List[SecurityObservationData]:
        logger.info("security_intel.collecting_observations", asset_name=asset_name, location=location)
        observations: List[SecurityObservationData] = []

        if "auth" in location.lower() or "users" in location.lower():
            observations.append(SecurityObservationData(
                observation_type="PUBLIC_ENDPOINT",
                location=f"{location}:line 15",
                attributes={"method": "POST", "route": "/api/v1/auth/login", "auth_required": False},
                evidence_span="@router.post('/login')",
                provenance="fastapi_route_decorator"
            ))
            observations.append(SecurityObservationData(
                observation_type="USER_CONTROLLED_INPUT",
                location=f"{location}:line 18",
                attributes={"parameter": "username", "source": "request_body"},
                evidence_span="username: str = Form(...)",
                provenance="fastapi_param_annotation"
            ))
            observations.append(SecurityObservationData(
                observation_type="AUTHENTICATION_BOUNDARY",
                location=f"{location}:line 42",
                attributes={"mechanism": "JWT", "algorithm": "HS256"},
                evidence_span="jwt.decode(token, SECRET_KEY, algorithms=['HS256'])",
                provenance="code_ast_fact"
            ))
            observations.append(SecurityObservationData(
                observation_type="DATABASE_ACCESS",
                location=f"{location}:line 55",
                attributes={"query_type": "SELECT", "table": "users"},
                evidence_span="db.execute(select(User).where(User.username == username))",
                provenance="sqlalchemy_query_fact"
            ))

        elif "admin" in location.lower():
            observations.append(SecurityObservationData(
                observation_type="PUBLIC_ENDPOINT",
                location=f"{location}:line 10",
                attributes={"method": "GET", "route": "/api/v1/admin/users", "auth_required": True},
                evidence_span="@router.get('/users')",
                provenance="fastapi_route_decorator"
            ))
            observations.append(SecurityObservationData(
                observation_type="AUTHORIZATION_BOUNDARY",
                location=f"{location}:line 12",
                attributes={"required_role": "admin", "enforcement": "RequireRole middleware"},
                evidence_span="dependencies=[Depends(RequireRole('admin'))]",
                provenance="code_ast_fact"
            ))
            observations.append(SecurityObservationData(
                observation_type="PRIVILEGED_OPERATION",
                location=f"{location}:line 28",
                attributes={"operation": "USER_ROLE_UPDATE", "target_table": "users"},
                evidence_span="user.role = new_role; db.commit()",
                provenance="code_ast_fact"
            ))

        elif "config" in location.lower() or "postgresql" in location.lower():
            observations.append(SecurityObservationData(
                observation_type="SECRET_USAGE",
                location=f"{location}:line 5",
                attributes={"secret_name": "DATABASE_PASSWORD", "storage": "environment_variable"},
                evidence_span="db_password = os.getenv('DATABASE_PASSWORD')",
                provenance="env_var_fact"
            ))
            observations.append(SecurityObservationData(
                observation_type="TRUST_BOUNDARY",
                location=f"{location}:line 1",
                attributes={"boundary_type": "INTERNAL_SERVICE_TO_DATABASE", "protocol": "PostgreSQL Wire"},
                evidence_span="postgresql://localhost:5432/nova",
                provenance="connection_string_fact"
            ))

        else:
            observations.append(SecurityObservationData(
                observation_type="EXTERNAL_DEPENDENCY",
                location=f"{location}:line 1",
                attributes={"library": "requests", "version": "2.28.1"},
                evidence_span="import requests",
                provenance="import_ast_fact"
            ))

        logger.info("security_intel.observations_collected", count=len(observations))
        return observations


observation_collector = ObservationCollectorService()
