"""
NOVA — Reports API Routes
Handles serving generated report artifacts.
"""

import uuid
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.models.report import Report
from app.models.user import User
from app.repositories.deps import get_report_repository
from app.repositories.report_repository import ReportRepository
from app.schemas.report import ReportPathsResponse, ReportStatusDetail
from app.services.reports.storage import get_storage

logger = structlog.get_logger(__name__)
router = APIRouter()

VALID_REPORT_TYPES = [
    "pdf",
    "pdf_technical",
    "json",
    "csv",
    "sarif",
    "sbom",
    "unified_findings",
    "compliance_report",
]

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "pdf_technical": "application/pdf",
    "csv": "text/csv",
    "json": "application/json",
    "sarif": "application/json",
    "sbom": "application/json",
    "unified_findings": "application/json",
    "compliance_report": "application/json",
}


@router.get("/reports/{report_id}", response_model=ReportPathsResponse)
async def get_report_status(
    report_id: uuid.UUID,
    reports: Annotated[ReportRepository, Depends(get_report_repository)],
    _current_user: Annotated[User, Depends(require_permission(Permission.REPORT_READ))],
):
    job_reports = await reports.list_by_scan_job(report_id)
    completed_types = {r.report_type for r in job_reports if r.status == "completed"}

    return ReportPathsResponse(
        scan_job_id=report_id,
        pdf_available="pdf" in completed_types,
        pdf_technical_available="pdf_technical" in completed_types,
        sarif_available="sarif" in completed_types,
        sbom_available="sbom" in completed_types,
        unified_findings_available="unified_findings" in completed_types,
        compliance_report_available="compliance_report" in completed_types,
        csv_available="csv" in completed_types,
        reports=[
            ReportStatusDetail(report_type=r.report_type, status=r.status, error_message=r.error_message)
            for r in job_reports
        ],
    )


@router.get("/reports/{scan_job_id}/download/{report_type}")
async def download_report(
    scan_job_id: uuid.UUID,
    report_type: str,
    reports: Annotated[ReportRepository, Depends(get_report_repository)],
    _current_user: Annotated[User, Depends(require_permission(Permission.REPORT_DOWNLOAD))],
):
    """
    Download a specific generated report artifact.
    - Local storage: streams the file directly via FileResponse.
    - S3 storage: redirects (307) to a presigned URL.
    """
    report = await reports.get_by_type(scan_job_id, report_type)
    if report is None:
        raise NotFoundError(f"Report '{report_type}' for scan job '{scan_job_id}' not found.")

    if report.status in ("pending", "generating"):
        raise ConflictError(f"Report '{report_type}' generation is still in progress (status: {report.status}).")

    if report.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {report.error_message or 'Unknown error'}",
        )

    storage = get_storage()
    download_ref = storage.get_download_reference(report.storage_key or report.file_path or "")

    if download_ref.presigned_url:
        logger.info("reports_api.redirect_to_s3", scan_job_id=str(scan_job_id), report_type=report_type)
        return RedirectResponse(url=download_ref.presigned_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    if download_ref.local_path:
        if not download_ref.local_path.exists():
            logger.error("reports_api.file_missing_on_disk", scan_job_id=str(scan_job_id), path=str(download_ref.local_path))
            raise NotFoundError(f"Report file not found on storage: {download_ref.local_path.name}")

        media_type = MEDIA_TYPES.get(report_type, "application/octet-stream")
        ext = "pdf" if "pdf" in report_type else ("json" if any(k in report_type for k in ("json", "sarif", "sbom", "compliance", "findings")) else report_type)
        filename = f"nova-{report_type}-{scan_job_id}.{ext}"

        logger.info("reports_api.streaming_local_file", scan_job_id=str(scan_job_id), filename=filename)
        return FileResponse(
            path=str(download_ref.local_path),
            media_type=media_type,
            filename=filename,
        )

    raise NotFoundError("Report download reference could not be resolved.")
