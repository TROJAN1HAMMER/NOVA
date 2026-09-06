"""
NOVA Security Intelligence — Remediation Verifier
Re-evaluates security findings against actual repository source code.
Never trusts frontend text alone: checks the actual file on disk to determine:
  STILL_PRESENT vs VERIFIED_FIXED vs INCONCLUSIVE
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from app.services.security_intelligence.security_rules import static_security_rules_engine
from app.services.security_intelligence.utils import normalize_repo_path

logger = structlog.get_logger(__name__)


class RemediationVerifierService:
    """Re-analyzes code state to verify whether an assessment or finding has been structurally remediated."""

    def verify_remediation(
        self,
        assessment_id: str,
        code_snippet: str = "",
        target_file_path: Optional[str] = None,
        repo_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "security_intel.verifying_remediation",
            assessment_id=assessment_id,
            target_file=target_file_path,
        )

        root = repo_root or Path(".").resolve()
        resolved_file: Optional[Path] = None

        if target_file_path:
            # Strip line number suffix if present (e.g. "routes.py:42" -> "routes.py")
            clean_file_path = target_file_path.split(":line")[0].split(":")[0].strip()
            cand = Path(clean_file_path)
            if cand.is_absolute() and cand.exists() and cand.is_file():
                resolved_file = cand
            else:
                rel_cand = (root / clean_file_path).resolve()
                if rel_cand.exists() and rel_cand.is_file():
                    resolved_file = rel_cand

        # ---------------------------------------------------------------------
        # Tier 1: Real Disk File Re-Analysis (Never Trust Frontend Text Alone)
        # ---------------------------------------------------------------------
        if resolved_file and resolved_file.exists():
            norm_path = normalize_repo_path(resolved_file, root)
            try:
                # Re-run static rules engine on the actual disk file
                findings_after = static_security_rules_engine.analyze_file(resolved_file, root)
                if findings_after:
                    # Vulnerability remains present in source
                    first_f = findings_after[0]
                    return {
                        "assessment_id": assessment_id,
                        "status": "STILL_PRESENT",
                        "fixed": False,
                        "verification_summary": f"Vulnerability STILL_PRESENT in {norm_path}:{first_f.line_number}. Static rule {first_f.rule_id} triggered on current code.",
                        "evidence": first_f.code_snippet,
                        "line_number": first_f.line_number,
                        "target_file": norm_path,
                    }
                else:
                    # Validated clean
                    return {
                        "assessment_id": assessment_id,
                        "status": "VERIFIED_FIXED",
                        "fixed": True,
                        "verification_summary": f"VERIFIED_FIXED: Re-analysis of {norm_path} confirmed no security rule violations remain.",
                        "evidence": "Source file re-analyzed cleanly with 0 rule violations.",
                        "target_file": norm_path,
                    }
            except Exception as exc:
                logger.warning("remediation_verifier.file_analysis_failed", file=str(resolved_file), error=str(exc))
                return {
                    "assessment_id": assessment_id,
                    "status": "INCONCLUSIVE",
                    "fixed": False,
                    "verification_summary": f"INCONCLUSIVE: Failed to re-analyze file {norm_path}: {str(exc)}",
                    "evidence": "",
                    "target_file": norm_path,
                }

        # ---------------------------------------------------------------------
        # Tier 2: Snippet Analysis (When no disk file is available)
        # ---------------------------------------------------------------------
        if not code_snippet or not code_snippet.strip():
            return {
                "assessment_id": assessment_id,
                "status": "INCONCLUSIVE",
                "fixed": False,
                "verification_summary": "INCONCLUSIVE: No target file or code snippet provided to verify.",
                "evidence": "",
            }

        # Check for vulnerable patterns in the snippet
        has_sql_injection = (
            "SELECT " in code_snippet.upper()
            and any(tok in code_snippet for tok in ["f\"", "f'", "%", " + ", ".format("])
        )
        has_vulnerable_pattern = has_sql_injection or any(
            bad in code_snippet for bad in [
                "shell=True", "eval(", "exec(", "AKIA", "verify=False",
                "allow_origins=['*']", "allow_origins=[\"*\"]", "md5(", "sha1("
            ]
        )

        if has_vulnerable_pattern:
            return {
                "assessment_id": assessment_id,
                "status": "STILL_PRESENT",
                "fixed": False,
                "verification_summary": "Vulnerability STILL_PRESENT. Insecure pattern was detected in the submitted patch.",
                "evidence": code_snippet[:200],
                "verification_tiers": {
                    "structural_implementation": False,
                    "control_effectiveness": False,
                },
            }

        # Structural implementation check via AST
        structural_implementation = False
        try:
            tree = ast.parse(code_snippet)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in node.decorator_list:
                        dec_str = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                        if any(kw in dec_str for kw in ["Depends(", "RequireRole", "role", "auth", "permission"]):
                            structural_implementation = True
                            break
                elif isinstance(node, ast.ClassDef):
                    if any("base" in b.id.lower() or "model" in b.id.lower() for b in node.bases if hasattr(b, "id")):
                        structural_implementation = True
        except Exception:
            pass

        has_controls = any(
            kw in code_snippet
            for kw in ["RequireRole", "Depends(", "Pydantic", "BaseModel", "sanitiz", "select(", "getenv", "hashlib.sha256", "bcrypt"]
        )

        if structural_implementation or has_controls:
            return {
                "assessment_id": assessment_id,
                "status": "VERIFIED_FIXED",
                "fixed": True,
                "verification_summary": "VERIFIED_FIXED: Structural security controls detected and dangerous patterns eliminated.",
                "evidence": code_snippet[:200],
                "verification_tiers": {
                    "structural_implementation": True,
                    "control_effectiveness": True,
                },
            }

        return {
            "assessment_id": assessment_id,
            "status": "OPEN",
            "fixed": False,
            "verification_summary": "OPEN: Insufficient evidence to establish whether the finding was fully remediated.",
            "evidence": code_snippet[:200],
            "verification_tiers": {
                "structural_implementation": False,
                "control_effectiveness": False,
            },
        }


remediation_verifier = RemediationVerifierService()
