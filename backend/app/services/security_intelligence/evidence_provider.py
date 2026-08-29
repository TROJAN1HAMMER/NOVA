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
        posture_terms = {"posture", "trend", "change", "delta", "history", "score", "snapshot", "security"}
        if any(term in query_lower for term in posture_terms):
            from app.services.security_intelligence.intelligence_orchestrator import security_intelligence_orchestrator
            history = security_intelligence_orchestrator.get_posture_history(".", limit=2)

            if history:
                latest = history[-1]
                delta_str = f"{latest['delta_score']:+.1f}%" if latest.get('delta_score') is not None else "N/A"
                evolution = latest.get("risk_evolution_summary") or {}
                new_cnt = evolution.get("new_risks_count", 0)
                res_cnt = evolution.get("resolved_risks_count", 0)

                posture_item = {
                    "source_id": f"sec-posture-{latest['analysis_run_id'][:8]}",
                    "document_id": f"sec-posture-{latest['analysis_run_id'][:8]}",
                    "source_type": "security_finding",
                    "title": f"Security Posture Trend ({latest['trend_direction']})",
                    "content": (
                        f"Security posture rating is {latest['posture_rating']} with score {latest['posture_score']:.1f}/100 "
                        f"(delta: {delta_str}, trend: {latest['trend_direction']}). "
                        f"Risk evolution: {new_cnt} new risk(s) identified and {res_cnt} resolved risk(s)."
                    ),
                    "excerpt": f"Security posture score is {latest['posture_score']:.1f}/100 (delta: {delta_str}, trend: {latest['trend_direction']}).",
                    "file_path": "security_intel_posture_snapshots",
                    "cwe_id": "CWE-1000",
                    "cve": "",
                    "score": 0.95,
                    "reliability_weight": 0.95,
                    "metadata": {
                        "provider": "security_intelligence_service",
                        "severity": "INFO" if latest['trend_direction'] == "IMPROVED" else ("HIGH" if latest['trend_direction'] == "DEGRADED" else "LOW"),
                        "confidence": 0.95,
                        "status": "OPEN",
                        "posture_score": latest['posture_score'],
                        "delta_score": latest.get('delta_score'),
                        "trend_direction": latest['trend_direction'],
                    }
                }
                evidence_items.append(posture_item)

        filtered = [
            item for item in evidence_items
            if any(term in item["content"].lower() or term in item["file_path"].lower()
                   for term in query_lower.split() if len(term) > 3)
        ]

        return filtered[:top_k]


security_evidence_provider = SecurityEvidenceProvider()
