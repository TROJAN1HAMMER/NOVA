"""
NOVA Security Intelligence — Observation Collector
Extracts security facts & observations from code, configuration, and interfaces using real AST parsing and static rules.
Observations represent verified security facts and findings across application assets.
"""

import ast
import datetime
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.security_rules import static_security_rules_engine, StaticFindingData
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class SecurityObservationData:
    observation_type: str  # PUBLIC_ENDPOINT, USER_CONTROLLED_INPUT, DATABASE_ACCESS, SECRET_USAGE, AUTHORIZATION_BOUNDARY, AUTHENTICATION_BOUNDARY, PRIVILEGED_OPERATION, EXTERNAL_DEPENDENCY, STATIC_SECURITY_FINDING
    location: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    evidence_span: str = ""
    confidence: float = 0.90
    provenance: str = "code_ast_fact"
    lifecycle_state: str = "OBSERVED"
    asset_id: str = "asset_default"
    version_hash: str = "head"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    provenance_chain: List[str] = field(default_factory=lambda: ["code_ast_parser"])
    transition_condition: str = "AST_NODE_EXTRACTED"
    finding_data: Optional[StaticFindingData] = None


class ObservationCollectorService:
    """Collects security observations across application assets using AST parsing, static rules, and structural inspection."""

    def _collect_ast_observations_for_file(self, file_path: Path, rel_path: str) -> List[SecurityObservationData]:
        observations: List[SecurityObservationData] = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code_content = f.read()

            tree = ast.parse(code_content, filename=str(file_path))
            lines = code_content.splitlines()

            for node in ast.walk(tree):
                # 1. Route Decorators (@router.get, @router.post, @app.get, etc.)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    line_no = getattr(node, "lineno", 1)
                    for decorator in node.decorator_list:
                        dec_str = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
                        if any(r in dec_str for r in ["router.", "app.", "blueprint."]):
                            method = "POST" if "post" in dec_str.lower() else ("GET" if "get" in dec_str.lower() else "HTTP")
                            is_auth_required = "Depends" in dec_str or "auth" in dec_str.lower()
                            observations.append(SecurityObservationData(
                                observation_type="PUBLIC_ENDPOINT",
                                location=f"{rel_path}:line {line_no}",
                                attributes={
                                    "method": method,
                                    "function_name": node.name,
                                    "decorator": dec_str,
                                    "auth_required": is_auth_required,
                                },
                                evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else dec_str,
                                provenance="fastapi_route_ast"
                            ))

                        if "Depends(" in dec_str and any(auth_kw in dec_str for auth_kw in ["RequireRole", "Role", "auth", "get_current_user"]):
                            observations.append(SecurityObservationData(
                                observation_type="AUTHORIZATION_BOUNDARY",
                                location=f"{rel_path}:line {line_no}",
                                attributes={"enforcement": dec_str, "function": node.name},
                                evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else dec_str,
                                provenance="ast_decorator_dependency"
                            ))

                    # Check for privileged operations inside function body
                    if any(adm in node.name.lower() for adm in ["admin", "role", "delete", "grant", "permission", "update_user"]):
                        observations.append(SecurityObservationData(
                            observation_type="PRIVILEGED_OPERATION",
                            location=f"{rel_path}:line {line_no}",
                            attributes={"operation": node.name, "privileged": True},
                            evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else f"def {node.name}()",
                            provenance="ast_function_name_heuristic"
                        ))

                    # User-controlled input parameters
                    for arg in node.args.args:
                        if arg.arg not in ["self", "cls", "db", "session"]:
                            observations.append(SecurityObservationData(
                                observation_type="USER_CONTROLLED_INPUT",
                                location=f"{rel_path}:line {line_no}",
                                attributes={"parameter": arg.arg, "function": node.name},
                                evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else arg.arg,
                                provenance="ast_function_param"
                            ))

                # 2. Environment Variables & Configuration Usage (os.getenv, settings.)
                elif isinstance(node, ast.Call):
                    func_str = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                    line_no = getattr(node, "lineno", 1)
                    norm_loc = normalize_repo_path(f"{rel_path}:line {line_no}")
                    if "getenv" in func_str or "environ" in func_str or "settings." in func_str:
                        observations.append(SecurityObservationData(
                            observation_type="ENV_CONFIG_READ",
                            location=norm_loc,
                            attributes={"call": func_str, "is_vulnerability": False},
                            evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else func_str,
                            provenance="ast_env_var_fact"
                        ))

                    elif any(db_call in func_str for db_call in ["select(", "execute(", "query(", "raw(", "cursor.execute"]):
                        observations.append(SecurityObservationData(
                            observation_type="DATABASE_ACCESS",
                            location=norm_loc,
                            attributes={"query_call": func_str},
                            evidence_span=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else func_str,
                            provenance="ast_database_query_fact"
                        ))

        except Exception as exc:
            logger.warning("observation_collector.ast_parse_failed", file_path=str(file_path), error=str(exc))

        return observations

    def collect_observations(
        self, asset_name: str, location: str, repo_root: Optional[Path] = None
    ) -> List[SecurityObservationData]:
        logger.info("security_intel.collecting_observations", asset_name=asset_name, location=location)
        observations: List[SecurityObservationData] = []

        root = repo_root or Path(".").resolve()
        loc_path = Path(location)
        if not loc_path.is_absolute():
            resolved_target = (root / loc_path).resolve()
            if not resolved_target.exists():
                stripped = location.removeprefix("backend/").lstrip("/")
                if (root / stripped).exists():
                    resolved_target = (root / stripped).resolve()
                elif (root.parent / loc_path).exists():
                    resolved_target = (root.parent / loc_path).resolve()
        else:
            resolved_target = loc_path

        from app.services.security_intelligence.repository_ingestion import IGNORED_DIRS

        files_to_analyze: List[Path] = []
        if resolved_target.is_file():
            files_to_analyze.append(resolved_target)
        elif resolved_target.is_dir():
            for r, dirs, files in os.walk(resolved_target):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]
                for f in files:
                    if not f.startswith(".") and Path(f).suffix in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".yml", ".yaml", ".json"]:
                        fp = Path(r) / f
                        try:
                            if fp.stat().st_size < 300 * 1024:  # skip files > 300KB
                                files_to_analyze.append(fp)
                        except Exception:
                            pass
        if not files_to_analyze:
            # Check for close matching file by filename or stem (e.g. admin_router.py for admin.py)
            target_name = Path(location).name
            stem = Path(location).stem
            search_roots = [root]
            if root.name == "backend" and root.parent.exists():
                search_roots.append(root.parent)
            for s_root in search_roots:
                for r, dirs, files in os.walk(s_root):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]
                    for f in files:
                        if f == target_name or f == f"{stem}_router.py" or (stem in f and f.endswith(".py") and not f.startswith("test_")):
                            files_to_analyze.append(Path(r) / f)
                            break
                    if files_to_analyze:
                        break
                if files_to_analyze:
                    break

        # Analyze each file for AST facts and static security findings
        for f_path in files_to_analyze:
            rel = normalize_repo_path(f_path, root)

            if f_path.suffix == ".py":
                ast_obs = self._collect_ast_observations_for_file(f_path, rel)
                observations.extend(ast_obs)

            # Static security rules analysis
            static_findings = static_security_rules_engine.analyze_file(f_path, root)
            for sf in static_findings:
                obs_type = "SECRET_EXPOSURE_FINDING" if sf.category == "SECRET_EXPOSURE" else (
                    "USER_CONTROLLED_INPUT" if sf.category == "INJECTION" else (
                        "AUTHORIZATION_BOUNDARY" if sf.category == "AUTHENTICATION_AUTHORIZATION" else "STATIC_SECURITY_FINDING"
                    )
                )
                finding_loc = normalize_repo_path(f"{sf.file_path}:line {sf.line_number}", root)
                observations.append(SecurityObservationData(
                    observation_type=obs_type,
                    location=finding_loc,
                    attributes={
                        "rule_id": sf.rule_id,
                        "title": sf.title,
                        "severity": sf.severity,
                        "cwe_id": sf.cwe_id,
                        "finding_data": sf,
                    },
                    evidence_span=sf.code_snippet,
                    confidence=sf.confidence,
                    provenance=f"rule_{sf.rule_id}",
                    finding_data=sf,
                ))

        logger.info("security_intel.observations_collected", count=len(observations))
        return observations


observation_collector = ObservationCollectorService()
