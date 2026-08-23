"""
NOVA — ast-grep Scanner Adapter
Executes ast-grep CLI if installed, or falls back to structural code analysis patterns.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)

AST_PATTERN_RULES = [
    {
        "id": "mass-assignment",
        "title": "Mass assignment vulnerability in model or dictionary update",
        "category": "security_misconfiguration",
        "severity": "HIGH",
        "cvss": 7.5,
        "description": "Directly updating database models or user records from unvalidated request dictionaries allows unauthorized privilege escalation.",
        "regex": re.compile(r'(?:user\.__dict__\.update|User\.query\.filter.*?update)\s*\(', re.IGNORECASE),
    },
    {
        "id": "ssrf-request",
        "title": "Server-Side Request Forgery (SSRF) via unvalidated outbound URL fetch",
        "category": "security_misconfiguration",
        "severity": "CRITICAL",
        "cvss": 9.1,
        "description": "Fetching arbitrary caller-supplied URLs without an origin allowlist allows attackers to access internal network services and cloud metadata.",
        "regex": re.compile(r'(?:requests\.get|urllib\.request\.urlopen|httpx\.get)\s*\(\s*(?:url|target_url|request\.args\.get|params\.get)', re.IGNORECASE),
    },
    {
        "id": "unrestricted-upload",
        "title": "Unrestricted file upload with unvalidated filename",
        "category": "security_misconfiguration",
        "severity": "HIGH",
        "cvss": 8.0,
        "description": "Saving uploaded files directly using client-supplied filenames without type validation or destination sanitization can lead to file overwrite or arbitrary code execution.",
        "regex": re.compile(r'(?:file\.save|with open)\s*\(\s*(?:os\.path\.join\(.*?,?\s*file\.filename\)|f["\'].*?\{file\.filename\}|file\.filename)', re.IGNORECASE),
    },
    {
        "id": "stored-xss-template",
        "title": "Cross-Site Scripting (XSS) via unescaped template interpolation",
        "category": "security_misconfiguration",
        "severity": "MEDIUM",
        "cvss": 6.1,
        "description": "Interpolating raw user input directly into HTML templates without proper auto-escaping enables execution of malicious client-side scripts.",
        "regex": re.compile(r'(?:res\.send|response\.write|innerHTML)\s*\(.*?`.*?<.*?\{.*?\}.*?>.*?`', re.DOTALL | re.IGNORECASE),
    },
]


class AstGrepScanner(BaseScanner):
    """ast-grep structural code scanner with pattern fallback."""

    def __init__(self, cli_command: str = "ast-grep") -> None:
        super().__init__(name="ast-grep", cli_command=cli_command)

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
            cmd = [self.cli_command or "ast-grep", "scan", "--json", str(target)]
            code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=120.0)
            if code == 0 and stdout.strip():
                items = json.loads(stdout)
                findings: List[Dict[str, Any]] = []
                for item in items:
                    findings.append({
                        "title": item.get("message", "ast-grep pattern match"),
                        "severity": item.get("severity", "MEDIUM").upper(),
                        "category": "code_vulnerability",
                        "source": self.name,
                        "cvss": 6.0,
                        "file_path": self.relative_path_str(item.get("file", ""), target),
                        "line_number": item.get("range", {}).get("start", {}).get("line"),
                        "description": item.get("message", ""),
                    })
                return findings
        except Exception as exc:
            logger.warning("ast_grep.cli_scan_failed", error=str(exc))
        return None

    def _run_fallback_scan(self, target: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        files = self.walk_files(target, extensions={".py", ".js", ".ts", ".jsx", ".tsx"})

        for f_path in files:
            content = self.read_file_safe(f_path)
            if not content:
                continue

            rel_path = self.relative_path_str(f_path, target)
            lines = content.splitlines()

            for rule in AST_PATTERN_RULES:
                for line_idx, line in enumerate(lines, 1):
                    if rule["regex"].search(line):
                        findings.append({
                            "title": rule["title"],
                            "severity": rule["severity"],
                            "category": rule["category"],
                            "source": self.name,
                            "cvss": rule["cvss"],
                            "file_path": rel_path,
                            "line_number": line_idx,
                            "description": rule["description"],
                        })

        return findings
