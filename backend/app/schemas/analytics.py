"""
NOVA — Activity Analytics Schemas
Backs the two role-dashboard analytics endpoints
(app/api/v1/endpoints/analytics.py): a Security Analyst's own scan
activity, and a Security Manager's org-wide view of the same shape,
broken down per user. Both are built entirely from data that already
exists (ScanJob/ScanResult/Finding) — no new tables.
"""

import uuid
from typing import Optional

from pydantic import BaseModel


class RecentScanSummary(BaseModel):
    scan_job_id: uuid.UUID
    repository_name: str
    status: str
    brs_score: Optional[float] = None
    brs_risk_level: Optional[str] = None
    finished_at: Optional[str] = None


class MyActivitySummary(BaseModel):
    """A Security Analyst's own workload/efficiency view — see
    ROLE_DISPLAY_NAMES in app/auth/permissions.py for the role mapping."""

    total_scans: int
    scans_by_status: dict[str, int]
    total_findings: int
    findings_by_severity: dict[str, int]
    average_scan_duration_seconds: Optional[float] = None
    average_brs_score: Optional[float] = None
    recent_scans: list[RecentScanSummary]


class TeamMemberActivity(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    total_scans: int
    total_findings: int
    average_brs_score: Optional[float] = None


class TeamActivitySummary(BaseModel):
    """Org-wide scan-activity aggregation for a Security Manager — how much
    got scanned, by whom, what it found. Deliberately not the same thing as
    the audit log (who changed what) — see Permission.TEAM_ANALYTICS_READ's
    docstring."""

    total_scans: int
    total_findings: int
    members: list[TeamMemberActivity]
