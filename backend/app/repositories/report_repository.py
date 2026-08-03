"""
NOVA — Report Repository
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, *, scan_job_id: uuid.UUID, report_type: str, file_path: str) -> Report:
        """Back-compat convenience: a report whose file already exists, recorded as completed in one step."""
        report = Report(
            scan_job_id=scan_job_id,
            report_type=report_type,
            file_path=file_path,
            status="completed",
            storage_backend="local",
        )
        self.db.add(report)
        await self.db.flush()
        return report

    async def get_by_id(self, report_id: uuid.UUID) -> Optional[Report]:
        return await self.db.get(Report, report_id)

    async def list_by_scan_job(self, scan_job_id: uuid.UUID) -> list[Report]:
        result = await self.db.execute(select(Report).where(Report.scan_job_id == scan_job_id))
        return list(result.scalars().all())

    async def get_by_type(self, scan_job_id: uuid.UUID, report_type: str) -> Optional[Report]:
        result = await self.db.execute(
            select(Report).where(Report.scan_job_id == scan_job_id, Report.report_type == report_type)
        )
        return result.scalar_one_or_none()

    async def create_pending(self, *, scan_job_id: uuid.UUID, report_type: str) -> Report:
        """
        Called before any file exists — this is what makes generation
        observably asynchronous (`GET /reports/{scan_job_id}` sees a
        "pending" row immediately, not just once a file shows up).

        Get-or-create rather than a plain insert: a retried generation
        pass reuses the same row (reset to pending) instead of violating
        the (scan_job_id, report_type) unique constraint or accumulating
        duplicate rows the way a second insert would have before it.
        """
        existing = await self.get_by_type(scan_job_id, report_type)
        if existing is not None:
            existing.status = "pending"
            existing.error_message = None
            await self.db.flush()
            return existing

        report = Report(scan_job_id=scan_job_id, report_type=report_type, status="pending")
        self.db.add(report)
        await self.db.flush()
        return report

    async def mark_generating(self, report_id: uuid.UUID) -> None:
        report = await self.get_by_id(report_id)
        if report is not None:
            report.status = "generating"
            await self.db.flush()

    async def mark_completed(
        self,
        report_id: uuid.UUID,
        *,
        file_path: str,
        storage_backend: str = "local",
        storage_key: Optional[str] = None,
    ) -> None:
        report = await self.get_by_id(report_id)
        if report is not None:
            report.status = "completed"
            report.file_path = file_path
            report.storage_backend = storage_backend
            report.storage_key = storage_key
            report.error_message = None
            await self.db.flush()

    async def mark_failed(self, report_id: uuid.UUID, *, error_message: str) -> None:
        report = await self.get_by_id(report_id)
        if report is not None:
            report.status = "failed"
            report.error_message = error_message[:4000]
            await self.db.flush()
