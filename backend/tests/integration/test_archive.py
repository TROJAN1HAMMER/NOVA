"""
NOVA — Integration Test: Archive Sweep
The last step of the pipeline: real Postgres rows, a real local report
file on disk, and the real `_archive_old_scans()` sweep — verifies it
only touches terminal jobs past the retention cutoff, and that it
actually reclaims disk space rather than just flipping a flag.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.models.enums import ScanJobPriority, ScanJobStatus
from app.models.report import Report
from app.models.scan_job import ScanJob
from app.tasks.archive_tasks import _archive_old_scans

pytestmark = pytest.mark.integration


async def test_archive_sweep_reclaims_old_terminal_jobs_only(db_session, test_repository, override_settings):
    now = datetime.now(timezone.utc)
    old_finished = now - timedelta(days=100)
    recent_finished = now - timedelta(days=10)

    from app.config import get_settings

    settings = get_settings()
    report_dir = Path(settings.reports_dir) / "archive_integration_test"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"{uuid.uuid4().hex}.pdf"
    report_file.write_bytes(b"%PDF-1.4 fake report content")

    old_job = ScanJob(
        repository_id=test_repository.id,
        status=ScanJobStatus.COMPLETED,
        priority=ScanJobPriority.NORMAL,
        finished_at=old_finished,
    )
    recent_job = ScanJob(
        repository_id=test_repository.id,
        status=ScanJobStatus.COMPLETED,
        priority=ScanJobPriority.NORMAL,
        finished_at=recent_finished,
    )
    running_job = ScanJob(repository_id=test_repository.id, status=ScanJobStatus.RUNNING)
    db_session.add_all([old_job, recent_job, running_job])
    await db_session.flush()

    old_report = Report(
        scan_job_id=old_job.id,
        report_type="pdf",
        status="completed",
        file_path=str(report_file),
        storage_backend="local",
    )
    db_session.add(old_report)
    await db_session.commit()

    old_job_id, recent_job_id, running_job_id = old_job.id, recent_job.id, running_job.id

    with override_settings(archive_after_days=90):
        await _archive_old_scans()

    # Targeted, not `expire_all()`: the archive sweep committed these
    # three via its own separate session, so this session's identity map
    # still holds the pre-archive versions — but expiring `test_repository`
    # too would break its own fixture teardown (plain `.id` access on an
    # expired AsyncSession-loaded object isn't valid outside an awaited
    # refresh — see test_pipeline_aggregation.py for the same lesson).
    db_session.expire(old_job)
    db_session.expire(recent_job)
    db_session.expire(running_job)

    refreshed_old = await db_session.get(ScanJob, old_job_id)
    refreshed_recent = await db_session.get(ScanJob, recent_job_id)
    refreshed_running = await db_session.get(ScanJob, running_job_id)

    assert refreshed_old.archived_at is not None
    assert refreshed_recent.archived_at is None
    assert refreshed_running.archived_at is None
    assert not report_file.exists(), "the archived job's local report file should have been deleted"

    await db_session.execute(delete(Report).where(Report.scan_job_id == old_job_id))
    report_dir.rmdir()
