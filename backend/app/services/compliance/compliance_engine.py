"""
NOVA — Compliance Engine
Evaluates findings against regulatory compliance frameworks (RBI IT Framework,
PCI DSS v4.0, SWIFT CSP) and computes framework & control-level compliance scores.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ComplianceEvidence:
    finding_title: str
    severity: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    source: str = "scanner"


@dataclass
class ComplianceControlResult:
    requirement_id: str
    title: str
    description: str
    status: str  # "PASS" | "FAIL"
    evidence: List[ComplianceEvidence] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class FrameworkComplianceReport:
    framework_name: str
    short_code: str
    version: str
    controls: List[ComplianceControlResult] = field(default_factory=list)
    total_controls: int = 0
    passed_controls: int = 0
    failed_controls: int = 0
    compliance_percentage: float = 100.0


@dataclass
class ComplianceEngineResult:
    scan_job_id: Optional[str] = None
    frameworks: List[FrameworkComplianceReport] = field(default_factory=list)
    overall_compliance_percentage: float = 100.0


FRAMEWORK_CONTROLS = {
    "RBI": {
        "name": "RBI Cyber Security Framework",
        "short_code": "RBI",
        "version": "2021",
        "controls": [
            {
                "id": "SEC-4.2",
                "title": "Access Control & Identity Management",
                "desc": "Ensure credentials and API secrets are protected against exposure.",
                "categories": ["hardcoded_secret", "broken_authentication"],
                "remediation": "Store secrets securely in secret managers rather than source code.",
            },
            {
                "id": "SEC-5.3",
                "title": "Cryptography & Data Protection",
                "desc": "Use strong cryptographic algorithms and secure RNGs for financial data.",
                "categories": ["weak_cryptography", "insecure_random"],
                "remediation": "Upgrade hashing/ciphers to SHA-256 / AES-256-GCM and use secrets.token_bytes.",
            },
            {
                "id": "SEC-6.4",
                "title": "Application Security & Secure Coding",
                "desc": "Sanitize user input and prevent injection vulnerabilities.",
                "categories": ["sql_injection", "command_injection", "unsafe_deserialization", "path_traversal", "xss"],
                "remediation": "Use parameterized queries, safe deserializers, and strict input validation.",
            },
            {
                "id": "SEC-6.6",
                "title": "Patch and Vulnerability Management",
                "desc": "Keep software dependencies patched against known vulnerabilities.",
                "categories": ["vulnerable_dependency"],
                "remediation": "Upgrade vulnerable third-party dependencies immediately.",
            },
        ],
    },
    "PCI-DSS": {
        "name": "Payment Card Industry Data Security Standard",
        "short_code": "PCI-DSS",
        "version": "v4.0",
        "controls": [
            {
                "id": "REQ-3.4",
                "title": "Render PAN and Authentication Credentials Unreadable",
                "desc": "Prevent hardcoding or exposing keys and cardholder account data.",
                "categories": ["hardcoded_secret"],
                "remediation": "Remove hardcoded credentials and encrypt stored authentication data.",
            },
            {
                "id": "REQ-4.2",
                "title": "Protect Cardholder Data in Transit",
                "desc": "Ensure strong cryptography protocols for transmission.",
                "categories": ["weak_cryptography", "insecure_random"],
                "remediation": "Enforce modern TLS and deprecate insecure cryptographic functions.",
            },
            {
                "id": "REQ-6.2",
                "title": "Bespoke Custom Software Vulnerabilities",
                "desc": "Prevent common coding flaws including injection and path traversal.",
                "categories": ["sql_injection", "command_injection", "path_traversal", "unsafe_deserialization", "xss"],
                "remediation": "Implement secure coding guidelines and automated SAST verification.",
            },
            {
                "id": "REQ-6.3",
                "title": "System Components and Dependency Protection",
                "desc": "Maintain secure component libraries free of known CVEs.",
                "categories": ["vulnerable_dependency"],
                "remediation": "Regularly audit and patch open-source dependencies via SCA scanners.",
            },
        ],
    },
    "SWIFT-CSP": {
        "name": "SWIFT Customer Security Programme",
        "short_code": "SWIFT-CSP",
        "version": "2024",
        "controls": [
            {
                "id": "CTL-2.6",
                "title": "Cryptographic Protection",
                "desc": "Protect confidentiality and integrity using approved ciphers.",
                "categories": ["weak_cryptography", "insecure_random"],
                "remediation": "Implement validated cryptographic modules.",
            },
            {
                "id": "CTL-4.1",
                "title": "Password & Credential Security",
                "desc": "Enforce strong authentication credential handling.",
                "categories": ["hardcoded_secret", "broken_authentication"],
                "remediation": "Never commit plaintext keys or tokens to repository history.",
            },
            {
                "id": "CTL-7.2",
                "title": "Software Integrity & Secure Development",
                "desc": "Protect applications against exploitation and code injection.",
                "categories": ["sql_injection", "command_injection", "unsafe_deserialization"],
                "remediation": "Apply defense-in-depth secure coding and input neutralization.",
            },
        ],
    },
}


def evaluate_compliance(
    findings: List[Dict[str, Any]],
    scan_job_id: Optional[str] = None,
) -> ComplianceEngineResult:
    """Evaluate findings against all regulatory compliance frameworks."""
    framework_reports: List[FrameworkComplianceReport] = []
    total_all_controls = 0
    passed_all_controls = 0

    for fw_key, fw_spec in FRAMEWORK_CONTROLS.items():
        control_results: List[ComplianceControlResult] = []
        fw_passed = 0

        for ctrl in fw_spec["controls"]:
            matched_evidence: List[ComplianceEvidence] = []
            target_categories = set(ctrl["categories"])

            for f in findings:
                f_cat = (f.get("category") or "unknown").lower()
                if f_cat in target_categories or any(c in f_cat for c in target_categories):
                    matched_evidence.append(
                        ComplianceEvidence(
                            finding_title=f.get("title", "Finding"),
                            severity=f.get("severity", "MEDIUM"),
                            file_path=f.get("file_path"),
                            line_number=f.get("line_number"),
                            source=f.get("source", "scanner"),
                        )
                    )

            status = "FAIL" if matched_evidence else "PASS"
            if status == "PASS":
                fw_passed += 1

            control_results.append(
                ComplianceControlResult(
                    requirement_id=ctrl["id"],
                    title=ctrl["title"],
                    description=ctrl["desc"],
                    status=status,
                    evidence=matched_evidence,
                    recommendation=ctrl["remediation"],
                )
            )

        total_fw_controls = len(fw_spec["controls"])
        failed_fw_controls = total_fw_controls - fw_passed
        fw_percentage = round((fw_passed / total_fw_controls) * 100.0, 1) if total_fw_controls else 100.0

        framework_reports.append(
            FrameworkComplianceReport(
                framework_name=fw_spec["name"],
                short_code=fw_spec["short_code"],
                version=fw_spec["version"],
                controls=control_results,
                total_controls=total_fw_controls,
                passed_controls=fw_passed,
                failed_controls=failed_fw_controls,
                compliance_percentage=fw_percentage,
            )
        )

        total_all_controls += total_fw_controls
        passed_all_controls += fw_passed

    overall_pct = (
        round((passed_all_controls / total_all_controls) * 100.0, 1)
        if total_all_controls
        else 100.0
    )

    return ComplianceEngineResult(
        scan_job_id=scan_job_id,
        frameworks=framework_reports,
        overall_compliance_percentage=overall_pct,
    )
