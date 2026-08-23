"""
NOVA — OSV Scanner Adapter
Queries Open Source Vulnerabilities database or falls back to multi-ecosystem (Python, Node/npm) dependency advisory matching.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)

# Multi-ecosystem offline advisory database (Python & Node.js npm)
KNOWN_OSV_ADVISORIES: Dict[str, List[Dict[str, Any]]] = {
    "lodash": [
        {
            "vulnerable_spec": lambda v: v in {"4.17.11", "4.17.10", "4.17.9", "4.17.4"},
            "cve": "CVE-2019-10744",
            "title": "Prototype pollution vulnerability in lodash < 4.17.12",
            "severity": "CRITICAL",
            "cvss": 9.8,
            "description": "lodash defaultsDeep, merge, and mergeWith functions are vulnerable to Prototype Pollution.",
        },
        {
            "vulnerable_spec": lambda v: v in {"4.17.15", "4.17.14", "4.17.13", "4.17.12"},
            "cve": "CVE-2020-8203",
            "title": "Prototype pollution vulnerability in lodash < 4.17.21",
            "severity": "MEDIUM",
            "cvss": 7.4,
            "description": "lodash zipObjectDeep function allows prototype pollution when user input controls property path keys.",
        },
    ],
    "flask": [
        {
            "vulnerable_spec": lambda v: v in {"2.2.3", "2.2.0", "2.2.1", "2.2.2"},
            "cve": "CVE-2023-30861",
            "title": "Cookie session fixation in Flask < 2.2.5",
            "severity": "MEDIUM",
            "cvss": 7.5,
            "description": "Flask session cookies are vulnerable to fixation under specific caching configurations.",
        }
    ],
    "pyyaml": [
        {
            "vulnerable_spec": lambda v: v in {"5.3.1", "5.3", "5.1", "5.2"},
            "cve": "CVE-2020-14343",
            "title": "Arbitrary code execution in PyYAML < 5.4",
            "severity": "CRITICAL",
            "cvss": 9.8,
            "description": "PyYAML full_load method can be exploited to execute arbitrary system commands via crafted YAML tags.",
        }
    ],
    "requests": [
        {
            "vulnerable_spec": lambda v: v == "2.31.0",
            "cve": "CVE-2024-35195",
            "title": "Session verify=False persistence weakness in requests 2.31.0",
            "severity": "MEDIUM",
            "cvss": 5.3,
            "description": "requests Session verify=False persists across subsequent requests unintentionally.",
        }
    ],
}


class OsvScanner(BaseScanner):
    """OSV vulnerability scanner for multi-ecosystem repositories."""

    def __init__(self, cli_command: str = "osv-scanner") -> None:
        super().__init__(name="osv", cli_command=cli_command)

    async def scan(self, target_path: Path | str, **kwargs: Any) -> Dict[str, Any]:
        target = Path(target_path)
        if not target.exists():
            return {"scanner": self.name, "success": False, "findings": [], "error": f"Target path does not exist: {target}"}

        if self.is_available():
            findings = await self._run_cli_scan(target)
            if findings is not None:
                return {"scanner": self.name, "success": True, "findings": findings}

        findings = self._run_fallback_scan(target)
        return {"scanner": self.name, "success": True, "findings": findings}

    async def _run_cli_scan(self, target: Path) -> Optional[List[Dict[str, Any]]]:
        try:
            cmd = [self.cli_command or "osv-scanner", "--json", "-r", str(target)]
            code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=120.0)
            if stdout.strip():
                data = json.loads(stdout)
                results = data.get("results", [])
                findings: List[Dict[str, Any]] = []
                for res in results:
                    packages = res.get("packages", [])
                    for p in packages:
                        pkg_info = p.get("package", {})
                        pkg_name = pkg_info.get("name")
                        pkg_ver = pkg_info.get("version")
                        vulns = p.get("vulnerabilities", [])
                        for v in vulns:
                            cve_id = v.get("id")
                            aliases = v.get("aliases", [])
                            cve = next((a for a in aliases if a.startswith("CVE-")), cve_id)
                            findings.append({
                                "title": f"Vulnerability in {pkg_name} {pkg_ver} ({cve})",
                                "severity": "HIGH",
                                "category": "vulnerable_dependency",
                                "source": self.name,
                                "cvss": 7.5,
                                "file_path": self.relative_path_str(res.get("source", {}).get("path", ""), target),
                                "package": pkg_name,
                                "package_version": pkg_ver,
                                "cve": cve,
                                "description": v.get("details", ""),
                            })
                return findings
        except Exception as exc:
            logger.warning("osv.cli_scan_failed", error=str(exc))
        return None

    def _run_fallback_scan(self, target: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Check Python requirements.txt
        req_files = self.walk_files(target, include_filenames={"requirements.txt"})
        for req in req_files:
            content = self.read_file_safe(req)
            if not content:
                continue
            rel_path = self.relative_path_str(req, target)
            deps = self._parse_requirements(content)
            for line_no, pkg_name, pkg_version in deps:
                pkg_key = pkg_name.lower().replace("_", "-")
                if pkg_key in KNOWN_OSV_ADVISORIES:
                    for adv in KNOWN_OSV_ADVISORIES[pkg_key]:
                        if adv["vulnerable_spec"](pkg_version):
                            findings.append({
                                "title": adv["title"],
                                "severity": adv["severity"],
                                "category": "vulnerable_dependency",
                                "source": self.name,
                                "cvss": adv["cvss"],
                                "file_path": rel_path,
                                "line_number": line_no,
                                "package": pkg_name,
                                "package_version": pkg_version,
                                "cve": adv["cve"],
                                "description": adv["description"],
                            })

        # 2. Check Node package.json
        pkg_json_files = self.walk_files(target, include_filenames={"package.json"})
        for pjf in pkg_json_files:
            content = self.read_file_safe(pjf)
            if not content:
                continue
            rel_path = self.relative_path_str(pjf, target)
            try:
                data = json.loads(content)
                all_deps = {}
                all_deps.update(data.get("dependencies", {}))
                all_deps.update(data.get("devDependencies", {}))
                for pkg_name, ver_spec in all_deps.items():
                    clean_ver = re.sub(r'[\^~>=<v]', '', ver_spec).strip()
                    pkg_key = pkg_name.lower()
                    if pkg_key in KNOWN_OSV_ADVISORIES:
                        for adv in KNOWN_OSV_ADVISORIES[pkg_key]:
                            if adv["vulnerable_spec"](clean_ver):
                                findings.append({
                                "title": adv["title"],
                                "severity": adv["severity"],
                                "category": "vulnerable_dependency",
                                "source": self.name,
                                "cvss": adv["cvss"],
                                "file_path": rel_path,
                                "package": pkg_name,
                                "package_version": clean_ver,
                                "cve": adv["cve"],
                                "description": adv["description"],
                            })
            except Exception:
                pass

        return findings

    def _parse_requirements(self, text: str) -> List[Tuple[int, str, str]]:
        deps: List[Tuple[int, str, str]] = []
        for line_idx, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*(?:==|<=|>=|<|>|~=)\s*([a-zA-Z0-9_\-\.]+)', line)
            if match:
                deps.append((line_idx, match.group(1), match.group(2)))
        return deps
