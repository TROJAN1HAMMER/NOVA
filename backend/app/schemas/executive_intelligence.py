"""
NOVA — Executive Intelligence Schemas
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.assistant import ChatMessage


class ExecutiveAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)


class ExecutiveCitation(BaseModel):
    document_id: str
    filename: str
    page_number: Optional[int] = None
    section_path: Optional[str] = None
    heading: Optional[str] = None
    similarity_score: float
    excerpt: str = Field(max_length=4000)


class RepositoryRiskEvidenceSchema(BaseModel):
    repository_id: str
    repository_name: str
    latest_brs_score: float
    latest_brs_risk_level: Optional[str] = None
    latest_scan_finished_at: Optional[str] = None


class ComplianceFrameworkEvidenceSchema(BaseModel):
    framework_key: str
    framework_name: str
    compliant_repo_count: int
    non_compliant_repo_count: int
    total_violations: int


class WeeklyTrendPointSchema(BaseModel):
    week_start: str
    scan_count: int
    average_brs: Optional[float] = None
    critical_high_findings: int


class WeekOverWeekDeltaSchema(BaseModel):
    scans_this_week: int
    scans_last_week: int
    findings_this_week: int
    findings_last_week: int
    average_brs_this_week: Optional[float] = None
    average_brs_last_week: Optional[float] = None


class EvidenceSnapshotSchema(BaseModel):
    generated_at: str
    total_repositories: int
    total_completed_scans: int
    total_findings: int
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    portfolio_average_brs: Optional[float] = None
    top_risk_repositories: list[RepositoryRiskEvidenceSchema] = Field(default_factory=list)
    compliance_by_framework: list[ComplianceFrameworkEvidenceSchema] = Field(default_factory=list)
    weekly_trend: list[WeeklyTrendPointSchema] = Field(default_factory=list)
    week_over_week: Optional[WeekOverWeekDeltaSchema] = None


class ExecutivePdfExportRequest(BaseModel):
    """
    Carries back exactly what the client already displayed — see
    app/services/executive_intelligence/pdf_export.py's docstring for why
    this is never recomputed server-side at export time.
    """

    question: str = Field(max_length=2000)
    # Milestone 5 hardening: caps how large a PDF this endpoint will ever
    # attempt to render, regardless of what a caller sends — reportlab
    # has no built-in size ceiling of its own.
    answer: str = Field(max_length=20000)
    evidence: EvidenceSnapshotSchema
    citations: list[ExecutiveCitation] = Field(default_factory=list, max_length=20)
    confidence: Optional[float] = None
