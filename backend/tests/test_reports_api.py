"""
NOVA — Reports API Endpoint & Download Pipeline Tests
Validates status inspection, dynamic availability flags, artifact downloads
(local FileResponse and S3 307 RedirectResponse), 404/409/500 error cases,
and RBAC permission enforcement (REPORT_READ & REPORT_DOWNLOAD).
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from app.api.v1.endpoints.reports import (
    download_report as api_download_report,
    get_report_status as api_get_report_status,
)
from app.auth.permissions import Permission, require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import AuthProvider, UserRole
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportPathsResponse
from app.services.reports.storage import DownloadReference


@pytest.fixture
def test_user():
    return User(
        id=uuid.uuid4(),
        email="auditor@nova.example",
        role=UserRole.AUDITOR,
        is_active=True,
        auth_provider=AuthProvider.LOCAL,
    )


# ── 1. Report Status Endpoint Tests ───────────────────────────────────────────


class TestReportStatusEndpoint:
    @pytest.mark.asyncio
    async def test_get_report_status_dynamic_availability(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()

        sample_reports = [
            Report(scan_job_id=scan_job_id, report_type="pdf", status="completed"),
            Report(scan_job_id=scan_job_id, report_type="pdf_technical", status="completed"),
            Report(scan_job_id=scan_job_id, report_type="compliance_report", status="completed"),
            Report(scan_job_id=scan_job_id, report_type="csv", status="completed"),
            Report(scan_job_id=scan_job_id, report_type="sarif", status="completed"),
            Report(scan_job_id=scan_job_id, report_type="sbom", status="generating"),
        ]
        mock_reports_repo.list_by_scan_job.return_value = sample_reports

        res = await api_get_report_status(
            report_id=scan_job_id,
            reports=mock_reports_repo,
            _current_user=test_user,
        )

        assert isinstance(res, ReportPathsResponse)
        assert res.scan_job_id == scan_job_id
        assert res.pdf_available is True
        assert res.pdf_technical_available is True
        assert res.compliance_report_available is True
        assert res.csv_available is True
        assert res.sarif_available is True
        # In progress ("generating") should not mark it as available
        assert res.sbom_available is False
        assert len(res.reports) == 6

    @pytest.mark.asyncio
    async def test_get_report_status_empty(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_reports_repo.list_by_scan_job.return_value = []

        res = await api_get_report_status(
            report_id=scan_job_id,
            reports=mock_reports_repo,
            _current_user=test_user,
        )

        assert res.pdf_available is False
        assert res.pdf_technical_available is False
        assert res.compliance_report_available is False
        assert res.csv_available is False
        assert len(res.reports) == 0


# ── 2. Report Download Endpoint Tests ─────────────────────────────────────────


class TestReportDownloadEndpoint:
    @pytest.mark.asyncio
    async def test_download_report_local_success(self, test_user):
        scan_job_id = uuid.uuid4()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(b"%PDF-1.4 test report content")
            tmp_path = Path(tmp_file.name)

        try:
            mock_reports_repo = AsyncMock()
            mock_report = Report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                status="completed",
                file_path=str(tmp_path),
                storage_backend="local",
            )
            mock_reports_repo.get_by_type.return_value = mock_report

            res = await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

            assert isinstance(res, FileResponse)
            assert res.path == str(tmp_path)
            assert res.media_type == "application/pdf"
            assert f"nova-pdf-{scan_job_id}.pdf" in res.filename
        finally:
            tmp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_download_report_s3_redirect(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_report = Report(
            scan_job_id=scan_job_id,
            report_type="pdf",
            status="completed",
            storage_backend="s3",
            storage_key="reports/2026/08/scan-pdf.pdf",
        )
        mock_reports_repo.get_by_type.return_value = mock_report

        mock_storage = MagicMock()
        mock_storage.get_download_reference.return_value = DownloadReference(
            presigned_url="https://s3.example.com/reports/presigned-pdf?token=abc"
        )

        with patch("app.api.v1.endpoints.reports.get_storage", return_value=mock_storage):
            res = await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

            assert isinstance(res, RedirectResponse)
            assert res.status_code == 307
            assert res.headers["location"] == "https://s3.example.com/reports/presigned-pdf?token=abc"

    @pytest.mark.asyncio
    async def test_download_report_not_found(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_reports_repo.get_by_type.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

        assert f"Report 'pdf' for scan job '{scan_job_id}' not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_download_report_in_progress_conflict(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_report = Report(
            scan_job_id=scan_job_id,
            report_type="pdf",
            status="generating",
        )
        mock_reports_repo.get_by_type.return_value = mock_report

        with pytest.raises(ConflictError) as exc_info:
            await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

        assert "still in progress" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_download_report_failed_500(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_report = Report(
            scan_job_id=scan_job_id,
            report_type="pdf",
            status="failed",
            error_message="ReportLab generation OOM",
        )
        mock_reports_repo.get_by_type.return_value = mock_report

        with pytest.raises(HTTPException) as exc_info:
            await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

        assert exc_info.value.status_code == 500
        assert "Report generation failed: ReportLab generation OOM" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_download_report_file_missing_on_disk(self, test_user):
        scan_job_id = uuid.uuid4()
        mock_reports_repo = AsyncMock()
        mock_report = Report(
            scan_job_id=scan_job_id,
            report_type="pdf",
            status="completed",
            file_path="/tmp/non_existent_report_file_12345.pdf",
            storage_backend="local",
        )
        mock_reports_repo.get_by_type.return_value = mock_report

        with pytest.raises(NotFoundError) as exc_info:
            await api_download_report(
                scan_job_id=scan_job_id,
                report_type="pdf",
                reports=mock_reports_repo,
                _current_user=test_user,
            )

        assert "not found on storage" in str(exc_info.value.message)


# ── 3. RBAC Permissions Tests ─────────────────────────────────────────────────


class TestReportsPermissions:
    @pytest.mark.asyncio
    async def test_report_permissions_gating(self):
        read_dep = require_permission(Permission.REPORT_READ)
        download_dep = require_permission(Permission.REPORT_DOWNLOAD)

        # All 5 platform roles have REPORT_READ and REPORT_DOWNLOAD
        all_roles = [
            UserRole.ADMIN,
            UserRole.SECURITY_ENGINEER,
            UserRole.DEVELOPER,
            UserRole.AUDITOR,
            UserRole.READ_ONLY,
        ]

        for role in all_roles:
            user = User(
                id=uuid.uuid4(),
                email=f"{role.value}@nova.example",
                role=role,
                is_active=True,
                auth_provider=AuthProvider.LOCAL,
            )
            assert await read_dep(current_user=user) == user
            assert await download_dep(current_user=user) == user
