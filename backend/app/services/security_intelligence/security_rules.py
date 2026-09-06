"""
NOVA Security Intelligence — Static Security Rules Engine
Implements evidence-based, defensible static analysis rules across Python, JS/TS, Java, and configs.
Provides exact line numbers, code spans, confidence, severity, and secret masking.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import structlog

from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


def mask_secret(secret_str: str) -> str:
    """Safely masks secret strings for logs, UI, and evidence."""
    if not secret_str:
        return "[EMPTY]"
    s = secret_str.strip()
    if len(s) <= 8:
        return "****"
    return f"{s[:4]}...{s[-3:]}"


@dataclass
class StaticFindingData:
    finding_id: str
    rule_id: str
    title: str
    category: str  # SECRET_EXPOSURE, INJECTION, AUTHENTICATION_AUTHORIZATION, CONFIGURATION, CRYPTOGRAPHY, DEPENDENCIES
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    confidence: float
    file_path: str
    line_number: int
    code_snippet: str
    reasoning: str
    remediation: str
    related_control: str  # SECRET_MANAGEMENT, AUTHENTICATION, AUTHORIZATION, INPUT_VALIDATION, ENCRYPTION, SECURE_CONFIGURATION, DEPENDENCY_GOVERNANCE
    cwe_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)


# Regex Patterns for Static Checks
AWS_KEY_PATTERN = re.compile(r"(?:^|[^A-Z0-9])(AKIA[0-9A-Z]{16})(?:[^A-Z0-9]|$)", re.IGNORECASE)
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----")
GENERIC_SECRET_PATTERN = re.compile(
    r"""(?i)(?:api_key|apikey|secret_key|app_secret|auth_token|access_token|private_key|db_password|password)\s*[:=]\s*["']([^"'\s]{8,})["']"""
)
DB_CONN_CREDENTIALS = re.compile(r"""(?:postgres|postgresql|mysql|mongodb|redis)://([^:]+):([^@]+)@([a-zA-Z0-9_.-]+)""")

SQL_CONCAT_PATTERN = re.compile(
    r"""(?i)(?:select|insert|update|delete|drop|union)\s+.*(?:\+|%|format\(|f["']).*|f["'].*(?:select|insert|update|delete|drop|union)\s+.*""",
    re.IGNORECASE,
)
COMMAND_INJECTION_PATTERN = re.compile(
    r"""(?i)(?:os\.system|os\.popen|subprocess\.call|subprocess\.Popen|subprocess\.run)\s*\([^)]*shell\s*=\s*True""",
    re.IGNORECASE,
)
EVAL_EXEC_PATTERN = re.compile(r"""(?i)\b(?:eval|exec)\s*\([^)]+\)""")

DEBUG_MODE_PATTERN = re.compile(r"""(?i)\b(?:debug|DEBUG)\s*=\s*(?:True|true|1|["']true["'])""")
CORS_WILDCARD_PATTERN = re.compile(r"""(?i)(?:allow_origins|origins)\s*=\s*\[?\s*["']\*["']\s*\]?""")
INSECURE_TLS_PATTERN = re.compile(r"""(?i)(?:verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true)""")
MD5_SHA1_PATTERN = re.compile(r"""(?i)(?:hashlib\.md5|hashlib\.sha1|createHash\(["']md5["']\)|createHash\(["']sha1["']\)|getInstance\(["']MD5["']\))""")


class StaticSecurityRulesEngine:
    """Evaluates security rules against codebase files and AST structures."""

    def analyze_file(self, file_path: Path, repo_root: Path) -> List[StaticFindingData]:
        findings: List[StaticFindingData] = []
        rel_path = normalize_repo_path(file_path, repo_root)

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as exc:
            logger.warning("security_rules.read_failed", file=rel_path, error=str(exc))
            return findings

        lines = content.splitlines()

        # 1. Regex-based pattern matching line by line
        for line_idx, line in enumerate(lines, start=1):
            if len(line) > 1000:
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "/*", "*")):
                continue

            # Check: AWS Access Keys
            aws_match = AWS_KEY_PATTERN.search(line)
            if aws_match:
                key_val = aws_match.group(1)
                findings.append(StaticFindingData(
                    finding_id=f"FIND-SEC-{rel_path}-{line_idx}",
                    rule_id="SEC001_AWS_CREDENTIAL",
                    title="Exposed Hardcoded AWS Access Key",
                    category="SECRET_EXPOSURE",
                    severity="CRITICAL",
                    confidence=0.98,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.replace(key_val, mask_secret(key_val)).strip(),
                    reasoning=f"Hardcoded AWS credential pattern ({mask_secret(key_val)}) was detected in source code. Credentials committed to source control can lead to unauthorized cloud infrastructure access.",
                    remediation="Remove hardcoded credentials immediately. Rotate the exposed key in AWS IAM and load secrets using environment variables or a secure secrets manager.",
                    related_control="SECRET_MANAGEMENT",
                    cwe_id="CWE-798",
                ))

            # Check: Private Keys
            if PRIVATE_KEY_PATTERN.search(line):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-SEC-KEY-{rel_path}-{line_idx}",
                    rule_id="SEC002_PRIVATE_KEY",
                    title="Exposed Cryptographic Private Key Material",
                    category="SECRET_EXPOSURE",
                    severity="CRITICAL",
                    confidence=0.99,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet="-----BEGIN PRIVATE KEY----- [MASKED] -----END PRIVATE KEY-----",
                    reasoning="Unencrypted cryptographic private key material was detected directly in source code.",
                    remediation="Remove private keys from repository history. Use a dedicated key management service (KMS) or secure vault for private keys.",
                    related_control="SECRET_MANAGEMENT",
                    cwe_id="CWE-312",
                ))

            # Check: Hardcoded Secret Assignment
            sec_match = GENERIC_SECRET_PATTERN.search(line)
            if sec_match and not any(ign in rel_path.lower() for ign in ["test", "mock", "fixture", "example", ".env.example"]):
                secret_val = sec_match.group(1)
                if not any(placeholder in secret_val.lower() for placeholder in ["your_", "example", "placeholder", "changeme", "default", "xxxx"]):
                    findings.append(StaticFindingData(
                        finding_id=f"FIND-GEN-SEC-{rel_path}-{line_idx}",
                        rule_id="SEC003_HARDCODED_SECRET",
                        title="Hardcoded API Key / Secret Credential",
                        category="SECRET_EXPOSURE",
                        severity="HIGH",
                        confidence=0.88,
                        file_path=rel_path,
                        line_number=line_idx,
                        code_snippet=line.replace(secret_val, mask_secret(secret_val)).strip(),
                        reasoning=f"Hardcoded secret assignment was detected in {rel_path}. Storing secrets in plaintext increases risk of credential leakage.",
                        remediation="Store secrets in environment variables or configuration management files excluded via .gitignore.",
                        related_control="SECRET_MANAGEMENT",
                        cwe_id="CWE-798",
                    ))

            # Check: Database URI Credentials
            db_match = DB_CONN_CREDENTIALS.search(line)
            if db_match and not any(ign in rel_path.lower() for ign in ["test", "mock", "example", ".env.example"]):
                user, pwd = db_match.group(1), db_match.group(2)
                findings.append(StaticFindingData(
                    finding_id=f"FIND-DB-URI-{rel_path}-{line_idx}",
                    rule_id="SEC004_DATABASE_CREDENTIALS",
                    title="Database Connection String with Embedded Password",
                    category="SECRET_EXPOSURE",
                    severity="HIGH",
                    confidence=0.92,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.replace(pwd, mask_secret(pwd)).strip(),
                    reasoning="Database connection string with embedded plaintext credentials detected in source code.",
                    remediation="Construct database connection URIs dynamically using environment variables.",
                    related_control="SECRET_MANAGEMENT",
                    cwe_id="CWE-259",
                ))

            # Check: SQL Injection via string formatting/concatenation
            if SQL_CONCAT_PATTERN.search(line) and not any(ign in rel_path.lower() for ign in ["test", "conftest"]):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-SQL-INJ-{rel_path}-{line_idx}",
                    rule_id="INJ001_SQL_INJECTION",
                    title="Potential SQL Injection via Unparameterized Query",
                    category="INJECTION",
                    severity="HIGH",
                    confidence=0.91,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Query constructed using dynamic string formatting/concatenation. This can allow arbitrary SQL execution if variables include untrusted user input.",
                    remediation="Use parameterized queries (e.g., cursor.execute(query, (params,))) or an ORM like SQLAlchemy.",
                    related_control="INPUT_VALIDATION",
                    cwe_id="CWE-89",
                ))

            # Check: Command Injection (shell=True)
            if COMMAND_INJECTION_PATTERN.search(line):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-CMD-INJ-{rel_path}-{line_idx}",
                    rule_id="INJ002_COMMAND_INJECTION",
                    title="Command Execution with Shell=True",
                    category="INJECTION",
                    severity="CRITICAL",
                    confidence=0.94,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Invoking system commands with shell=True allows command chaining and arbitrary OS command execution if inputs are user-controlled.",
                    remediation="Pass command arguments as a list without shell=True, or use shlex.quote() to sanitize parameters.",
                    related_control="INPUT_VALIDATION",
                    cwe_id="CWE-78",
                ))

            # Check: Insecure Eval/Exec
            if EVAL_EXEC_PATTERN.search(line) and not any(ign in rel_path.lower() for ign in ["test", "setup.py"]):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-EVAL-{rel_path}-{line_idx}",
                    rule_id="INJ003_DYNAMIC_EVAL",
                    title="Unsafe Dynamic Code Evaluation (eval/exec)",
                    category="INJECTION",
                    severity="CRITICAL",
                    confidence=0.90,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Dynamic evaluation functions (eval/exec) can execute arbitrary code in the process context.",
                    remediation="Refactor code to use explicit data parsing (e.g. json.loads or ast.literal_eval) instead of dynamic evaluation.",
                    related_control="INPUT_VALIDATION",
                    cwe_id="CWE-95",
                ))

            # Check: Weak Hashing Algorithm
            if MD5_SHA1_PATTERN.search(line):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-CRYPTO-HASH-{rel_path}-{line_idx}",
                    rule_id="CRY001_WEAK_HASH",
                    title="Use of Broken Cryptographic Hash (MD5 / SHA1)",
                    category="CRYPTOGRAPHY",
                    severity="MEDIUM",
                    confidence=0.91,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="MD5 and SHA-1 are cryptographically broken and susceptible to collision attacks.",
                    remediation="Upgrade to SHA-256/SHA-512 for cryptographic integrity, or bcrypt/argon2id for password hashing.",
                    related_control="ENCRYPTION",
                    cwe_id="CWE-328",
                ))

            # Check: Insecure TLS / SSL Verification Disabled
            if INSECURE_TLS_PATTERN.search(line):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-TLS-DIS-{rel_path}-{line_idx}",
                    rule_id="CFG001_TLS_VERIFY_DISABLED",
                    title="TLS Certificate Validation Disabled",
                    category="CONFIGURATION",
                    severity="HIGH",
                    confidence=0.93,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Disabling TLS certificate verification allows Machine-in-the-Middle (MitM) attacks against network traffic.",
                    remediation="Enable standard TLS certificate validation by removing verify=False / rejectUnauthorized: false.",
                    related_control="SECURE_CONFIGURATION",
                    cwe_id="CWE-295",
                ))

            # Check: Debug Mode Enabled in Non-Test Code
            if DEBUG_MODE_PATTERN.search(line) and not any(ign in rel_path.lower() for ign in ["test", "conftest"]):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-CFG-DEBUG-{rel_path}-{line_idx}",
                    rule_id="CFG002_DEBUG_ENABLED",
                    title="Application Debug Mode Explicitly Enabled",
                    category="CONFIGURATION",
                    severity="MEDIUM",
                    confidence=0.85,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Enabling debug mode in production can expose stack traces, internal variables, and diagnostic endpoints.",
                    remediation="Ensure debug flags are disabled in production or bound to environment variables that default to False.",
                    related_control="SECURE_CONFIGURATION",
                    cwe_id="CWE-489",
                ))

            # Check: Overly Permissive CORS
            if CORS_WILDCARD_PATTERN.search(line):
                findings.append(StaticFindingData(
                    finding_id=f"FIND-CFG-CORS-{rel_path}-{line_idx}",
                    rule_id="CFG003_PERMISSIVE_CORS",
                    title="Wildcard Cross-Origin Resource Sharing (CORS)",
                    category="CONFIGURATION",
                    severity="LOW",
                    confidence=0.86,
                    file_path=rel_path,
                    line_number=line_idx,
                    code_snippet=line.strip(),
                    reasoning="Configuring allow_origins=['*'] allows any website to make cross-origin requests to this service.",
                    remediation="Specify explicit trusted origin domains in CORS middleware configurations.",
                    related_control="SECURE_CONFIGURATION",
                    cwe_id="CWE-942",
                ))

        # 2. Python AST Analysis for Deeper Structural Checks
        if file_path.suffix == ".py":
            findings.extend(self._analyze_python_ast(content, rel_path, lines))

        return findings

    def _analyze_python_ast(self, content: str, rel_path: str, lines: List[str]) -> List[StaticFindingData]:
        ast_findings: List[StaticFindingData] = []
        try:
            tree = ast.parse(content, filename=rel_path)
        except Exception:
            return ast_findings

        for node in ast.walk(tree):
            # Check: SQL Injection via string formatting/concatenation in function calls
            if isinstance(node, ast.Call):
                func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
                if any(sql_kw in func_name.lower() for sql_kw in ["execute", "raw", "select", "cursor", "query"]):
                    if node.args:
                        first_arg = node.args[0]
                        # Check: f-string or % or + string concatenation in execute(...)
                        if isinstance(first_arg, (ast.JoinedStr, ast.BinOp)):
                            arg_str = ast.unparse(first_arg) if hasattr(ast, "unparse") else ""
                            line_no = getattr(node, "lineno", 1)
                            if any(kw in arg_str.upper() for kw in ["SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "FROM"]):
                                ast_findings.append(StaticFindingData(
                                    finding_id=f"FIND-SQL-INJ-{rel_path}-{line_no}",
                                    rule_id="INJ001_SQL_INJECTION",
                                    title="Potential SQL Injection via Unparameterized Query",
                                    category="INJECTION",
                                    severity="HIGH",
                                    confidence=0.92,
                                    file_path=rel_path,
                                    line_number=line_no,
                                    code_snippet=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else arg_str,
                                    reasoning=f"Query constructed using dynamic string formatting/concatenation ({arg_str[:60]}...). This can allow arbitrary SQL execution if variables include untrusted user input.",
                                    remediation="Use parameterized queries (e.g., cursor.execute(query, (params,))) or an ORM like SQLAlchemy.",
                                    related_control="INPUT_VALIDATION",
                                    cwe_id="CWE-89",
                                ))

            # Check: Administrative Route Missing Authorization Dependency
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                line_no = getattr(node, "lineno", 1)
                for decorator in node.decorator_list:
                    dec_str = ast.unparse(decorator) if hasattr(ast, "unparse") else ""
                    if any(r_kw in dec_str for r_kw in ["router.", "app."]) and any(adm in node.name.lower() or adm in dec_str.lower() for adm in ["admin", "user_delete", "grant_role", "set_role", "promote"]):
                        # Check if authorization dependency is present
                        has_authz = "RequireRole" in dec_str or "Role" in dec_str or "admin" in dec_str or "Depends(" in dec_str
                        if not has_authz:
                            ast_findings.append(StaticFindingData(
                                finding_id=f"FIND-AUTHZ-MISSING-{rel_path}-{line_no}",
                                rule_id="AUT001_MISSING_AUTHORIZATION",
                                title="Administrative Route Missing Authorization Guard",
                                category="AUTHENTICATION_AUTHORIZATION",
                                severity="HIGH",
                                confidence=0.87,
                                file_path=rel_path,
                                line_number=line_no,
                                code_snippet=lines[line_no - 1].strip() if 0 <= line_no - 1 < len(lines) else dec_str,
                                reasoning=f"Privileged administrative route function '{node.name}' does not enforce an explicit role-based access control dependency in its route decorator.",
                                remediation="Add role-based authorization dependency, e.g., dependencies=[Depends(RequireRole('admin'))].",
                                related_control="AUTHORIZATION",
                                cwe_id="CWE-285",
                            ))

        return ast_findings


static_security_rules_engine = StaticSecurityRulesEngine()
