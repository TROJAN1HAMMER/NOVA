"""
NOVA — Report Pydantic Schemas
`ScanStatusResponse`/`ScanCreateResponse` (the old `Scan`-based DTOs) were
retired along with the `Scan` model — see `app/schemas/scan_job.py` for
their `ScanJob` replacements.
"""

import uuid
from typing import Optional

from pydantic import BaseModel


class ReportStatusDetail(BaseModel):
    """Per-report-type detail — lets a client show "generating"/"failed" instead of just a missing boolean."""

    report_type: str
    status: str  # pending | generating | completed | failed
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportPathsResponse(BaseModel):
    scan_job_id: uuid.UUID
    pdf_available: bool
    pdf_technical_available: bool
    sarif_available: bool
    sbom_available: bool
    unified_findings_available: bool
    compliance_report_available: bool
    csv_available: bool
    reports: list[ReportStatusDetail] = []

    model_config = {"from_attributes": True}
