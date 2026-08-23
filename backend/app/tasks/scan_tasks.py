"""
NOVA — Celery Scan Intake & Fan-Out Task
Intakes scan requests, resolves and extracts repository artifacts, marks jobs running,
initializes fine-grained Redis worker status, and fans out 9 parallel scanner tasks
via a Celery chord with aggregator callback.
"""

import asyncio
import os
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

import structlog
from celery import chord
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.github.client import GitHubRepoProvider
from app.models.enums import RepoProviderType, ScanJobStatus
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.orchestrator import scan_status
from app.repositories.scan_job_repository import ScanJobRepository
from app.tasks.aggregator_tasks import aggregate_scan_results_task
from app.tasks.scanner_tasks import run_scanner_task
from app.workers.celery_app import celery_app, queue_for_priority

logger = structlog.get_logger(__name__)

SCANNERS: List[str] = [
    "semgrep",
    "ast-grep",
    "joern",
    "pip-audit",
    "osv",
    "nvd",
    "secrets",
    "docker",
    "yaml",
]


def dispatch_scan_job(job: ScanJob) -> None:
    """Entrypoint helper to queue scan intake with priority-based worker routing."""
    priority_str = job.priority.value if hasattr(job.priority, "value") else str(job.priority)
    queue = queue_for_priority(priority_str)
    prepare_scan_task.apply_async(args=[str(job.id)], queue=queue)


@celery_app.task(
    bind=True,
    name="NOVA.prepare_scan",
    max_retries=1,
    default_retry_delay=15,
    acks_late=True,
)
def prepare_scan_task(self, scan_job_id: str) -> None:
    """Worker task to resolve scan artifact and fan-out parallel scanner chord."""
    asyncio.run(_prepare_and_fan_out(scan_job_id=scan_job_id))


async def _resolve_artifact(job: ScanJob, db) -> Path:
    """Resolve, download, or extract the repository artifact to a target directory on disk."""
    temp_dir = Path(tempfile.mkdtemp(prefix=f"nova-scan-{job.id}-"))

    # 1. Existing artifact on disk
    if job.artifact_path and os.path.exists(job.artifact_path):
        source_path = Path(job.artifact_path)
        if source_path.is_dir():
            return source_path
        if source_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(temp_dir)
            return temp_dir
        if source_path.name.endswith((".tar.gz", ".tgz")):
            with tarfile.open(source_path, "r:gz") as tf:
                tf.extractall(temp_dir)
            return temp_dir

    # 2. Remote repository URL download
    if job.repository_id:
        repo_res = await db.execute(select(Repository).where(Repository.id == job.repository_id))
        repo = repo_res.scalar_one_or_none()
        if repo and repo.url:
            provider = GitHubRepoProvider()
            archive_file = await provider.download_archive(
                repo_url=repo.url, ref=job.ref or repo.default_branch, dest_dir=temp_dir
            )
            extract_dir = temp_dir / "src"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_file, "r:gz") as tf:
                tf.extractall(extract_dir)
            return extract_dir

    # Fallback to empty directory
    return temp_dir


async def _prepare_and_fan_out(scan_job_id: str) -> None:
    job_uuid = uuid.UUID(scan_job_id)

    async with AsyncSessionLocal() as db:
        scan_jobs = ScanJobRepository(db)
        job = await scan_jobs.get(job_uuid, fresh=True)
        if job is None:
            logger.error("scan_tasks.job_not_found", scan_job_id=scan_job_id)
            return

        if scan_status.is_cancelled(scan_job_id) or job.status == ScanJobStatus.CANCELLED:
            logger.info("scan_tasks.job_already_cancelled", scan_job_id=scan_job_id)
            await scan_jobs.mark_cancelled(job)
            scan_status.clear(scan_job_id)
            return

        try:
            # 1. Mark ScanJob RUNNING
            await scan_jobs.mark_running(job)

            # 2. Resolve artifact directory
            artifact_dir = await _resolve_artifact(job, db)
            logger.info(
                "scan_tasks.artifact_resolved",
                scan_job_id=scan_job_id,
                artifact_dir=str(artifact_dir),
            )

            # 3. Initialize per-scanner Redis worker status
            for scanner in SCANNERS:
                scan_status.set_status(scan_job_id, scanner, "queued")

            # 4. Construct Celery Chord: Header (9 Scanners) -> Callback (Aggregator)
            header = [
                run_scanner_task.s(scanner, scan_job_id, str(artifact_dir))
                for scanner in SCANNERS
            ]
            callback = aggregate_scan_results_task.s(scan_job_id, str(artifact_dir))

            chord_task = chord(header)(callback)
            logger.info(
                "scan_tasks.chord_dispatched",
                scan_job_id=scan_job_id,
                chord_id=str(chord_task.id),
                scanners=SCANNERS,
            )

        except Exception as exc:
            logger.error("scan_tasks.prepare_failed", scan_job_id=scan_job_id, error=str(exc))
            if scan_jobs.should_retry(job):
                await scan_jobs.prepare_retry(job)
            else:
                await scan_jobs.mark_failed(job, error_message=f"Scan preparation failed: {exc}")
            await db.commit()
            scan_status.clear(scan_job_id)
            raise
