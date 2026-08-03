"""
NOVA — Archive Task
Celery Beat runs `archive_old_scans` nightly (see `app/workers/celery_app.py`'s
`beat_schedule`) — the final step of the pipeline: GitHub webhook → scan
job → queue → workers → aggregation → risk → compliance → AI explanation
→ reports → dashboard → notifications → **archive**.

Archiving here means reclaiming disk/object-storage space, not deleting
history: a job's `ScanJob`/`Finding`/`ScanResult` rows stay in Postgres
forever (that's the queryable data behind the Risk/Executive dashboards),
only the heavier rendered report files (PDF/SARIF/SBOM/...) get purged
once a job has been terminal for longer than `settings.archive_after_days`.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.repositories.report_repository import ReportRepository
from app.repositories.scan_job_repository import ScanJobRepository
from app.services.reports.storage import get_storage
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(name="NOVA.archive_old_scans")
def archive_old_scans_task() -> None:
    asyncio.run(_archive_old_scans())


async def _archive_old_scans() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.archive_after_days)
    storage = get_storage()
    archived_count = 0
    reports_reclaimed = 0

    async with AsyncSessionLocal() as db:
        scan_jobs = ScanJobRepository(db)
        reports_repo = ReportRepository(db)

        for job in await scan_jobs.list_archivable(older_than=cutoff):
            reports = await reports_repo.list_by_scan_job(job.id)
            for report in reports:
                if report.status != "completed":
                    continue
                storage_ref = report.storage_key if report.storage_backend == "s3" else report.file_path
                if not storage_ref:
                    continue
                try:
                    storage.delete_report(storage_ref)
                    reports_reclaimed += 1
                except Exception as exc:
                    # Reclaiming disk space is best-effort housekeeping,
                    # not part of scan correctness — one failed delete
                    # (e.g. a transient S3 error) must never block this
                    # job (or the rest of the batch) from being marked
                    # archived; the next nightly run will retry deletion
                    # for any report row still pointing at a live file.
                    logger.warning(
                        "archive.report_delete_failed",
                        scan_job_id=str(job.id),
                        report_type=report.report_type,
                        error=str(exc),
                    )

            await scan_jobs.mark_archived(job)
            await db.commit()
            archived_count += 1

    logger.info(
        "archive.sweep_completed",
        archived_count=archived_count,
        reports_reclaimed=reports_reclaimed,
        cutoff=cutoff.isoformat(),
    )
