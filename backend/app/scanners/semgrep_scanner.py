"""
NOVA — Semgrep Scanner Adapter
Executes Semgrep CLI if installed, or falls back to built-in AST and pattern-based static analysis rules.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from app.scanners.base import BaseScanner

logger = structlog.get_logger(__name__)

# Built-in fallback pattern rules for static code analysis
PATTERN_RULES = [
    {
        "id": "sql-injection-concat",
        "title": "SQL query built via string concatenation or interpolation",
        "category": "sql_injection",
        "severity": "HIGH",
        "cvss": 8.5,
        "description": "User-controllable input is directly interpolated or concatenated into a raw SQL query string.",
        "regex": re.compile(
            r'(?:execute|query|raw|cursor\.execute)\s*\(\s*(?:f["\'].*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*?\{.+?\}|["\'].*?(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE).*?["\']\s*[\+%]\s*\w+)',
            re.IGNORECASE,
        ),
    },
    {
        "id": "os-system",
        "title": "Remote command execution via os.system",
        "category": "command_injection",
        "severity": "CRITICAL",
        "cvss": 9.8,
        "description": "os.system executes shell commands without input sanitization, allowing arbitrary command execution.",
        "regex": re.compile(r'os\.system\s*\(\s*(?:f["\'].*?\{.+?\}|["\'].*?["\']\s*[\+%]\s*\w+|\w+)', re.IGNORECASE),
    },
    {
        "id": "command-injection-shell",
        "title": "Command execution via subprocess with shell=True",
        "category": "command_injection",
        "severity": "CRITICAL",
        "cvss": 9.5,
        "description": "subprocess call with shell=True is vulnerable to command injection if arguments contain untrusted input.",
        "regex": re.compile(r'subprocess\.(?:call|Popen|run|check_output)\s*\(.*?shell\s*=\s*True', re.DOTALL),
    },
    {
        "id": "weak-hash-md5",
        "title": "Use of cryptographically weak hash algorithm MD5",
        "category": "weak_cryptography",
        "severity": "HIGH",
        "cvss": 7.5,
        "description": "MD5 is cryptographically broken and vulnerable to collision attacks. It must not be used for security-sensitive operations or passwords.",
        "regex": re.compile(r'hashlib\.md5\s*\(', re.IGNORECASE),
    },
    {
        "id": "weak-hash-sha1",
        "title": "Use of cryptographically weak hash algorithm SHA-1",
        "category": "weak_cryptography",
        "severity": "LOW",
        "cvss": 3.5,
        "description": "SHA-1 is susceptible to collision attacks and should be replaced with SHA-256 or stronger.",
        "regex": re.compile(r'hashlib\.sha1\s*\(', re.IGNORECASE),
    },
    {
        "id": "weak-cipher-des",
        "title": "Use of obsolete and weak DES cipher algorithm",
        "category": "weak_cryptography",
        "severity": "HIGH",
        "cvss": 7.5,
        "description": "DES uses a short 56-bit key susceptible to brute force attacks. Use AES-GCM instead.",
        "regex": re.compile(r'(?:Crypto\.Cipher\.DES|DES\.new|cipher\s*=\s*DES)', re.IGNORECASE),
    },
    {
        "id": "unsafe-pickle",
        "title": "Unsafe deserialization of untrusted data using pickle",
        "category": "unsafe_deserialization",
        "severity": "HIGH",
        "cvss": 8.8,
        "description": "pickle.loads() can execute arbitrary Python bytecode during deserialization of untrusted input.",
        "regex": re.compile(r'pickle\.(?:loads|load)\s*\(', re.IGNORECASE),
    },
    {
        "id": "insecure-random",
        "title": "Use of cryptographically weak pseudo-random number generator for tokens or identifiers",
        "category": "insecure_random",
        "severity": "MEDIUM",
        "cvss": 5.3,
        "description": "Standard pseudo-random generators (such as random.random() or random.randint()) are predictable and unsuitable for security tokens or order IDs.",
        "regex": re.compile(r'random\.(?:random|randint|choice|randrange)\s*\(', re.IGNORECASE),
    },
    {
        "id": "path-traversal",
        "title": "Potential Path Traversal via unvalidated path joining",
        "category": "path_traversal",
        "severity": "HIGH",
        "cvss": 7.5,
        "description": "Constructing filesystem paths from unvalidated user input enables reading or writing arbitrary files outside intended directories.",
        "regex": re.compile(r'(?:os\.path\.join|Path)\s*\(.*?(?:filename|filepath|file_name|path|user_file)\b', re.IGNORECASE),
    },
    {
        "id": "jwt-no-verification",
        "title": "JWT signature verification explicitly disabled",
        "category": "security_misconfiguration",
        "severity": "HIGH",
        "cvss": 8.0,
        "description": "Decoding JWT tokens with verify_signature=False allows attackers to forge authentication tokens and bypass authorization.",
        "regex": re.compile(r'jwt\.decode\s*\(.*?verify_signature["\']?\s*:\s*False', re.DOTALL | re.IGNORECASE),
    },
    {
        "id": "directory-listing",
        "title": "Directory listing misconfiguration on static file route",
        "category": "security_misconfiguration",
        "severity": "MEDIUM",
        "cvss": 5.3,
        "description": "Enabling directory listing exposes internal folder contents and uploaded documents to unauthorized viewers.",
        "regex": re.compile(r'(?:autoindex\s*=\s*True|send_from_directory.*?list_directory|directory_listing\s*=\s*True)', re.IGNORECASE),
    },
]


class SemgrepScanner(BaseScanner):
    """Semgrep SAST scanner with built-in pattern fallback."""

    def __init__(self, cli_command: str = "semgrep") -> None:
        super().__init__(name="semgrep", cli_command=cli_command)

    async def scan(self, target_path: Path | str, **kwargs: Any) -> Dict[str, Any]:
        target = Path(target_path)
        if not target.exists():
            return {"scanner": self.name, "success": False, "findings": [], "error": f"Target path does not exist: {target}"}

        # If CLI is available, try running Semgrep
        if self.is_available():
            findings = await self._run_cli_scan(target)
            if findings is not None:
                return {"scanner": self.name, "success": True, "findings": findings}

        # Fallback to internal pattern rules
        findings = self._run_fallback_scan(target)
        return {"scanner": self.name, "success": True, "findings": findings}

    async def _run_cli_scan(self, target: Path) -> Optional[List[Dict[str, Any]]]:
        try:
            cmd = [self.cli_command or "semgrep", "scan", "--json", "--quiet", str(target)]
            code, stdout, stderr = await self.run_subprocess(cmd, cwd=target, timeout=120.0)
            if code == 0 and stdout.strip():
                data = json.loads(stdout)
                results = data.get("results", [])
                findings: List[Dict[str, Any]] = []
                for res in results:
                    extra = res.get("extra", {})
                    path = res.get("path")
                    start = res.get("start", {})
                    line = start.get("line")
                    sev = str(extra.get("severity", "MEDIUM")).upper()
                    findings.append({
                        "title": extra.get("message", res.get("check_id", "Semgrep finding")),
                        "severity": sev if sev in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"} else "MEDIUM",
                        "category": extra.get("metadata", {}).get("category", "code_vulnerability"),
                        "source": self.name,
                        "cvss": float(extra.get("metadata", {}).get("cvss", 5.0) or 5.0),
                        "file_path": self.relative_path_str(path, target),
                        "line_number": line,
                        "description": extra.get("message", ""),
                    })
                return findings
        except Exception as exc:
            logger.warning("semgrep.cli_scan_failed", error=str(exc))
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

            for rule in PATTERN_RULES:
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
                # Check multiline matches
                if rule["id"] in {"command-injection-shell", "jwt-no-verification"}:
                    for match in rule["regex"].finditer(content):
                        # Approximate line number
                        line_no = content[: match.start()].count("\n") + 1
                        # Avoid duplicate if line-by-line caught it
                        if not any(f["file_path"] == rel_path and f["line_number"] == line_no and f["title"] == rule["title"] for f in findings):
                            findings.append({
                                "title": rule["title"],
                                "severity": rule["severity"],
                                "category": rule["category"],
                                "source": self.name,
                                "cvss": rule["cvss"],
                                "file_path": rel_path,
                                "line_number": line_no,
                                "description": rule["description"],
                            })

        return findings
