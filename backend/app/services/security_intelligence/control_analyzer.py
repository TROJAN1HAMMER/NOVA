"""
NOVA Security Intelligence — Security Control Analyzer
Evaluates security controls independently across software assets and codebases
based on real static evidence (PASS / PRESENT, PARTIAL, FAIL / ABSENT, UNKNOWN).
Outputs fully informative controls with control_id, name, domain, status, evidence references, and rationale.
"""

import datetime
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


@dataclass
class SecurityControlEvaluation:
    control_id: str = "GEN-001"
    control_name: str = "General Control"
    domain: str = "Application Security"
    control_type: str = "AUTHORIZATION"
    scope: str = "."
    status: str = "UNKNOWN"
    state: str = "UNKNOWN"
    evidence_count: int = 0
    evidence_references: List[str] = field(default_factory=list)
    evidence_summary: str = ""
    rationale: str = ""
    limitations: str = ""
    evidence: str = ""
    primary_location: str = ""
    confidence: float = 0.85
    lifecycle_state: str = "CONTROL_EVALUATED"
    parent_observation_ids: List[str] = field(default_factory=list)
    evaluation_timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def __post_init__(self):
        if self.evidence and not self.evidence_summary:
            self.evidence_summary = self.evidence



class ControlAnalyzerService:
    """Evaluates security controls across endpoints, code paths, repositories, and configurations."""

    def evaluate_controls(
        self,
        asset_name: str,
        location: str,
        repo_root: Optional[Path] = None,
        observations: Optional[List[Any]] = None,
    ) -> List[SecurityControlEvaluation]:
        logger.info("security_intel.evaluating_controls", asset_name=asset_name, location=location)
        controls: List[SecurityControlEvaluation] = []

        root = repo_root or Path(".").resolve()
        loc_path = Path(location)
        if not loc_path.is_absolute():
            resolved_target = (root / loc_path).resolve()
        else:
            resolved_target = loc_path

        from app.services.security_intelligence.repository_ingestion import IGNORED_DIRS

        SUPPORTED_CRYPTO_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java"}
        EXCLUDED_LOCKFILES = {
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
            "composer.lock", "gemfile.lock", "cargo.lock"
        }
        EXCLUDED_BINARY_EXTS = {
            ".pkl", ".h5", ".bin", ".pt", ".onnx", ".model", ".weights",
            ".tar", ".gz", ".zip", ".7z", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2"
        }
        auth_signals = ["jwt.decode", "oauth2", "get_current_user", "passport.authenticate", "bcrypt", "argon2", "hash_password", "bearertoken", "@login_required"]
        authz_signals = ["requirerole", "has_permission", "require_permission", "has_role", "authorize", "@preauthorize", "role."]
        val_signals = ["basemodel", "pydantic", "zod", "joi", "form(", "query(", "body(", "validator", "sqlalchemy", "select("]
        env_signals = ["os.getenv", "process.env", "environ", "settings."]
        cfg_signals = ["corsmiddleware", "allow_origins", "strict-transport-security", "content-security-policy", "x-frame-options"]
        crypto_pat = re.compile(
            r'(?<![a-zA-Z0-9_-])(?:sha256|sha512|bcrypt|argon2|cryptography|fernet|aes(?:-(?:128|192|256|gcm|cbc|ctr))?)(?![a-zA-Z0-9_=-])',
            re.IGNORECASE
        )

        auth_ev_locations: List[str] = []
        authz_ev_locations: List[str] = []
        val_ev_locations: List[str] = []
        env_ev_locations: List[str] = []
        cfg_ev_locations: List[str] = []
        crypto_ev_locations: List[str] = []

        all_content = ""
        crypto_source_content = ""

        def _scan_content_lines(fp_obj: Path, text: str):
            rel = normalize_repo_path(str(fp_obj), root)
            ext = fp_obj.suffix.lower()
            fname = fp_obj.name.lower()
            for idx, raw_line in enumerate(text.splitlines(), 1):
                line = raw_line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                loc = f"{rel}:{idx}"
                if any(s in line_lower for s in auth_signals) and loc not in auth_ev_locations:
                    auth_ev_locations.append(loc)
                if any(s in line_lower for s in authz_signals) and loc not in authz_ev_locations:
                    authz_ev_locations.append(loc)
                if any(s in line_lower for s in val_signals) and loc not in val_ev_locations:
                    val_ev_locations.append(loc)
                if any(s in line_lower for s in env_signals) and loc not in env_ev_locations:
                    env_ev_locations.append(loc)
                if any(s in line_lower for s in cfg_signals) and loc not in cfg_ev_locations:
                    cfg_ev_locations.append(loc)
                if (
                    ext in SUPPORTED_CRYPTO_EXTENSIONS
                    and fname not in EXCLUDED_LOCKFILES
                    and ext not in EXCLUDED_BINARY_EXTS
                    and not any(ign in line_lower for ign in ["integrity", "checksum", "sha512-", "sha384-", "sha256-"])
                    and crypto_pat.search(line)
                    and loc not in crypto_ev_locations
                ):
                    crypto_ev_locations.append(loc)

        try:
            if resolved_target.is_file():
                content = resolved_target.read_text(encoding="utf-8", errors="ignore")[:30000]
                all_content = content
                _scan_content_lines(resolved_target, content)
                if (
                    resolved_target.suffix.lower() in SUPPORTED_CRYPTO_EXTENSIONS
                    and resolved_target.name.lower() not in EXCLUDED_LOCKFILES
                    and resolved_target.suffix.lower() not in EXCLUDED_BINARY_EXTS
                ):
                    crypto_source_content = content
            elif resolved_target.is_dir():
                for r, dirs, files in os.walk(resolved_target):
                    # Prune ignored and hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]
                    for f in files:
                        fname = f.lower()
                        ext = Path(f).suffix.lower()
                        if fname in EXCLUDED_LOCKFILES or ext in EXCLUDED_BINARY_EXTS:
                            continue

                        fp = Path(r) / f
                        try:
                            if fp.stat().st_size < 100 * 1024:
                                file_text = fp.read_text(encoding="utf-8", errors="ignore")[:5000] + "\n"
                                if ext in [".py", ".ts", ".js", ".json", ".yml", ".yaml"]:
                                    all_content += file_text
                                    _scan_content_lines(fp, file_text)
                                if ext in SUPPORTED_CRYPTO_EXTENSIONS:
                                    crypto_source_content += file_text
                        except Exception:
                            pass
        except Exception:
            pass


        # Extract findings from observations
        obs_findings = []
        env_obs = []
        db_obs = []
        if observations:
            for o in observations:
                fd = getattr(o, "finding_data", None)
                if not fd and isinstance(getattr(o, "attributes", None), dict):
                    fd = o.attributes.get("finding_data")
                if fd:
                    obs_findings.append(fd)
                obs_type = getattr(o, "observation_type", "")
                if obs_type == "ENV_CONFIG_READ":
                    env_obs.append(o)
                elif obs_type == "DATABASE_ACCESS":
                    db_obs.append(o)

        finding_rules = {getattr(f, "rule_id", "") for f in obs_findings}
        norm_scope = normalize_repo_path(location, root)

        # -------------------------------------------------------------------------
        # 1. AUTH-001: Authentication Controls (Identity & Access)
        # -------------------------------------------------------------------------
        found_auth_signals = [s for s in auth_signals if s in all_content.lower()]
        auth_findings = [f for f in obs_findings if getattr(f, "category", "") == "AUTHENTICATION_AUTHORIZATION" and "auth" in getattr(f, "rule_id", "").lower()]

        if auth_findings:
            auth_status, auth_state = "FAIL", "ABSENT"
            auth_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in auth_findings]
            auth_summary = f"Authentication bypass or vulnerability detected ({len(auth_findings)} findings)."
            auth_rationale = "Authentication controls failed verification due to vulnerable or bypassed authentication handlers."
            auth_limitations = ""
        elif found_auth_signals:
            auth_status, auth_state = "PASS", "PRESENT"
            auth_ev_refs = auth_ev_locations[:3] if auth_ev_locations else ([f"{norm_scope}"] if norm_scope != "." else [])
            auth_summary = f"Authentication mechanisms detected ({', '.join(found_auth_signals[:3])})."
            auth_rationale = "Token verification or credential hashing guards are present on protected service routes."
            auth_limitations = ""
        else:
            auth_status, auth_state = "UNKNOWN", "UNKNOWN"
            auth_ev_refs = []
            auth_summary = "No authentication mechanisms detected."
            auth_rationale = "No supported evidence was found to determine this control."
            auth_limitations = "No token verification, session middleware, or authentication handlers detected in evaluated scope."

        controls.append(SecurityControlEvaluation(
            control_id="AUTH-001",
            control_name="Authentication Controls",
            domain="Identity & Access",
            control_type="AUTHENTICATION",
            scope=norm_scope,
            status=auth_status,
            state=auth_state,
            evidence_count=len(auth_ev_refs),
            evidence_references=auth_ev_refs,
            evidence_summary=auth_summary,
            rationale=auth_rationale,
            limitations=auth_limitations,
            primary_location=auth_ev_refs[0] if auth_ev_refs else norm_scope,
            confidence=0.88,
        ))

        # -------------------------------------------------------------------------
        # 2. AUTHZ-001: Role-Based Authorization Controls (Identity & Access)
        # -------------------------------------------------------------------------
        found_authz_signals = [s for s in authz_signals if s in all_content.lower()]
        authz_findings = [f for f in obs_findings if "AUT001" in getattr(f, "rule_id", "")]

        if authz_findings:
            authz_status, authz_state = "FAIL", "ABSENT"
            authz_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in authz_findings]
            authz_summary = "Privileged routes lack required role-based authorization guards."
            authz_rationale = "Administrative operations exposed without RBAC permission enforcement."
            authz_limitations = ""
        elif found_authz_signals:
            authz_status, authz_state = "PASS", "PRESENT"
            authz_ev_refs = authz_ev_locations[:3] if authz_ev_locations else ([f"{norm_scope}"] if norm_scope != "." else [])
            authz_summary = f"Role-based authorization guards enforced ({', '.join(found_authz_signals[:2])})."
            authz_rationale = "Role-based access control (RBAC) middleware or dependency guards verified on service routes."
            authz_limitations = ""
        else:
            authz_status, authz_state = "UNKNOWN", "UNKNOWN"
            authz_ev_refs = []
            authz_summary = "No explicit authorization enforcement detected."
            authz_rationale = "No supported evidence was found to determine this control."
            authz_limitations = "No role checking, permission guards, or access control policies detected in evaluated scope."

        controls.append(SecurityControlEvaluation(
            control_id="AUTHZ-001",
            control_name="Authorization & Access Control",
            domain="Identity & Access",
            control_type="AUTHORIZATION",
            scope=norm_scope,
            status=authz_status,
            state=authz_state,
            evidence_count=len(authz_ev_refs),
            evidence_references=authz_ev_refs,
            evidence_summary=authz_summary,
            rationale=authz_rationale,
            limitations=authz_limitations,
            primary_location=authz_ev_refs[0] if authz_ev_refs else norm_scope,
            confidence=0.90,
        ))

        # -------------------------------------------------------------------------
        # 3. INPJ-001: Input Validation & Injection Controls (Application Security)
        # -------------------------------------------------------------------------
        inj_findings = [f for f in obs_findings if getattr(f, "category", "") == "INJECTION"]
        found_val_signals = [s for s in val_signals if s in all_content.lower()]

        if inj_findings:
            val_status, val_state = "FAIL", "ABSENT"
            val_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in inj_findings]
            val_summary = f"Dynamic query concatenation or unsafe command execution detected ({len(inj_findings)} findings)."
            val_rationale = "Unparameterized database queries or unvalidated command executions expose the component to injection."
            val_limitations = ""
        elif found_val_signals:
            val_status, val_state = "PASS", "PRESENT"
            val_ev_refs = val_ev_locations[:3] if val_ev_locations else ([f"{norm_scope}"] if norm_scope != "." else [])
            val_summary = f"Schema validation and parameterization verified ({', '.join(found_val_signals[:2])})."
            val_rationale = "Structured schema validation (Pydantic/ORM) and parameterized data parsing active."
            val_limitations = ""
        else:
            val_status, val_state = "UNKNOWN", "UNKNOWN"
            val_ev_refs = []
            val_summary = "No input validation schemas detected."
            val_rationale = "No supported evidence was found to determine this control."
            val_limitations = "No structured validation schemas or parameterized database query calls detected in evaluated scope."

        controls.append(SecurityControlEvaluation(
            control_id="INPJ-001",
            control_name="Input Validation & Injection Prevention",
            domain="Application Security",
            control_type="INPUT_VALIDATION",
            scope=norm_scope,
            status=val_status,
            state=val_state,
            evidence_count=len(val_ev_refs),
            evidence_references=val_ev_refs,
            evidence_summary=val_summary,
            rationale=val_rationale,
            limitations=val_limitations,
            primary_location=val_ev_refs[0] if val_ev_refs else norm_scope,
            confidence=0.90,
        ))

        # -------------------------------------------------------------------------
        # 4. SECM-001: Secrets Management & Key Storage (Data Protection)
        # -------------------------------------------------------------------------
        secret_findings = [f for f in obs_findings if getattr(f, "category", "") == "SECRET_EXPOSURE"]
        has_env = "os.getenv" in all_content or "process.env" in all_content or "environ" in all_content or "settings." in all_content or len(env_obs) > 0

        if secret_findings:
            sec_status, sec_state = "FAIL", "ABSENT"
            sec_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in secret_findings]
            sec_summary = f"Plaintext secret or hardcoded credential detected ({len(secret_findings)} findings)."
            sec_rationale = "Sensitive credentials or cryptographic key material committed directly to source repository."
            sec_limitations = ""
        elif has_env:
            sec_status, sec_state = "PASS", "PRESENT"
            sec_ev_refs = [normalize_repo_path(o.location, root) for o in env_obs[:3]] or env_ev_locations[:3] or ([f"{norm_scope}"] if norm_scope != "." else [])
            sec_summary = "Environment variable & configuration secret management active without hardcoded secrets."
            sec_rationale = "Application configuration loads secrets via environment variables or external configuration."
            sec_limitations = ""
        else:
            sec_status, sec_state = "UNKNOWN", "UNKNOWN"
            sec_ev_refs = []
            sec_summary = "No secret management mechanism detected."
            sec_rationale = "No supported evidence was found to determine this control."
            sec_limitations = "No environment variable calls or hardcoded secret patterns detected in evaluated scope."

        controls.append(SecurityControlEvaluation(
            control_id="SECM-001",
            control_name="Secrets Management & Key Storage",
            domain="Data Protection",
            control_type="SECRET_MANAGEMENT",
            scope=norm_scope,
            status=sec_status,
            state=sec_state,
            evidence_count=len(sec_ev_refs),
            evidence_references=sec_ev_refs,
            evidence_summary=sec_summary,
            rationale=sec_rationale,
            limitations=sec_limitations,
            primary_location=sec_ev_refs[0] if sec_ev_refs else norm_scope,
            confidence=0.92,
        ))

        # -------------------------------------------------------------------------
        # 5. CONF-001: Secure Configuration & Transport (Infrastructure & Perimeter)
        # -------------------------------------------------------------------------
        cfg_findings = [f for f in obs_findings if getattr(f, "category", "") == "CONFIGURATION"]

        if cfg_findings:
            cfg_status, cfg_state = "FAIL", "ABSENT"
            cfg_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in cfg_findings]
            cfg_summary = f"Insecure configuration detected ({len(cfg_findings)} findings)."
            cfg_rationale = "Insecure configuration items detected (e.g. debug mode enabled or wildcard CORS)."
            cfg_limitations = ""
        elif any(sec_cfg in all_content.lower() for sec_cfg in cfg_signals):
            cfg_status, cfg_state = "PASS", "PRESENT"
            cfg_ev_refs = cfg_ev_locations[:3] if cfg_ev_locations else ([f"{norm_scope}"] if norm_scope != "." else [])
            cfg_summary = "Transport security and CORS middleware configuration active."
            cfg_rationale = "Application configuration enforces standard security policies without detected misconfigurations."
            cfg_limitations = ""
        else:
            cfg_status, cfg_state = "UNKNOWN", "UNKNOWN"
            cfg_ev_refs = []
            cfg_summary = "No explicit transport or security headers configuration detected."
            cfg_rationale = "No supported evidence was found to determine this control."
            cfg_limitations = "No explicit transport or security headers configuration detected in evaluated scope."

        controls.append(SecurityControlEvaluation(
            control_id="CONF-001",
            control_name="Secure Configuration & Transport",
            domain="Infrastructure & Perimeter",
            control_type="SECURE_CONFIGURATION",
            scope=norm_scope,
            status=cfg_status,
            state=cfg_state,
            evidence_count=len(cfg_ev_refs),
            evidence_references=cfg_ev_refs,
            evidence_summary=cfg_summary,
            rationale=cfg_rationale,
            limitations=cfg_limitations,
            primary_location=cfg_ev_refs[0] if cfg_ev_refs else norm_scope,
            confidence=0.86,
        ))

        # -------------------------------------------------------------------------
        # 6. CRYP-001: Cryptographic Controls (Data Protection)
        # -------------------------------------------------------------------------
        cry_findings = [f for f in obs_findings if getattr(f, "category", "") == "CRYPTOGRAPHY"]

        valid_crypto_lines = []
        for line in crypto_source_content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if any(ign in line_str.lower() for ign in ["integrity", "checksum", "sha512-", "sha384-", "sha256-"]):
                continue
            if crypto_pat.search(line_str):
                valid_crypto_lines.append(line_str)

        has_strong_crypto = len(valid_crypto_lines) > 0


        if cry_findings:
            cry_status, cry_state = "FAIL", "ABSENT"
            cry_ev_refs = [normalize_repo_path(f"{f.file_path}:{f.line_number}", root) for f in cry_findings]
            cry_summary = f"Weak cryptographic hash algorithm detected ({len(cry_findings)} findings)."
            cry_rationale = f"Use of broken cryptographic hash algorithms (MD5 / SHA1) detected in {', '.join(cry_ev_refs[:2])}."
            cry_limitations = ""
        elif has_strong_crypto:
            cry_status, cry_state = "PASS", "PRESENT"
            cry_ev_refs = crypto_ev_locations[:3] if crypto_ev_locations else ([f"{norm_scope}"] if norm_scope != "." else [])
            cry_summary = "Modern cryptographic primitives verified."
            cry_rationale = "Modern cryptographic primitives (SHA-256 / bcrypt / AES) utilized for data protection."
            cry_limitations = ""
        else:
            cry_status, cry_state = "UNKNOWN", "UNKNOWN"
            cry_ev_refs = []
            cry_summary = "No cryptographic primitives detected."
            cry_rationale = "No supported evidence was found to determine this control."
            cry_limitations = "No modern cryptographic primitives (SHA-256/bcrypt/AES) detected in application source code."

        controls.append(SecurityControlEvaluation(
            control_id="CRYP-001",
            control_name="Cryptographic Controls",
            domain="Data Protection",
            control_type="ENCRYPTION",
            scope=norm_scope,
            status=cry_status,
            state=cry_state,
            evidence_count=len(cry_ev_refs),
            evidence_references=cry_ev_refs,
            evidence_summary=cry_summary,
            rationale=cry_rationale,
            limitations=cry_limitations,
            primary_location=cry_ev_refs[0] if cry_ev_refs else norm_scope,
            confidence=0.88,
        ))

        logger.info("security_intel.controls_evaluated", count=len(controls))
        return controls


control_analyzer = ControlAnalyzerService()
