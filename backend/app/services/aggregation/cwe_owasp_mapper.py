"""
NOVA — CWE, OWASP Top 10, and MITRE ATT&CK Mapping Service
Enriches security findings with standard taxonomy identifiers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaxonomyMapping:
    cwe_id: Optional[str] = None
    cwe_name: Optional[str] = None
    owasp_category: Optional[str] = None
    owasp_name: Optional[str] = None
    mitre_technique_ids: List[str] = field(default_factory=list)


CATEGORY_TAXONOMY_MAP: Dict[str, TaxonomyMapping] = {
    "hardcoded_secret": TaxonomyMapping(
        cwe_id="CWE-798",
        cwe_name="Use of Hard-coded Credentials",
        owasp_category="A07",
        owasp_name="Identification and Authentication Failures",
        mitre_technique_ids=["T1552"],
    ),
    "sql_injection": TaxonomyMapping(
        cwe_id="CWE-89",
        cwe_name="Improper Neutralization of Special Elements used in an SQL Command",
        owasp_category="A03",
        owasp_name="Injection",
        mitre_technique_ids=["T1190"],
    ),
    "command_injection": TaxonomyMapping(
        cwe_id="CWE-78",
        cwe_name="Improper Neutralization of Special Elements used in an OS Command",
        owasp_category="A03",
        owasp_name="Injection",
        mitre_technique_ids=["T1059"],
    ),
    "weak_cryptography": TaxonomyMapping(
        cwe_id="CWE-327",
        cwe_name="Use of a Broken or Risky Cryptographic Algorithm",
        owasp_category="A02",
        owasp_name="Cryptographic Failures",
        mitre_technique_ids=["T1557"],
    ),
    "unsafe_deserialization": TaxonomyMapping(
        cwe_id="CWE-502",
        cwe_name="Deserialization of Untrusted Data",
        owasp_category="A08",
        owasp_name="Software and Data Integrity Failures",
        mitre_technique_ids=["T1203"],
    ),
    "security_misconfiguration": TaxonomyMapping(
        cwe_id="CWE-16",
        cwe_name="Configuration",
        owasp_category="A05",
        owasp_name="Security Misconfiguration",
        mitre_technique_ids=["T1082"],
    ),
    "vulnerable_dependency": TaxonomyMapping(
        cwe_id="CWE-1395",
        cwe_name="Dependency on Vulnerable Third-Party Component",
        owasp_category="A06",
        owasp_name="Vulnerable and Outdated Components",
        mitre_technique_ids=["T1195"],
    ),
    "path_traversal": TaxonomyMapping(
        cwe_id="CWE-22",
        cwe_name="Improper Limitation of a Pathname to a Restricted Directory",
        owasp_category="A01",
        owasp_name="Broken Access Control",
        mitre_technique_ids=["T1083"],
    ),
    "insecure_random": TaxonomyMapping(
        cwe_id="CWE-338",
        cwe_name="Use of Cryptographically Weak Pseudo-Random Number Generator",
        owasp_category="A02",
        owasp_name="Cryptographic Failures",
        mitre_technique_ids=["T1600"],
    ),
}


class CweOwaspMapper:
    @staticmethod
    def map_taxonomy(
        category: str,
        cwe_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> TaxonomyMapping:
        """Map category, title, or CWE identifier to full CWE, OWASP, and MITRE taxonomy metadata."""
        cat_key = (category or "").lower().replace(" ", "_").replace("-", "_")

        if cat_key in CATEGORY_TAXONOMY_MAP:
            mapping = CATEGORY_TAXONOMY_MAP[cat_key]
            # Override cwe_id if explicitly provided
            if cwe_id and not mapping.cwe_id:
                return TaxonomyMapping(
                    cwe_id=cwe_id,
                    cwe_name=mapping.cwe_name,
                    owasp_category=mapping.owasp_category,
                    owasp_name=mapping.owasp_name,
                    mitre_technique_ids=list(mapping.mitre_technique_ids),
                )
            return mapping

        # Default fallback
        return TaxonomyMapping(
            cwe_id=cwe_id or "CWE-699",
            cwe_name="Software Development Vulnerability",
            owasp_category="A00",
            owasp_name="General Security Finding",
            mitre_technique_ids=[],
        )
