"""
NOVA — ScanJob Repository
Handles asynchronous database access, atomic lifecycle transitions,
and real-time WebSocket pub/sub broadcasting for security scan jobs.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ScanJobPriority, ScanJobStatus
from app.models.scan_job import ScanJob
from app.orchestrator import scan_status


class ScanJobRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_queued(
        self,
        *,
        repository_id: uuid.UUID,
        priority: ScanJobPriority = ScanJobPriority.NORMAL,
        owner_id: Optional[uuid.UUID] = None,
        ref: Optional[str] = None,
        artifact_path: Optional[str] = None,
        timeout_seconds: int = 900,
        max_retries: int = 2,
    ) -> ScanJob:
        """Create and queue a new ScanJob."""
        job = ScanJob(
            repository_id=repository_id,
            priority=priority,
            owner_id=owner_id,
            ref=ref,
            artifact_path=artifact_path,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            status=ScanJobStatus.QUEUED,
            queued_at=datetime.now(timezone.utc),
            progress_percent=0,
            current_stage="queued",
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get(self, scan_job_id: uuid.UUID, *, fresh: bool = False) -> Optional[ScanJob]:
        """Fetch a ScanJob by UUID.

        If `fresh=True`, forces SQLAlchemy to populate from the database directly,
        bypassing cached identity-map objects on long-lived sessions.
        """
        if fresh:
            result = await self.db.execute(
                select(ScanJob)
                .where(ScanJob.id == scan_job_id)
                .execution_options(populate_existing=True)
            )
            return result.scalar_one_or_none()
        return await self.db.get(ScanJob, scan_job_id)

    async def _commit_and_publish(self, job: ScanJob, event_type: str = "status_change") -> None:
        """Commit the session transaction BEFORE publishing the update to Redis pub/sub.

        This guarantees that any cross-process or WebSocket subscriber querying
        Postgres immediately upon receiving the Redis event observes the committed data.
        """
        await self.db.commit()
        scan_status.publish_update(
            str(job.id),
            {
                "type": "job_status",
                "event": event_type,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "current_stage": job.current_stage,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def mark_running(self, job: ScanJob) -> None:
        """Transition job to RUNNING state."""
        now = datetime.now(timezone.utc)
        job.status = ScanJobStatus.RUNNING
        if job.started_at is None:
            job.started_at = now
        job.last_heartbeat_at = now
        job.progress_percent = 0
        job.current_stage = "scanning"
        await self._commit_and_publish(job, "running")

    async def update_progress(self, job: ScanJob, percent: int, stage: Optional[str] = None) -> None:
        """Update job progress percentage and current stage."""
        job.progress_percent = percent
        if stage is not None:
            job.current_stage = stage
        job.last_heartbeat_at = datetime.now(timezone.utc)
        await self._commit_and_publish(job, "progress")

    async def mark_completed(self, job: ScanJob) -> None:
        """Transition job to COMPLETED state."""
        job.status = ScanJobStatus.COMPLETED
        job.progress_percent = 100
        job.finished_at = datetime.now(timezone.utc)
        job.current_stage = "completed"
        await self._commit_and_publish(job, "completed")

    async def mark_failed(self, job: ScanJob, *, error_message: str) -> None:
        """Transition job to FAILED state."""
        job.status = ScanJobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
        job.error_message = error_message
        job.current_stage = "failed"
        await self._commit_and_publish(job, "failed")

    async def mark_cancelled(self, job: ScanJob) -> None:
        """Transition job to CANCELLED state."""
        job.status = ScanJobStatus.CANCELLED
        job.finished_at = datetime.now(timezone.utc)
        job.current_stage = "cancelled"
        await self._commit_and_publish(job, "cancelled")

    async def list_running(self) -> List[ScanJob]:
        """List all jobs currently in RUNNING state."""
        result = await self.db.execute(select(ScanJob).where(ScanJob.status == ScanJobStatus.RUNNING))
        return list(result.scalars().all())

    async def list_archivable(self, *, older_than: datetime) -> List[ScanJob]:
        """List terminal jobs older than the given cutoff that have not been archived."""
        result = await self.db.execute(
            select(ScanJob).where(
                ScanJob.status.in_([ScanJobStatus.COMPLETED, ScanJobStatus.FAILED, ScanJobStatus.CANCELLED]),
                ScanJob.finished_at <= older_than,
                ScanJob.archived_at.is_(None),
            )
        )
        return list(result.scalars().all())

    def should_retry(self, job: ScanJob) -> bool:
        """Check if job has remaining retries."""
        return job.retry_count < job.max_retries

    async def prepare_retry(self, job: ScanJob) -> None:
        """Reset job state for retry execution."""
        job.retry_count += 1
        job.status = ScanJobStatus.QUEUED
        job.progress_percent = 0
        job.current_stage = "retry_queued"
        job.started_at = None
        job.finished_at = None
        job.error_message = None
        await self.db.flush()

    async def list_by_repository(
        self, repository_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> List[ScanJob]:
        """List scan jobs for a repository ordered by creation time descending."""
        result = await self.db.execute(
            select(ScanJob)
            .where(ScanJob.repository_id == repository_id)
            .order_by(ScanJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
