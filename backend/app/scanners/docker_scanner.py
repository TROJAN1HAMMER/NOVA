"""
NOVA — Dockerfile & Container Security Scanner Adapter
Executes Hadolint CLI if installed, or falls back to rule-based container misconfiguration analysis.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)


class DockerScanner(BaseScanner):
    """Docker and container configuration scanner."""

    def __init__(self, cli_command: str = "hadolint") -> None:
        super().__init__(name="docker", cli_command=cli_command)

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
            dockerfiles = self.walk_files(target, include_filenames={"dockerfile", "dockerfile.dev", "dockerfile.prod"})
            if not dockerfiles:
                return []

            findings: List[Dict[str, Any]] = []
            for df in dockerfiles:
                cmd = [self.cli_command or "hadolint", "-f", "json", str(df)]
                code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=60.0)
                if stdout.strip():
                    items = json.loads(stdout)
                    for item in items:
                        sev_map = {"error": "HIGH", "warning": "MEDIUM", "info": "LOW", "style": "INFO"}
                        level = sev_map.get(item.get("level", "warning").lower(), "MEDIUM")
                        findings.append({
                            "title": item.get("message", "Dockerfile configuration issue"),
                            "severity": level,
                            "category": "security_misconfiguration",
                            "source": self.name,
                            "cvss": 5.0 if level == "MEDIUM" else (7.0 if level == "HIGH" else 3.0),
                            "file_path": self.relative_path_str(df, target),
                            "line_number": item.get("line"),
                            "description": item.get("message", ""),
                        })
            return findings
        except Exception as exc:
            logger.warning("docker.cli_scan_failed", error=str(exc))
        return None

    def _run_fallback_scan(self, target: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Analyze Dockerfile
        dockerfiles = self.walk_files(target, include_filenames={"dockerfile", "dockerfile.dev", "dockerfile.prod"})
        for df in dockerfiles:
            content = self.read_file_safe(df)
            if not content:
                continue

            rel_path = self.relative_path_str(df, target)
            lines = content.splitlines()

            # Check for non-root USER directive
            has_user_directive = any(re.match(r'^\s*USER\s+(?!root\b)[a-zA-Z0-9_-]+', l, re.IGNORECASE) for l in lines)
            runs_explicit_root = any(re.match(r'^\s*USER\s+root\b', l, re.IGNORECASE) for l in lines)

            if runs_explicit_root or not has_user_directive:
                # Find line number if explicit
                root_line = next((idx for idx, l in enumerate(lines, 1) if re.match(r'^\s*USER\s+root\b', l, re.IGNORECASE)), 1)
                findings.append({
                    "title": "Container runs as root user without least-privilege USER directive",
                    "severity": "CRITICAL" if runs_explicit_root else "MEDIUM",
                    "category": "security_misconfiguration",
                    "source": self.name,
                    "cvss": 8.5 if runs_explicit_root else 5.3,
                    "file_path": rel_path,
                    "line_number": root_line,
                    "description": "Running containers as root allows potential container escape to compromise the host operating system.",
                })

            # Check for retained build toolchain in non-multistage Dockerfile
            is_multistage = content.count("FROM ") > 1
            if not is_multistage and re.search(r'apt-get install.*?(?:build-essential|gcc|g\+\+|make)', content, re.IGNORECASE):
                build_line = next((idx for idx, l in enumerate(lines, 1) if re.search(r'(?:build-essential|gcc|g\+\+|make)', l)), None)
                findings.append({
                    "title": "Dockerfile retains development and build toolchain in production image",
                    "severity": "LOW",
                    "category": "security_misconfiguration",
                    "source": self.name,
                    "cvss": 3.5,
                    "file_path": rel_path,
                    "line_number": build_line,
                    "description": "Including gcc/build-essential in production images expands attack surface and enables local compilation of exploit payloads.",
                })

        # 2. Analyze docker-compose.yml
        compose_files = self.walk_files(target, include_filenames={"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
        for cf in compose_files:
            content = self.read_file_safe(cf)
            if not content:
                continue

            rel_path = self.relative_path_str(cf, target)
            lines = content.splitlines()

            for line_idx, line in enumerate(lines, 1):
                if re.search(r'privileged\s*:\s*true', line, re.IGNORECASE):
                    findings.append({
                        "title": "Docker container configured with privileged execution mode",
                        "severity": "CRITICAL",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 9.0,
                        "file_path": rel_path,
                        "line_number": line_idx,
                        "description": "privileged: true disables all container isolation boundaries, giving full access to all host devices and kernel capabilities.",
                    })

        return findings
