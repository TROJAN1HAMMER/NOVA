"""
NOVA — Compliance Mapping Service
Maps vulnerability finding categories to regulatory controls:
  - RBI IT Framework 2021
  - PCI DSS v4.0
  - SWIFT Customer Security Programme (CSP)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Fallback in-memory mappings if data JSON file is absent
DEFAULT_COMPLIANCE_MAPPINGS = {
    "hardcoded_secret": {
        "rbi": "RBI IT Framework 2021 — Section 4.2: Access Control & Identity Management; Annex II: Sensitive Data Protection",
        "pci": "PCI DSS v4.0 — Requirement 8.2: Protect credentials; Requirement 3.4: Render PAN unreadable",
        "swift": "SWIFT CSP Control 4.1: Password Policy; Control 6.1: Operator Session Security",
        "notes": "Hardcoded secrets represent an immediate breach risk.",
    },
    "sql_injection": {
        "rbi": "RBI IT Framework 2021 — Section 6.4: Application Security; Clause 7.1: Secure Coding Standards",
        "pci": "PCI DSS v4.0 — Requirement 6.2: Bespoke and custom software; Requirement 6.3.1: Security vulnerabilities",
        "swift": "SWIFT CSP Control 3.2: Malware Protection; Control 7.2: Software Integrity",
        "notes": "SQL Injection is in OWASP Top 10 (A03:2021).",
    },
    "command_injection": {
        "rbi": "RBI IT Framework 2021 — Section 6.4: Application Security; Clause 7.1: Secure Coding Standards",
        "pci": "PCI DSS v4.0 — Requirement 6.2.4: Common attacks; Requirement 6.3.1: Vulnerabilities",
        "swift": "SWIFT CSP Control 7.2: Software Integrity; Control 3.2: Malware Protection",
        "notes": "Command injection allows execution of arbitrary OS commands.",
    },
    "weak_cryptography": {
        "rbi": "RBI IT Framework 2021 — Section 5.3: Cryptography Policy; Annex IV: Encryption Standards",
        "pci": "PCI DSS v4.0 — Requirement 4.2.1: Strong cryptography; Requirement 3.5: Use strong cryptography",
        "swift": "SWIFT CSP Control 2.6: Cryptographic Controls; Control 4.2: Data Encryption",
        "notes": "Weak hashing or ciphers violate banking cryptography standards.",
    },
    "unsafe_deserialization": {
        "rbi": "RBI IT Framework 2021 — Section 6.4: Application Security; Clause 6.5: Input Validation",
        "pci": "PCI DSS v4.0 — Requirement 6.2.4: Attacks on data integrity; Requirement 6.3.3: All components protected",
        "swift": "SWIFT CSP Control 7.2: Software Integrity; Control 3.1: Malware Protection",
        "notes": "Unsafe deserialization can lead to Remote Code Execution.",
    },
    "security_misconfiguration": {
        "rbi": "RBI IT Framework 2021 — Section 4.4: Security Configuration Management; Clause 8.1: Environment Hardening",
        "pci": "PCI DSS v4.0 — Requirement 2.2: System components configured and managed; Requirement 6.2: Secure configurations",
        "swift": "SWIFT CSP Control 2.7: System Hardening; Control 1.1: Environment Security",
        "notes": "Security misconfigurations violate CIS hardening baselines.",
    },
    "vulnerable_dependency": {
        "rbi": "RBI IT Framework 2021 — Section 6.6: Patch and Vulnerability Management; Clause 6.7: Third-party Risk",
        "pci": "PCI DSS v4.0 — Requirement 6.3.3: All system components protected from known vulnerabilities; Requirement 12.8: Third-party service providers",
        "swift": "SWIFT CSP Control 7.1: Vulnerability Scanning; Control 7.3: Patch Management",
        "notes": "Software Composition Analysis (SCA) is mandatory.",
    },
    "path_traversal": {
        "rbi": "RBI IT Framework 2021 — Section 6.4: Application Security; Clause 6.5: Input Validation",
        "pci": "PCI DSS v4.0 — Requirement 6.2.4: Common vulnerability attacks; Requirement 6.3.1",
        "swift": "SWIFT CSP Control 3.2: Malware Protection; Control 7.2: Software Integrity",
        "notes": "Path traversal allows unauthorized file access.",
    },
    "insecure_random": {
        "rbi": "RBI IT Framework 2021 — Section 5.3: Cryptography Policy; Annex IV: Random Number Generation",
        "pci": "PCI DSS v4.0 — Requirement 3.5: Cryptographic key generation; Requirement 4.2.1: Strong cryptography",
        "swift": "SWIFT CSP Control 2.6: Cryptographic Controls",
        "notes": "Non-cryptographic RNGs must not generate session tokens or keys.",
    },
    "unknown": {
        "rbi": "RBI IT Framework 2021 — Section 6.4: Application Security (General)",
        "pci": "PCI DSS v4.0 — Requirement 6.2: Software security (General)",
        "swift": "SWIFT CSP Control 7.2: Software Integrity (General)",
        "notes": "Review finding manually for regulatory mapping.",
    },
}


@dataclass
class ComplianceMappingData:
    rbi_clause: Optional[str] = None
    pci_clause: Optional[str] = None
    swift_clause: Optional[str] = None
    notes: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class ComplianceMapper:
    def __init__(self, data_path: Optional[Path] = None) -> None:
        self._mappings: Dict[str, Dict[str, str]] = {}
        self._load_mappings(data_path)

    def _load_mappings(self, data_path: Optional[Path]) -> None:
        if data_path and data_path.exists():
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    self._mappings = json.load(f)
                    return
            except Exception:
                pass

        # Try default relative location
        default_file = Path(__file__).parent.parent.parent / "data" / "compliance_mappings.json"
        if default_file.exists():
            try:
                with open(default_file, "r", encoding="utf-8") as f:
                    self._mappings = json.load(f)
                    return
            except Exception:
                pass

        self._mappings = DEFAULT_COMPLIANCE_MAPPINGS

    def map_finding(self, category: str, cwe_id: Optional[str] = None) -> ComplianceMappingData:
        """Map finding category and optional CWE to compliance clauses."""
        cat_key = category.lower().replace(" ", "_").replace("-", "_")
        mapping = self._mappings.get(cat_key) or self._mappings.get("unknown", {})
        return ComplianceMappingData(
            rbi_clause=mapping.get("rbi"),
            pci_clause=mapping.get("pci"),
            swift_clause=mapping.get("swift"),
            notes=mapping.get("notes"),
        )

    def summarize_compliance(self, findings: List[Any]) -> Dict[str, Any]:
        """Produce a compliance framework coverage summary across a list of findings."""
        rbi_violations = 0
        pci_violations = 0
        swift_violations = 0

        for f in findings:
            rbi = getattr(f, "rbi_clause", None)
            pci = getattr(f, "pci_clause", None)
            swift = getattr(f, "swift_clause", None)

            if rbi:
                rbi_violations += 1
            if pci:
                pci_violations += 1
            if swift:
                swift_violations += 1

        return {
            "rbi_it_framework": {"status": "non_compliant" if rbi_violations > 0 else "compliant", "violations_count": rbi_violations},
            "pci_dss_v4": {"status": "non_compliant" if pci_violations > 0 else "compliant", "violations_count": pci_violations},
            "swift_csp": {"status": "non_compliant" if swift_violations > 0 else "compliant", "violations_count": swift_violations},
        }


_global_mapper: Optional[ComplianceMapper] = None


def get_compliance_mapper() -> ComplianceMapper:
    global _global_mapper
    if _global_mapper is None:
        _global_mapper = ComplianceMapper()
    return _global_mapper
