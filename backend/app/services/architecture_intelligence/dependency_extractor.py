"""
NOVA Architecture Intelligence — Dependency Extractor Service
Extracts typed, provenance-backed dependency relationships between software components:
IMPORTS, CALLS, DEPENDS_ON, IMPLEMENTS, EXTENDS, USES, ACCESSES, EXPOSES, DEPENDS_ON_EXTERNAL.
Strictly static/read-only AST & lexical extraction.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set
import structlog

from app.services.architecture_intelligence.component_discovery import (
    DiscoveredComponent,
    SUPPORTED_PYTHON_EXTENSIONS,
    SUPPORTED_JS_TS_EXTENSIONS,
)
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class DiscoveredDependency:
    source_id: str
    target_id: str
    relation_type: str  # IMPORTS, CALLS, DEPENDS_ON, IMPLEMENTS, EXTENDS, USES, ACCESSES, EXPOSES, DEPENDS_ON_EXTERNAL
    file_path: str
    line_number: Optional[int] = None
    evidence: Optional[str] = None
    is_circular: bool = False


class DependencyExtractorService:
    """Extracts architectural dependencies from static source code and manifests."""

    def extract_dependencies(
        self,
        components: List[DiscoveredComponent],
        target_path: str = ".",
    ) -> List[DiscoveredDependency]:
        repo_root = Path(target_path).resolve()
        logger.info("dependency_extractor.started", components_count=len(components))

        dependencies: List[DiscoveredDependency] = []
        comp_by_id = {c.component_id: c for c in components}
        comp_by_name: Dict[str, List[DiscoveredComponent]] = {}
        comp_by_file: Dict[str, List[DiscoveredComponent]] = {}

        for c in components:
            comp_by_name.setdefault(c.name, []).append(c)
            comp_by_file.setdefault(c.file_path, []).append(c)

        # 1. Connect Endpoints to Modules / Handlers (EXPOSES & CALLS)
        for c in components:
            if c.component_type == "ENDPOINT":
                mod_id = c.parent_id
                if mod_id and mod_id in comp_by_id:
                    dependencies.append(
                        DiscoveredDependency(
                            source_id=mod_id,
                            target_id=c.component_id,
                            relation_type="EXPOSES",
                            file_path=c.file_path,
                            line_number=c.line_number,
                            evidence=f"Exposes endpoint {c.name}",
                        )
                    )
                handler_name = c.attributes.get("handler")
                if handler_name:
                    fn_id = f"CMP-FN-{c.file_path.replace('/', '.')}:{handler_name}"
                    if fn_id in comp_by_id:
                        dependencies.append(
                            DiscoveredDependency(
                                source_id=c.component_id,
                                target_id=fn_id,
                                relation_type="CALLS",
                                file_path=c.file_path,
                                line_number=c.line_number,
                                evidence=f"Route invokes handler {handler_name}",
                            )
                        )

        # 2. Extract Dependencies per file
        for rel_file, file_comps in comp_by_file.items():
            file_path = repo_root / rel_file
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lower()
            mod_comp = next((fc for fc in file_comps if fc.component_type in ("MODULE", "PACKAGE")), None)
            source_mod_id = mod_comp.component_id if mod_comp else f"CMP-MOD-{rel_file.replace('/', '.')}"

            if ext in SUPPORTED_PYTHON_EXTENSIONS:
                py_deps = self._extract_python_dependencies(
                    file_path=file_path,
                    rel_file=rel_file,
                    source_mod_id=source_mod_id,
                    components=components,
                    comp_by_name=comp_by_name,
                    comp_by_id=comp_by_id,
                )
                dependencies.extend(py_deps)

            elif ext in SUPPORTED_JS_TS_EXTENSIONS:
                js_deps = self._extract_jsts_dependencies(
                    file_path=file_path,
                    rel_file=rel_file,
                    source_mod_id=source_mod_id,
                    components=components,
                    comp_by_name=comp_by_name,
                    comp_by_id=comp_by_id,
                )
                dependencies.extend(js_deps)

        # Deduplicate edges (source, target, relation_type)
        unique_deps: List[DiscoveredDependency] = []
        seen = set()
        for d in dependencies:
            if d.source_id == d.target_id:
                continue  # ignore direct self-loops for coupling metrics
            key = (d.source_id, d.target_id, d.relation_type)
            if key not in seen:
                seen.add(key)
                unique_deps.append(d)

        logger.info("dependency_extractor.completed", total_dependencies=len(unique_deps))
        return unique_deps

    def _extract_python_dependencies(
        self,
        file_path: Path,
        rel_file: str,
        source_mod_id: str,
        components: List[DiscoveredComponent],
        comp_by_name: Dict[str, List[DiscoveredComponent]],
        comp_by_id: Dict[str, DiscoveredComponent],
    ) -> List[DiscoveredDependency]:
        deps: List[DiscoveredDependency] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return deps

        lines = content.splitlines()

        # Build map of local symbols for call resolution
        local_classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        local_functions = {
            node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        # 1. Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                line_no = getattr(node, "lineno", 1)
                span = lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else ""
                for alias in node.names:
                    imported_mod = alias.name
                    target = self._resolve_python_module(imported_mod, components, comp_by_id)
                    if target:
                        deps.append(
                            DiscoveredDependency(
                                source_id=source_mod_id,
                                target_id=target.component_id,
                                relation_type="IMPORTS",
                                file_path=rel_file,
                                line_number=line_no,
                                evidence=span,
                            )
                        )
                    else:
                        ext_id = f"CMP-EXT-{imported_mod.split('.')[0].lower()}"
                        if ext_id in comp_by_id:
                            deps.append(
                                DiscoveredDependency(
                                    source_id=source_mod_id,
                                    target_id=ext_id,
                                    relation_type="DEPENDS_ON_EXTERNAL",
                                    file_path=rel_file,
                                    line_number=line_no,
                                    evidence=span,
                                )
                            )

            elif isinstance(node, ast.ImportFrom):
                line_no = getattr(node, "lineno", 1)
                span = lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else ""
                module_name = node.module or ""
                target = self._resolve_python_module(module_name, components, comp_by_id)
                if target:
                    deps.append(
                        DiscoveredDependency(
                            source_id=source_mod_id,
                            target_id=target.component_id,
                            relation_type="IMPORTS",
                            file_path=rel_file,
                            line_number=line_no,
                            evidence=span,
                        )
                    )
                    # Check imported symbols (classes/functions)
                    for alias in node.names:
                        sym_target = comp_by_name.get(alias.name)
                        if sym_target:
                            for st in sym_target:
                                if st.component_type in ("CLASS", "SERVICE", "DATABASE"):
                                    deps.append(
                                        DiscoveredDependency(
                                            source_id=source_mod_id,
                                            target_id=st.component_id,
                                            relation_type="DEPENDS_ON",
                                            file_path=rel_file,
                                            line_number=line_no,
                                            evidence=f"Imports {alias.name} from {module_name}",
                                        )
                                    )
                else:
                    ext_id = f"CMP-EXT-{module_name.split('.')[0].lower()}" if module_name else None
                    if ext_id and ext_id in comp_by_id:
                        deps.append(
                            DiscoveredDependency(
                                source_id=source_mod_id,
                                target_id=ext_id,
                                relation_type="DEPENDS_ON_EXTERNAL",
                                file_path=rel_file,
                                line_number=line_no,
                                evidence=span,
                            )
                        )

            # 2. Class Inheritance & Interfaces (EXTENDS / IMPLEMENTS)
            elif isinstance(node, ast.ClassDef):
                line_no = getattr(node, "lineno", 1)
                cls_id = f"CMP-CLS-{rel_file.replace('/', '.')}:{node.name}"
                for base in node.bases:
                    base_name = ast.unparse(base) if hasattr(ast, "unparse") else ""
                    if not base_name:
                        continue
                    # Match base class in discovered components
                    base_matches = comp_by_name.get(base_name.split(".")[-1], [])
                    rel_type = "IMPLEMENTS" if any(k in base_name for k in ["ABC", "Protocol", "Interface"]) else "EXTENDS"
                    if base_matches:
                        for bm in base_matches:
                            deps.append(
                                DiscoveredDependency(
                                    source_id=cls_id,
                                    target_id=bm.component_id,
                                    relation_type=rel_type,
                                    file_path=rel_file,
                                    line_number=line_no,
                                    evidence=f"class {node.name}({base_name})",
                                )
                            )

            # 3. Function & Service Calls (CALLS / ACCESSES)
            elif isinstance(node, ast.Call):
                line_no = getattr(node, "lineno", 1)
                func_str = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                span = lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else func_str

                # Database Access
                if any(db_kw in func_str for db_kw in ["session.execute", "session.query", "db.execute", "cursor.execute", "select("]):
                    # Link to database component in repo if present
                    db_comps = [c for c in components if c.component_type == "DATABASE"]
                    if db_comps:
                        deps.append(
                            DiscoveredDependency(
                                source_id=source_mod_id,
                                target_id=db_comps[0].component_id,
                                relation_type="ACCESSES",
                                file_path=rel_file,
                                line_number=line_no,
                                evidence=span,
                            )
                        )

                # Cross-component Service Calls
                func_simple = func_str.split(".")[-1]
                target_matches = comp_by_name.get(func_simple, [])
                for tm in target_matches:
                    if tm.file_path != rel_file and tm.component_type in ("FUNCTION", "SERVICE", "CLASS"):
                        deps.append(
                            DiscoveredDependency(
                                source_id=source_mod_id,
                                target_id=tm.component_id,
                                relation_type="CALLS",
                                file_path=rel_file,
                                line_number=line_no,
                                evidence=span,
                            )
                        )

        return deps

    def _extract_jsts_dependencies(
        self,
        file_path: Path,
        rel_file: str,
        source_mod_id: str,
        components: List[DiscoveredComponent],
        comp_by_name: Dict[str, List[DiscoveredComponent]],
        comp_by_id: Dict[str, DiscoveredComponent],
    ) -> List[DiscoveredDependency]:
        deps: List[DiscoveredDependency] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return deps

        lines = content.splitlines()

        # Regexes for JS/TS imports and requires
        import_pattern = re.compile(r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\))""")

        for idx, line in enumerate(lines, 1):
            match = import_pattern.search(line)
            if match:
                specifier = match.group(1) or match.group(2)
                if specifier:
                    if specifier.startswith("."):
                        # Relative internal import
                        target = self._resolve_jsts_relative_module(rel_file, specifier, components, comp_by_id)
                        if target:
                            deps.append(
                                DiscoveredDependency(
                                    source_id=source_mod_id,
                                    target_id=target.component_id,
                                    relation_type="IMPORTS",
                                    file_path=rel_file,
                                    line_number=idx,
                                    evidence=line.strip(),
                                )
                            )
                    else:
                        # External package import
                        ext_id = f"CMP-EXT-{specifier.split('/')[0].lower()}"
                        if ext_id in comp_by_id:
                            deps.append(
                                DiscoveredDependency(
                                    source_id=source_mod_id,
                                    target_id=ext_id,
                                    relation_type="DEPENDS_ON_EXTERNAL",
                                    file_path=rel_file,
                                    line_number=idx,
                                    evidence=line.strip(),
                                )
                            )

        return deps

    def _resolve_python_module(
        self, module_str: str, components: List[DiscoveredComponent], comp_by_id: Dict[str, DiscoveredComponent]
    ) -> Optional[DiscoveredComponent]:
        if not module_str:
            return None
        # Check direct component ID
        direct_id = f"CMP-MOD-{module_str}"
        if direct_id in comp_by_id:
            return comp_by_id[direct_id]

        # Check by module path suffix
        mod_slug = module_str.replace(".", "/")
        for c in components:
            if c.component_type in ("MODULE", "PACKAGE"):
                if c.file_path.endswith(f"{mod_slug}.py") or c.file_path.endswith(f"{mod_slug}/__init__.py"):
                    return c
                if Path(c.file_path).stem == module_str.split(".")[-1]:
                    return c
        return None

    def _resolve_jsts_relative_module(
        self, current_file: str, specifier: str, components: List[DiscoveredComponent], comp_by_id: Dict[str, DiscoveredComponent]
    ) -> Optional[DiscoveredComponent]:
        try:
            curr_dir = Path(current_file).parent
            target_path = (curr_dir / specifier).as_posix()
            norm = Path(target_path).as_posix()

            for c in components:
                if c.component_type in ("MODULE", "PACKAGE"):
                    stem_path = Path(c.file_path).with_suffix("").as_posix()
                    if stem_path == norm or stem_path.endswith(norm.lstrip("/")):
                        return c
                    if c.file_path.startswith(norm):
                        return c
        except Exception:
            pass
        return None


dependency_extractor_service = DependencyExtractorService()
