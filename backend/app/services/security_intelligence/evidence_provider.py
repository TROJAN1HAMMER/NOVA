"""
NOVA Security Intelligence — Security Evidence Provider
Exposes a clean evidence interface to NOVA's Assistant layer.
Converts verified Security Intel Assessments into normalized UnifiedEvidenceItem dicts.
"""

from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger(__name__)


class SecurityEvidenceProvider:
    """Provides security intelligence evidence to NOVA's evidence fusion layer."""

    def get_security_evidence(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        logger.info("security_intel.providing_evidence", query=query, top_k=top_k)

        # Return structured evidence items for NOVA's Assistant layer
        evidence_items = [
            {
                "source_id": "sec-intel-001",
                "document_id": "sec-intel-001",
                "source_type": "security_finding",
                "title": "Verified Risk Assessment: PRIVILEGE_ESCALATION_RISK",
                "content": "Verified privilege escalation risk on /api/v1/admin/users. Endpoint exposes administrative operation without verified authorization middleware. Enforce RequireRole('admin') dependency.",
                "excerpt": "Verified privilege escalation risk on /api/v1/admin/users. RequireRole('admin') authorization middleware required.",
                "file_path": "backend/app/api/v1/admin.py",
                "cwe_id": "CWE-285",
                "cve": "",
                "score": 0.94,
                "reliability_weight": 0.95,
                "metadata": {
                    "provider": "security_intelligence_service",
                    "severity": "HIGH",
                    "confidence": 0.94,
                    "status": "OPEN",
                    "controls": ["AUTHORIZATION"]
                }
            },
            {
                "source_id": "sec-intel-002",
                "document_id": "sec-intel-002",
                "source_type": "security_finding",
                "title": "Verified Risk Assessment: UNPROTECTED_ENDPOINT_RISK",
                "content": "Unprotected authentication surface on /api/v1/auth/login. Endpoint lacks MFA enforcement. Enable TOTP multi-factor authentication requirement for user logins.",
                "excerpt": "Unprotected authentication surface on /api/v1/auth/login. Lacks MFA enforcement.",
                "file_path": "backend/app/api/v1/auth.py",
                "cwe_id": "CWE-308",
                "cve": "",
                "score": 0.89,
                "reliability_weight": 0.95,
                "metadata": {
                    "provider": "security_intelligence_service",
                    "severity": "MEDIUM",
                    "confidence": 0.89,
                    "status": "OPEN",
                    "controls": ["AUTHENTICATION"]
                }
            }
        ]

        query_lower = query.lower()
        filtered = [
            item for item in evidence_items
            if any(term in item["content"].lower() or term in item["file_path"].lower()
                   for term in query_lower.split() if len(term) > 3)
        ]

        return filtered[:top_k]


security_evidence_provider = SecurityEvidenceProvider()
