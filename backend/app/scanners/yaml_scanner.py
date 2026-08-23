"""
NOVA — YAML & Infrastructure as Code (IaC) Scanner Adapter
Analyzes GitHub Actions workflows, Kubernetes manifests, Compose files, and YAML configurations for security misconfigurations.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)


class YamlScanner(BaseScanner):
    """YAML, Kubernetes, and GitHub Actions workflow security scanner."""

    def __init__(self, cli_command: str = "yamllint") -> None:
        super().__init__(name="yaml", cli_command=cli_command)

    async def scan(self, target_path: Path | str, **kwargs: Any) -> Dict[str, Any]:
        target = Path(target_path)
        if not target.exists():
            return {"scanner": self.name, "success": False, "findings": [], "error": f"Target path does not exist: {target}"}

        # Run built-in IaC and YAML security rules
        findings = self._run_fallback_scan(target)
        return {"scanner": self.name, "success": True, "findings": findings}

    def _run_fallback_scan(self, target: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        yaml_files = self.walk_files(target, extensions={".yml", ".yaml"})

        for yf in yaml_files:
            content = self.read_file_safe(yf)
            if not content:
                continue

            rel_path = self.relative_path_str(yf, target)
            lines = content.splitlines()

            # 1. Check GitHub Actions Workflows (.github/workflows/)
            if ".github" in rel_path and "workflows" in rel_path:
                has_pr_target = False
                pr_target_line = None
                for idx, line in enumerate(lines, 1):
                    if re.search(r'\bpull_request_target\b', line):
                        has_pr_target = True
                        pr_target_line = idx

                if has_pr_target:
                    findings.append({
                        "title": "GitHub Actions workflow triggers on pull_request_target with potential untrusted checkout",
                        "severity": "CRITICAL",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 9.5,
                        "file_path": rel_path,
                        "line_number": pr_target_line,
                        "description": "pull_request_target runs in the context of the base repository with access to repository secrets. Checking out PR code allows fork PRs to execute arbitrary commands and exfiltrate secrets.",
                    })

                # Check for mutable action tags (e.g. @v4, @main instead of full 40-char commit SHA)
                for idx, line in enumerate(lines, 1):
                    m = re.search(r'uses:\s*([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)@([a-zA-Z0-9_.-]+)', line)
                    if m:
                        ref = m.group(2)
                        # If not a 40-character hex commit SHA
                        if not (len(ref) == 40 and all(c in "0123456789abcdefABCDEF" for c in ref)):
                            findings.append({
                                "title": f"GitHub Action step unpinned: uses mutable tag @{ref}",
                                "severity": "LOW",
                                "category": "security_misconfiguration",
                                "source": self.name,
                                "cvss": 3.7,
                                "file_path": rel_path,
                                "line_number": idx,
                                "description": f"Third-party action {m.group(1)} should be pinned to a full commit SHA to prevent supply chain compromise via mutable tags.",
                            })

            # 2. Check Kubernetes manifests (k8s/ or manifests/)
            for idx, line in enumerate(lines, 1):
                if re.search(r'privileged\s*:\s*true', line, re.IGNORECASE):
                    findings.append({
                        "title": "Privileged container execution configured in manifest",
                        "severity": "CRITICAL",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 9.0,
                        "file_path": rel_path,
                        "line_number": idx,
                        "description": "privileged: true provides container full access to host devices and bypasses security boundaries.",
                    })
                if re.search(r'runAsUser\s*:\s*0\b', line):
                    findings.append({
                        "title": "Kubernetes workload configured to run explicitly as root user (runAsUser: 0)",
                        "severity": "CRITICAL",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 8.5,
                        "file_path": rel_path,
                        "line_number": idx,
                        "description": "runAsUser: 0 runs container processes with host root permissions.",
                    })
                if re.search(r'hostNetwork\s*:\s*true', line, re.IGNORECASE):
                    findings.append({
                        "title": "Kubernetes pod configured with hostNetwork: true",
                        "severity": "CRITICAL",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 8.8,
                        "file_path": rel_path,
                        "line_number": idx,
                        "description": "hostNetwork: true allows pods to bind to host network interfaces and snoop on node traffic.",
                    })

            # 3. Check configuration files (config/*.yaml or settings.yaml)
            for idx, line in enumerate(lines, 1):
                if re.search(r'allow_origins\s*:\s*["\']?\*["\']?', line, re.IGNORECASE):
                    findings.append({
                        "title": "Wildcard cross-origin policy (CORS allow_origins: '*') configured",
                        "severity": "MEDIUM",
                        "category": "security_misconfiguration",
                        "source": self.name,
                        "cvss": 5.3,
                        "file_path": rel_path,
                        "line_number": idx,
                        "description": "Configuring Access-Control-Allow-Origin: * on authenticated internal APIs allows unauthorized external websites to read responses.",
                    })

        return findings
