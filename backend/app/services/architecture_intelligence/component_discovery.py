"""
NOVA Architecture Intelligence — Component Discovery Service
Statically discovers software components (files, modules, packages, classes,
functions, services, endpoints, databases, external dependencies) from repository structure.
Strictly static/read-only analysis; never executes repository code.
"""

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import structlog

from app.services.security_intelligence.repository_ingestion import repository_ingestion_service, IGNORED_DIRS
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)

# Supported code extensions for AST/structural analysis
SUPPORTED_PYTHON_EXTENSIONS = {".py"}
SUPPORTED_JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SUPPORTED_MANIFEST_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "pipfile",
    "package.json",
    "pom.xml",
    "go.mod",
}


@dataclass
class DiscoveredComponent:
    component_id: str
    name: str
    component_type: str  # FILE, MODULE, PACKAGE, CLASS, FUNCTION, SERVICE, ENDPOINT, DATABASE, EXTERNAL_DEPENDENCY
    file_path: str  # repository-relative path
    line_number: Optional[int] = None
    language: str = "generic"
    parent_id: Optional[str] = None
    members: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)


class ComponentDiscoveryService:
    """Discovers software components strictly via static analysis."""

    def discover_components(self, target_path: str = ".") -> List[DiscoveredComponent]:
        repo_root = Path(target_path).resolve()
        if not repo_root.exists():
            logger.warning("component_discovery.path_not_found", target_path=target_path)
            return []

        logger.info("component_discovery.started", target_path=str(repo_root))
        components: List[DiscoveredComponent] = []
        seen_ids: Set[str] = set()

        # Enumerate repository files
        repo_info = repository_ingestion_service.enumerate_repository_files(repo_root)
        files = repo_info.get("files", [])

        # 1. Discover External Dependencies from manifests
        manifest_components = self._discover_manifest_dependencies(repo_root, files)
        for comp in manifest_components:
            if comp.component_id not in seen_ids:
                seen_ids.add(comp.component_id)
                components.append(comp)

        # 2. Discover Code Components per file
        for rel_file in files:
            file_path = repo_root / rel_file
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            norm_rel_path = normalize_repo_path(rel_file, repo_root)

            # Module / File component
            module_name = self._derive_module_name(norm_rel_path)
            mod_type = "PACKAGE" if file_path.name in ("__init__.py", "index.ts", "index.js") else "MODULE"
            mod_id = f"CMP-MOD-{norm_rel_path.replace('/', '.')}"
            if mod_id not in seen_ids:
                seen_ids.add(mod_id)
                components.append(
                    DiscoveredComponent(
                        component_id=mod_id,
                        name=module_name,
                        component_type=mod_type,
                        file_path=norm_rel_path,
                        line_number=1,
                        language="python" if ext in SUPPORTED_PYTHON_EXTENSIONS else ("javascript" if ext in SUPPORTED_JS_TS_EXTENSIONS else "generic"),
                        attributes={"file_name": file_path.name, "size_bytes": file_path.stat().st_size},
                    )
                )

            # Analyze internal constructs
            if ext in SUPPORTED_PYTHON_EXTENSIONS:
                py_components = self._discover_python_components(file_path, norm_rel_path, mod_id)
                for c in py_components:
                    if c.component_id not in seen_ids:
                        seen_ids.add(c.component_id)
                        components.append(c)

            elif ext in SUPPORTED_JS_TS_EXTENSIONS:
                js_components = self._discover_jsts_components(file_path, norm_rel_path, mod_id)
                for c in js_components:
                    if c.component_id not in seen_ids:
                        seen_ids.add(c.component_id)
                        components.append(c)

        logger.info("component_discovery.completed", total_components=len(components))
        return components

    def _derive_module_name(self, rel_path: str) -> str:
        p = Path(rel_path)
        parts = list(p.parts)
        if parts and parts[-1].endswith(tuple(SUPPORTED_PYTHON_EXTENSIONS | SUPPORTED_JS_TS_EXTENSIONS)):
            parts[-1] = Path(parts[-1]).stem
        return ".".join(parts) if parts else rel_path

    def _discover_manifest_dependencies(self, root: Path, files: List[str]) -> List[DiscoveredComponent]:
        deps: List[DiscoveredComponent] = []
        for rel_file in files:
            name_lower = Path(rel_file).name.lower()
            if name_lower not in SUPPORTED_MANIFEST_FILES:
                continue

            file_path = root / rel_file
            norm_rel_path = normalize_repo_path(rel_file, root)
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if name_lower == "requirements.txt":
                    for line in content.splitlines():
                        clean = line.strip().split("#")[0].split(";")[0].strip()
                        if clean and not clean.startswith(("-", "http://", "https://")):
                            pkg_name = re.split(r"[=<>]", clean)[0].strip()
                            if pkg_name:
                                deps.append(
                                    DiscoveredComponent(
                                        component_id=f"CMP-EXT-{pkg_name.lower()}",
                                        name=pkg_name,
                                        component_type="EXTERNAL_DEPENDENCY",
                                        file_path=norm_rel_path,
                                        language="python",
                                        attributes={"manifest": "requirements.txt", "raw_spec": clean},
                                    )
                                )
                elif name_lower == "package.json":
                    try:
                        data = json.loads(content)
                        for dep_group in ["dependencies", "devDependencies"]:
                            for pkg_name, version in data.get(dep_group, {}).items():
                                deps.append(
                                    DiscoveredComponent(
                                        component_id=f"CMP-EXT-{pkg_name.lower()}",
                                        name=pkg_name,
                                        component_type="EXTERNAL_DEPENDENCY",
                                        file_path=norm_rel_path,
                                        language="javascript",
                                        attributes={"manifest": "package.json", "version": version, "group": dep_group},
                                    )
                                )
                    except Exception:
                        pass
            except Exception as exc:
                logger.debug("component_discovery.manifest_read_error", file=rel_file, error=str(exc))
        return deps

    def _discover_python_components(
        self, file_path: Path, rel_path: str, module_id: str
    ) -> List[DiscoveredComponent]:
        results: List[DiscoveredComponent] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception as exc:
            logger.debug("component_discovery.python_ast_failed", file=rel_path, error=str(exc))
            return results

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                line_no = getattr(node, "lineno", 1)
                bases = [ast.unparse(b) for b in node.bases if hasattr(ast, "unparse")]
                method_names = [
                    m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                is_db_model = any(b in ["Base", "Model", "DeclarativeBase"] for b in bases) or "model" in node.name.lower()
                is_service = "service" in node.name.lower() or "handler" in node.name.lower() or "engine" in node.name.lower()

                c_type = "DATABASE" if is_db_model else ("SERVICE" if is_service else "CLASS")
                class_id = f"CMP-CLS-{rel_path.replace('/', '.')}:{node.name}"
                results.append(
                    DiscoveredComponent(
                        component_id=class_id,
                        name=node.name,
                        component_type=c_type,
                        file_path=rel_path,
                        line_number=line_no,
                        language="python",
                        parent_id=module_id,
                        members=method_names,
                        attributes={
                            "bases": bases,
                            "method_count": len(method_names),
                            "is_service": is_service,
                            "is_db_model": is_db_model,
                        },
                    )
                )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                line_no = getattr(node, "lineno", 1)
                # Check for endpoint decorators
                endpoint_route = None
                endpoint_method = None
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                    match = re.search(r"@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", dec_str, re.IGNORECASE)
                    if match:
                        endpoint_method = match.group(1).upper()
                        endpoint_route = match.group(2)
                        break

                if endpoint_route and endpoint_method:
                    ep_id = f"CMP-EP-{endpoint_method}-{endpoint_route.strip('/').replace('/', '-') or 'root'}"
                    results.append(
                        DiscoveredComponent(
                            component_id=ep_id,
                            name=f"{endpoint_method} {endpoint_route}",
                            component_type="ENDPOINT",
                            file_path=rel_path,
                            line_number=line_no,
                            language="python",
                            parent_id=module_id,
                            attributes={
                                "method": endpoint_method,
                                "route": endpoint_route,
                                "handler": node.name,
                            },
                        )
                    )
                else:
                    fn_id = f"CMP-FN-{rel_path.replace('/', '.')}:{node.name}"
                    results.append(
                        DiscoveredComponent(
                            component_id=fn_id,
                            name=node.name,
                            component_type="FUNCTION",
                            file_path=rel_path,
                            line_number=line_no,
                            language="python",
                            parent_id=module_id,
                            attributes={
                                "is_async": isinstance(node, ast.AsyncFunctionDef),
                                "args": [a.arg for a in node.args.args],
                            },
                        )
                    )

        return results

    def _discover_jsts_components(
        self, file_path: Path, rel_path: str, module_id: str
    ) -> List[DiscoveredComponent]:
        results: List[DiscoveredComponent] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return results

        lines = content.splitlines()

        # Regex patterns for functions, classes, and endpoints in JS/TS
        class_pattern = re.compile(r"class\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_.]+))?")
        func_pattern = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(")
        const_func_pattern = re.compile(r"(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")
        endpoint_pattern = re.compile(r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)

        for line_idx, line in enumerate(lines, 1):
            # Endpoint match
            ep_match = endpoint_pattern.search(line)
            if ep_match:
                method = ep_match.group(1).upper()
                route = ep_match.group(2)
                ep_id = f"CMP-EP-{method}-{route.strip('/').replace('/', '-') or 'root'}"
                results.append(
                    DiscoveredComponent(
                        component_id=ep_id,
                        name=f"{method} {route}",
                        component_type="ENDPOINT",
                        file_path=rel_path,
                        line_number=line_idx,
                        language="javascript",
                        parent_id=module_id,
                        attributes={"method": method, "route": route},
                    )
                )
                continue

            # Class match
            cls_match = class_pattern.search(line)
            if cls_match:
                cls_name = cls_match.group(1)
                extends = cls_match.group(2)
                is_service = "service" in cls_name.lower() or "controller" in cls_name.lower()
                c_type = "SERVICE" if is_service else "CLASS"
                cls_id = f"CMP-CLS-{rel_path.replace('/', '.')}:{cls_name}"
                results.append(
                    DiscoveredComponent(
                        component_id=cls_id,
                        name=cls_name,
                        component_type=c_type,
                        file_path=rel_path,
                        line_number=line_idx,
                        language="javascript",
                        parent_id=module_id,
                        attributes={"extends": extends or None, "is_service": is_service},
                    )
                )
                continue

            # Function match
            fn_match = func_pattern.search(line) or const_func_pattern.search(line)
            if fn_match:
                fn_name = fn_match.group(1)
                if fn_name not in ("if", "for", "while", "switch", "catch"):
                    fn_id = f"CMP-FN-{rel_path.replace('/', '.')}:{fn_name}"
                    results.append(
                        DiscoveredComponent(
                            component_id=fn_id,
                            name=fn_name,
                            component_type="FUNCTION",
                            file_path=rel_path,
                            line_number=line_idx,
                            language="javascript",
                            parent_id=module_id,
                        )
                    )

        return results


component_discovery_service = ComponentDiscoveryService()
