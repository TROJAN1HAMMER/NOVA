"""
NOVA — Finding Pydantic Schemas
DTOs for findings returned by the API.
"""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


# ── Compliance Sub-schema ─────────────────────────────────────────────────────

class ComplianceMappingSchema(BaseModel):
    rbi_clause: Optional[str] = None
    pci_clause: Optional[str] = None
    swift_clause: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Finding Response ──────────────────────────────────────────────────────────

class FindingResponse(BaseModel):
    id: uuid.UUID
    scan_job_id: uuid.UUID
    title: str
    severity: str
    category: str
    source: str
    cvss: float
    brs: float
    brs_risk_level: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: str
    package: Optional[str] = None
    package_version: Optional[str] = None
    cve: Optional[str] = None
    ai_explanation: Optional[str] = None
    ai_business_impact: Optional[str] = None
    ai_remediation: Optional[str] = None
    compliance: Optional[ComplianceMappingSchema] = None

    # Aggregation-layer enrichment (app/services/aggregation/) — cross-tool
    # provenance + taxonomy mapping. Full CVE detail and the complete
    # correlation group are in the unified_findings.json report artifact,
    # not duplicated here.
    sources: Optional[list[str]] = None
    occurrence_count: int = 1
    cwe_id: Optional[str] = None
    cwe_name: Optional[str] = None
    owasp_category: Optional[str] = None
    owasp_name: Optional[str] = None
    mitre_technique_ids: Optional[list[str]] = None

    model_config = {"from_attributes": True}


# ── Findings List Response ────────────────────────────────────────────────────

class FindingsListResponse(BaseModel):
    scan_job_id: uuid.UUID
    total: int
    findings: list[FindingResponse]


# ── Internal Finding (used by scanners, not stored yet) ───────────────────────

class RawFinding(BaseModel):
    """Intermediate model passed between scanner services."""
    title: str
    severity: str  # CRITICAL|HIGH|MEDIUM|LOW|INFO
    category: str = "unknown"
    source: str  # semgrep|pip-audit|config-scanner
    cvss: float = 0.0
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: str = ""
    package: Optional[str] = None
    package_version: Optional[str] = None
    cve: Optional[str] = None
