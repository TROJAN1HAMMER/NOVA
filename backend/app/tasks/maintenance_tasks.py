"""
NOVA — Maintenance Tasks
Celery Beat schedules `sweep_stalled_jobs` every 60s (see
`app/workers/celery_app.py`'s `beat_schedule`). It exists specifically for
the failure mode nothing else in this system catches: a worker process
that's killed outright (OOM, node loss, SIGKILL) leaves its ScanJob stuck
at RUNNING forever — no exception is ever raised, so neither a scanner
task's own except blocks nor Celery's soft-time-limit handling ever run.

Heartbeat source: each of the 9 scanner tasks (app/tasks/scanner_tasks.py)
touches its Redis status entry (app/orchestrator/scan_status.py) when it
starts and when it finishes — `ScanJob.last_heartbeat_at` in Postgres is
only set once, at `mark_running`, and never refreshed in this fan-out
design (unlike the old sequential pipeline, which updated it at every
stage). So the freshest `updated_at` across all of a job's Redis
worker-status entries is the real liveness signal here, with
`job.started_at` as the fallback for a job whose prepare step hasn't
finished (no scanner tasks dispatched yet, so no Redis entries exist).
"""

import asyncio
from datetime import datetime, timezone

import structlog

from app.db.session import AsyncSessionLocal
from app.orchestrator import scan_status
from app.repositories.scan_job_repository import ScanJobRepository
from app.services.notifications.notification_service import get_notification_service
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Extra buffer added on top of each job's own `timeout_seconds` before
# treating a stale heartbeat as a crash rather than a slow-but-alive job —
# gives Celery's own per-scanner soft/hard time limits (set in
# scan_tasks.py::_dispatch_chord) a chance to fire and handle it first.
STALE_GRACE_SECONDS = 120


@celery_app.task(name="NOVA.sweep_stalled_jobs")
def sweep_stalled_jobs() -> None:
    asyncio.run(_sweep_stalled_jobs())


def _latest_heartbeat(scan_job_id: str, fallback: datetime | None) -> datetime | None:
    worker_status = scan_status.get_worker_status(scan_job_id)
    if not worker_status:
        return fallback
    latest_epoch = max(entry["updated_at"] for entry in worker_status.values())
    return datetime.fromtimestamp(latest_epoch, tz=timezone.utc)


async def _sweep_stalled_jobs() -> None:
    from app.tasks.scan_tasks import dispatch_scan_job

    async with AsyncSessionLocal() as db:
        scan_jobs = ScanJobRepository(db)
        now = datetime.now(timezone.utc)

        for job in await scan_jobs.list_running():
            reference_time = _latest_heartbeat(str(job.id), job.started_at)
            if reference_time is None:
                continue  # Marked running but prepare hasn't even set started_at yet — too new to judge.

            age_seconds = (now - reference_time).total_seconds()
            if age_seconds <= job.timeout_seconds + STALE_GRACE_SECONDS:
                continue  # Still within its own budget — not stalled.

            logger.warning(
                "maintenance.stalled_job_detected",
                scan_job_id=str(job.id),
                age_seconds=round(age_seconds, 1),
                timeout_seconds=job.timeout_seconds,
            )
            await get_notification_service().notify_worker_stalled(
                scan_job_id=str(job.id), age_seconds=age_seconds
            )

            if scan_jobs.should_retry(job):
                await scan_jobs.prepare_retry(job)
                await db.commit()
                scan_status.clear(str(job.id))
                # The prepare step resolves the artifact itself — an
                # existing path on disk for uploads, a fresh download via
                # the repository's provider otherwise — so no path needs
                # to be passed back in here.
                dispatch_scan_job(job)
            else:
                await scan_jobs.mark_failed(
                    job, error_message="Worker heartbeat timed out — presumed crashed"
                )
                await db.commit()
                scan_status.clear(str(job.id))
