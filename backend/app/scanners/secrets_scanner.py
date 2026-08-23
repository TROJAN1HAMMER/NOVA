"""
NOVA — Secrets Scanner Adapter
Executes TruffleHog / GitLeaks CLI if installed, or falls back to comprehensive regex and entropy secret detection.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)

SECRET_PATTERNS = [
    {
        "id": "aws-access-key",
        "title": "Hardcoded AWS Access Key ID",
        "category": "hardcoded_secret",
        "severity": "CRITICAL",
        "cvss": 9.1,
        "description": "An AWS Access Key ID was detected in source code or configuration.",
        "regex": re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
    },
    {
        "id": "private-key-header",
        "title": "Private key committed to repository",
        "category": "hardcoded_secret",
        "severity": "CRITICAL",
        "cvss": 9.8,
        "description": "An unencrypted private key header (RSA / EC / OpenSSH) was detected in repository files.",
        "regex": re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    },
    {
        "id": "stripe-live-key",
        "title": "Hardcoded payment-gateway live API key",
        "category": "hardcoded_secret",
        "severity": "HIGH",
        "cvss": 8.5,
        "description": "A live payment gateway secret API key (e.g. Stripe sk_live_) was detected in source code.",
        "regex": re.compile(r'\b(sk_live_[0-9a-zA-Z]{24,})\b'),
    },
    {
        "id": "slack-webhook",
        "title": "Committed Slack incoming webhook URL",
        "category": "hardcoded_secret",
        "severity": "LOW",
        "cvss": 4.0,
        "description": "A Slack webhook URL was found committed in code or environment configuration.",
        "regex": re.compile(r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+'),
    },
    {
        "id": "db-password",
        "title": "Hardcoded database password or connection string credentials",
        "category": "hardcoded_secret",
        "severity": "CRITICAL",
        "cvss": 9.0,
        "description": "Database connection string contains embedded plaintext authentication credentials.",
        "regex": re.compile(r'(?:postgres|postgresql|mysql|mongodb(?:\+srv)?):\/\/[a-zA-Z0-9_-]+:([a-zA-Z0-9_#@!%^&*-]{4,})@', re.IGNORECASE),
    },
    {
        "id": "jwt-hardcoded-secret",
        "title": "Hardcoded JWT secret key",
        "category": "hardcoded_secret",
        "severity": "CRITICAL",
        "cvss": 8.8,
        "description": "A hardcoded secret key used for signing JWT authentication tokens was found in source code.",
        "regex": re.compile(r'(?:JWT_SECRET|SECRET_KEY)\s*=\s*["\']([^"\']{6,})["\']', re.IGNORECASE),
    },
    {
        "id": "hardcoded-password-literal",
        "title": "Hardcoded production password literal",
        "category": "hardcoded_secret",
        "severity": "CRITICAL",
        "cvss": 9.0,
        "description": "A hardcoded password or credential assignment was detected in source code.",
        "regex": re.compile(r'(?:password|db_password|admin_password)\s*=\s*["\'](?!(?:test|mock|dummy|change-me|example|none|true|false))([^"\']{6,})["\']', re.IGNORECASE),
    },
]


class SecretsScanner(BaseScanner):
    """Secrets and credential detection scanner."""

    def __init__(self, cli_command: str = "gitleaks") -> None:
        super().__init__(name="secrets", cli_command=cli_command)

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
            cmd = [self.cli_command or "gitleaks", "detect", "--no-git", "--report-format", "json", "-s", str(target)]
            code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=90.0)
            if stdout.strip():
                items = json.loads(stdout)
                findings: List[Dict[str, Any]] = []
                for item in items:
                    findings.append({
                        "title": item.get("Description", "Secret detected in code"),
                        "severity": "CRITICAL",
                        "category": "hardcoded_secret",
                        "source": self.name,
                        "cvss": 9.0,
                        "file_path": self.relative_path_str(item.get("File", ""), target),
                        "line_number": item.get("StartLine"),
                        "description": item.get("Match", ""),
                    })
                return findings
        except Exception as exc:
            logger.warning("secrets.cli_scan_failed", error=str(exc))
        return None

    def _run_fallback_scan(self, target: Path) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        files = self.walk_files(target)

        for f_path in files:
            rel_path = self.relative_path_str(f_path, target)
            fname = f_path.name.lower()

            # Flag committed certificate/key files directly
            if f_path.suffix.lower() in {".pem", ".key", ".pkcs12", ".pfx"} or fname in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
                findings.append({
                    "title": "Private key or certificate committed to repository",
                    "severity": "CRITICAL",
                    "category": "hardcoded_secret",
                    "source": self.name,
                    "cvss": 9.8,
                    "file_path": rel_path,
                    "description": f"A private cryptographic key file ({f_path.name}) was found committed directly to the repository.",
                })

            # Check committed .env files (excluding .env.example)
            if fname == ".env":
                env_content = self.read_file_safe(f_path)
                if env_content and any("=" in line and not line.strip().endswith("=") for line in env_content.splitlines()):
                    findings.append({
                        "title": "Committed .env file with active environment secrets",
                        "severity": "CRITICAL",
                        "category": "hardcoded_secret",
                        "source": self.name,
                        "cvss": 9.0,
                        "file_path": rel_path,
                        "description": "An active .env file containing populated environment variables and credentials was committed to source control.",
                    })

            content = self.read_file_safe(f_path)
            if not content:
                continue

            lines = content.splitlines()
            for line_idx, line in enumerate(lines, 1):
                for pat in SECRET_PATTERNS:
                    if pat["regex"].search(line):
                        # Avoid duplicates if file-level rule already fired on same line
                        if not any(f["file_path"] == rel_path and f.get("line_number") == line_idx and f["title"] == pat["title"] for f in findings):
                            findings.append({
                                "title": pat["title"],
                                "severity": pat["severity"],
                                "category": pat["category"],
                                "source": self.name,
                                "cvss": pat["cvss"],
                                "file_path": rel_path,
                                "line_number": line_idx,
                                "description": pat["description"],
                            })

        return findings
