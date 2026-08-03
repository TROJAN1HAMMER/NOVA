"""
NOVA — Reports API Routes
Handles serving generated report artifacts.
"""

import uuid
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.auth.dependencies import get_current_active_user
from app.models.report import Report
from app.models.user import User
from app.repositories.deps import get_report_repository
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportPathsResponse, ReportStatusDetail
from app.services.reports.storage import get_storage

logger = structlog.get_logger(__name__)
router = APIRouter()

VALID_REPORT_TYPES = ["pdf", "json", "csv"]

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "json": "application/json",
}


@router.get("/reports/{report_id}", response_model=ReportPathsResponse)
async def get_report_status(
    report_id: uuid.UUID,
    reports: Annotated[ReportRepository, Depends(get_report_repository)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    job_reports = await reports.list_by_scan_job(report_id)
    completed_types = {r.report_type for r in job_reports if r.status == "completed"}

    return ReportPathsResponse(
        scan_job_id=report_id,
        pdf_available="pdf" in completed_types,
        pdf_technical_available=False,
        sarif_available=False,
        sbom_available=False,
        unified_findings_available=False,
        compliance_report_available=False,
        csv_available="csv" in completed_types,
        reports=[
            ReportStatusDetail(report_type=r.report_type, status=r.status, error_message=r.error_message)
            for r in job_reports
        ],
    )
