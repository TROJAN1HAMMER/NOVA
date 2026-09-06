"""
NOVA Security Intelligence — Independent Asset Discovery Engine
Discovers real repositories, applications, services, APIs, endpoints, modules, and database assets
from actual repository files and structure without static hardcoded mocks or path leaks.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.repository_ingestion import repository_ingestion_service
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)

BINARY_MODEL_EXTENSIONS = {
    ".pkl", ".pickle", ".onnx", ".pt", ".pth", ".h5", ".bin",
    ".joblib", ".safetensors", ".weights", ".pb", ".tflite", ".mlmodel"
}


@dataclass
class DiscoveredAsset:
    asset_name: str
    asset_type: str  # REPOSITORY, APPLICATION, SERVICE, API, ENDPOINT, DATABASE, MODULE, QUEUE_WORKER
    criticality: str  # CRITICAL, HIGH, MEDIUM, LOW
    owner: str
    location: str  # Strictly repository-relative path (e.g. '.', 'src/app.py', 'backend/db.py')
    asset_id: str = ""
    trust_boundary: str = "TB-3"  # TB-1 External, TB-2 Public Perimeter, TB-3 Internal Core, TB-4 Data & Secrets
    confidence: float = 0.90
    attributes: Dict[str, Any] = field(default_factory=dict)


class AssetDiscoveryService:
    """Discovers application assets, APIs, endpoints, data stores, and services from actual repository structure."""

    def discover_assets(self, target_path: str = ".") -> List[DiscoveredAsset]:
        logger.info("security_intel.asset_discovery_started", target_path=target_path)
        assets: List[DiscoveredAsset] = []

        repo_root = Path(target_path).resolve()
        if not repo_root.exists():
            logger.warning("asset_discovery.target_path_not_found", target_path=target_path)
            return assets

        # Enumerate repository files
        repo_info = repository_ingestion_service.enumerate_repository_files(repo_root)
        files = repo_info.get("files", [])
        languages = repo_info.get("languages", {})
        manifests = repo_info.get("manifests", [])

        # 1. Primary Application Asset
        primary_lang = max(languages, key=languages.get) if languages else "Generic"
        framework = self._detect_framework(repo_root, files)
        app_name = repo_root.name if repo_root.name not in [".", "source"] else "Application Core"
        # If folder name has github prefix like TROJAN1HAMMER-repo-commit, clean it
        if "-" in app_name and len(app_name) > 15:
            parts = app_name.split("-")
            if len(parts) >= 2:
                app_name = parts[1]

        assets.append(DiscoveredAsset(
            asset_id=f"AST-APP-{app_name.lower().replace(' ', '-')}",
            asset_name=f"{app_name} ({framework or primary_lang})",
            asset_type="APPLICATION",
            criticality="CRITICAL",
            owner="Engineering Team",
            location=".",
            trust_boundary="TB-3",
            confidence=0.98,
            attributes={
                "framework": framework or "Standard",
                "primary_language": primary_lang,
                "total_source_files": repo_info.get("total_files", 0),
                "manifests": manifests,
            }
        ))

        # 2. Discover API Surfaces & Routers
        discovered_apis = self._discover_api_surfaces(repo_root, files)
        for api in discovered_apis:
            assets.append(api)

        # 3. Discover Database / Storage Assets
        discovered_dbs = self._discover_databases(repo_root, files)
        for db in discovered_dbs:
            assets.append(db)

        # 4. Discover External Integrations & Services
        discovered_services = self._discover_services(repo_root, files)
        for svc in discovered_services:
            assets.append(svc)

        # 5. Discover Security-Relevant Modules
        discovered_modules = self._discover_security_modules(repo_root, files)
        for mod in discovered_modules:
            assets.append(mod)

        # 6. Discover Queues / Workers
        discovered_workers = self._discover_workers(repo_root, files)
        for worker in discovered_workers:
            assets.append(worker)

        logger.info("security_intel.asset_discovery_completed", count=len(assets))
        return assets

    def _detect_framework(self, root: Path, files: List[str]) -> Optional[str]:
        for f in files:
            f_lower = f.lower()
            if "fastapi" in f_lower or f.endswith("main.py") or f.endswith("app.py"):
                try:
                    p = root / f
                    if p.is_file():
                        content = p.read_text(encoding="utf-8", errors="ignore")[:3000]
                        if "FastAPI" in content:
                            return "FastAPI"
                        if "Flask" in content:
                            return "Flask"
                        if "django" in content.lower():
                            return "Django"
                except Exception:
                    pass
            if "package.json" in f_lower:
                try:
                    p = root / f
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if "express" in content:
                        return "Express.js"
                    if "next" in content:
                        return "Next.js"
                    if "react" in content:
                        return "React"
                except Exception:
                    pass
            if "pom.xml" in f_lower or "build.gradle" in f_lower:
                return "Spring Boot"
        return None

    def _discover_api_surfaces(self, root: Path, files: List[str]) -> List[DiscoveredAsset]:
        apis: List[DiscoveredAsset] = []
        route_patterns = ["api/", "routes/", "controllers/", "endpoints/", "routers/"]

        for f in files:
            f_lower = f.lower()
            # Skip binary files
            if Path(f).suffix.lower() in BINARY_MODEL_EXTENSIONS:
                continue

            is_candidate_file = (
                any(rp in f_lower for rp in route_patterns)
                or f_lower.endswith(("router.py", "routes.py", "routes.ts", "routes.js", "controller.java", "main.py", "app.py", "server.py"))
            )
            if not is_candidate_file:
                continue

            file_path = root / f
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                # Look for FastAPI / Flask route decorators e.g. @app.get('/predict'), @router.post('/users')
                decorator_routes = re.findall(
                    r"""@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]""",
                    content,
                    re.IGNORECASE,
                )
                if decorator_routes:
                    rel_loc = normalize_repo_path(f, root)
                    for method, route_path in decorator_routes[:4]:
                        is_admin = "admin" in route_path.lower()
                        is_auth = "auth" in route_path.lower() or "login" in route_path.lower()
                        route_name = f"{method.upper()} {route_path}"
                        apis.append(DiscoveredAsset(
                            asset_id=f"AST-EP-{method.upper()}-{route_path.strip('/').replace('/', '-') or 'root'}",
                            asset_name=route_name,
                            asset_type="ENDPOINT",
                            criticality="CRITICAL" if (is_admin or is_auth) else "HIGH",
                            owner="Identity / Security Team" if (is_admin or is_auth) else "API Engineering",
                            location=rel_loc,
                            trust_boundary="TB-2",
                            confidence=0.95,
                            attributes={
                                "route": route_path,
                                "method": method.upper(),
                                "auth_surface": is_auth,
                                "admin_surface": is_admin,
                                "file": rel_loc,
                            }
                        ))
                    continue

                # General route strings in route files
                if any(rp in f_lower for rp in route_patterns):
                    found_routes = re.findall(r"""['"](/(?:api|v[0-9]+|auth|admin|users|login|items)[a-zA-Z0-9_/.-]*)['"]""", content)
                    if found_routes:
                        unique_routes = sorted(list(set(found_routes)))[:3]
                        rel_loc = normalize_repo_path(f, root)
                        for route in unique_routes:
                            is_admin = "admin" in route.lower()
                            is_auth = "auth" in route.lower() or "login" in route.lower()
                            apis.append(DiscoveredAsset(
                                asset_id=f"AST-API-{route.strip('/').replace('/', '-')}",
                                asset_name=route,
                                asset_type="ENDPOINT" if route.count("/") > 2 else "API",
                                criticality="CRITICAL" if (is_admin or is_auth) else "HIGH",
                                owner="Identity / Security Team" if (is_admin or is_auth) else "API Engineering",
                                location=rel_loc,
                                trust_boundary="TB-2",
                                confidence=0.90,
                                attributes={"route": route, "auth_surface": is_auth, "admin_surface": is_admin, "file": rel_loc}
                            ))
            except Exception:
                pass

            if len(apis) >= 8:
                break
        return apis

    def _discover_databases(self, root: Path, files: List[str]) -> List[DiscoveredAsset]:
        dbs: List[DiscoveredAsset] = []
        for f in files:
            f_lower = f.lower()
            ext = Path(f).suffix.lower()

            # Strictly skip binary or model files
            if ext in BINARY_MODEL_EXTENSIONS:
                continue

            # Check for genuine database config/schema files
            is_db_candidate = (
                any(db_kw in f_lower for db_kw in ["database", "db.py", "db/", "alembic", "schema.prisma", "postgres", "mysql", "mongo", "redis"])
                or (f_lower.endswith(".sql") and "schema" in f_lower)
                or (f_lower.endswith("models.py") and not any(ign in f_lower for ign in ["ml", "transformer", "classifier"]))
            )

            if not is_db_candidate:
                continue

            file_path = root / f
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                # Validate that the file actually contains database connection or schema code
                has_db_evidence = any(
                    sig in content.lower()
                    for sig in [
                        "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
                        "sqlalchemy", "create_engine", "sessionmaker", "prisma", "datasource",
                        "declarative_base", "column(", "primary_key", "models.model",
                    ]
                )
                if not has_db_evidence:
                    continue

                engine = (
                    "PostgreSQL" if "postgres" in content.lower()
                    else ("MySQL" if "mysql" in content.lower()
                    else ("SQLite" if "sqlite" in content.lower()
                    else ("Redis" if "redis" in content.lower()
                    else ("MongoDB" if "mongo" in content.lower()
                    else "Relational Database"))))
                )
                rel_loc = normalize_repo_path(f, root)
                dbs.append(DiscoveredAsset(
                    asset_id=f"AST-DB-{engine.lower().replace(' ', '-')}",
                    asset_name=f"{engine} Database Store",
                    asset_type="DATABASE",
                    criticality="CRITICAL",
                    owner="Data Engineering",
                    location=rel_loc,
                    trust_boundary="TB-4",
                    confidence=0.92,
                    attributes={"engine": engine, "config_file": rel_loc}
                ))
                break  # Primary db found
            except Exception:
                pass

        return dbs

    def _discover_services(self, root: Path, files: List[str]) -> List[DiscoveredAsset]:
        services: List[DiscoveredAsset] = []
        for f in files:
            f_lower = f.lower()
            if Path(f).suffix.lower() in BINARY_MODEL_EXTENSIONS:
                continue

            if "service" in f_lower or "client" in f_lower or "integration" in f_lower:
                file_path = root / f
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                    if any(ext in content for ext in ["httpx.", "requests.", "axios.", "fetch(", "boto3", "stripe", "openai"]):
                        svc_name = "External API Integration"
                        if "boto3" in content or "aws" in content.lower():
                            svc_name = "AWS Cloud Service Integration"
                        elif "stripe" in content.lower():
                            svc_name = "Stripe Payment Integration"
                        elif "openai" in content.lower():
                            svc_name = "OpenAI Model API Integration"
                        elif "exa" in content.lower():
                            svc_name = "Exa Search External API"

                        rel_loc = normalize_repo_path(f, root)
                        services.append(DiscoveredAsset(
                            asset_id=f"AST-SVC-{svc_name.lower().replace(' ', '-')[:20]}",
                            asset_name=svc_name,
                            asset_type="SERVICE",
                            criticality="MEDIUM",
                            owner="Integrations Team",
                            location=rel_loc,
                            trust_boundary="TB-3",
                            confidence=0.88,
                            attributes={"external_integration": True, "file": rel_loc}
                        ))
                except Exception:
                    pass
            if len(services) >= 3:
                break
        return services

    def _discover_security_modules(self, root: Path, files: List[str]) -> List[DiscoveredAsset]:
        modules: List[DiscoveredAsset] = []
        for f in files:
            f_lower = f.lower()
            if Path(f).suffix.lower() in BINARY_MODEL_EXTENSIONS:
                continue

            if any(sec_kw in f_lower for sec_kw in ["auth", "jwt", "rbac", "permission", "crypto", "security"]):
                rel_loc = normalize_repo_path(f, root)
                modules.append(DiscoveredAsset(
                    asset_id=f"AST-MOD-{Path(f).stem.lower()}",
                    asset_name=f"Security Module ({Path(f).stem})",
                    asset_type="MODULE",
                    criticality="HIGH",
                    owner="Security Engineering",
                    location=rel_loc,
                    trust_boundary="TB-3",
                    confidence=0.88,
                    attributes={"security_module": True, "path": rel_loc}
                ))
            if len(modules) >= 3:
                break
        return modules

    def _discover_workers(self, root: Path, files: List[str]) -> List[DiscoveredAsset]:
        workers: List[DiscoveredAsset] = []
        for f in files:
            f_lower = f.lower()
            if Path(f).suffix.lower() in BINARY_MODEL_EXTENSIONS:
                continue

            if any(w_kw in f_lower for w_kw in ["celery", "worker", "tasks", "queue"]):
                file_path = root / f
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
                    if any(sig in content.lower() for sig in ["@celery", "celery(", "celery_app", "redistask", "rabbitmq", "backgroundtasks"]):
                        rel_loc = normalize_repo_path(f, root)
                        workers.append(DiscoveredAsset(
                            asset_id=f"AST-WRK-{Path(f).stem.lower()}",
                            asset_name=f"Background Worker ({Path(f).stem})",
                            asset_type="QUEUE_WORKER",
                            criticality="MEDIUM",
                            owner="Platform Engineering",
                            location=rel_loc,
                            trust_boundary="TB-3",
                            confidence=0.90,
                            attributes={"worker_type": "Asynchronous Task Processing", "file": rel_loc}
                        ))
                except Exception:
                    pass
            if len(workers) >= 2:
                break
        return workers


asset_discovery_service = AssetDiscoveryService()
