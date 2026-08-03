"""
NOVA — Compliance Engine Pydantic Schemas
API-facing DTOs mirroring `app/services/compliance/compliance_engine.py`'s
plain dataclasses (same pattern as brs_engine.py: the engine itself has
zero Pydantic/FastAPI dependency, only the API boundary does).
"""

from typing import Optional

from pydantic import BaseModel


class ComplianceEvidenceSchema(BaseModel):
    finding_title: str
    severity: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    source: str


class ComplianceControlResultSchema(BaseModel):
    requirement_id: str
    title: str
    description: str
    status: str  # "PASS" | "FAIL"
    evidence: list[ComplianceEvidenceSchema]
    recommendation: str


class FrameworkComplianceReportSchema(BaseModel):
    framework_name: str
    short_code: str
    version: str
    controls: list[ComplianceControlResultSchema]
    total_controls: int
    passed_controls: int
    failed_controls: int
    compliance_percentage: float


class ComplianceEngineResultSchema(BaseModel):
    scan_job_id: Optional[str] = None
    frameworks: list[FrameworkComplianceReportSchema]
    overall_compliance_percentage: float
