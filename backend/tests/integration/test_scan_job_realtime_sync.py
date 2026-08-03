"""
NOVA — Integration Test: ScanJob real-time status sync

Regression coverage for the "frontend never updates when a scan completes"
investigation. Two independent defects were found in
`ScanJobRepository`/`scan_progress_ws` and are covered here directly against
a real Postgres connection (no mocks) — see the docstrings on
`ScanJobRepository._commit_and_publish` and `ScanJobRepository.get` for the
full root-cause explanation:

1. `mark_running`/`mark_completed`/etc. used to `flush()` then publish to
   Redis pub/sub, leaving the actual `commit()` to the caller. A WebSocket
   subscriber living in a different process/DB connection could receive
   that event and re-query Postgres before the transaction was durably
   committed. Fixed by committing *before* publishing.

2. `scan_progress_ws`'s post-completion "final snapshot" re-fetches the job
   with `ScanJobRepository.get()` on the *same* long-lived session that
   already loaded it once when the socket connected. `AsyncSession.get()`
   returns the cached identity-map object in that case rather than
   re-querying — so the "fresh" snapshot was silently stale. Fixed by a
   `fresh=True` flag that passes `populate_existing=True` through to force
   a real re-read.
"""

import pytest
import pytest_asyncio

from app.models.enums import ScanJobStatus
from app.repositories.scan_job_repository import ScanJobRepository

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def scan_job(db_session, test_repository):
    scan_jobs = ScanJobRepository(db_session)
    job = await scan_jobs.create_queued(repository_id=test_repository.id)
    await db_session.commit()
    yield job


class TestStatusLifecycle:
    async def test_queued_to_running_to_completed(self, db_session, scan_job):
        """The status enum actually walks queued -> running -> completed,
        with progress/stage fields updated at each step — the same
        transitions the frontend polls/subscribes for."""
        scan_jobs = ScanJobRepository(db_session)

        assert scan_job.status == ScanJobStatus.QUEUED

        await scan_jobs.mark_running(scan_job)
        assert scan_job.status == ScanJobStatus.RUNNING
        assert scan_job.progress_percent == 0

        await scan_jobs.update_progress(scan_job, percent=42, stage="scanning")
        assert scan_job.progress_percent == 42
        assert scan_job.current_stage == "scanning"

        await scan_jobs.mark_completed(scan_job)
        assert scan_job.status == ScanJobStatus.COMPLETED
        assert scan_job.progress_percent == 100
        assert scan_job.finished_at is not None


class TestCrossSessionVisibility:
    """
    Simulates the exact shape of the bug: one long-lived session (standing
    in for the WebSocket handler's request-scoped session) observes a job,
    then a *different* session (standing in for the Celery worker) commits
    a status transition, and the first session must be able to see it.
    """

    async def test_commit_happens_before_publish_is_visible_cross_session(self, db_session, scan_job):
        from app.db.session import AsyncSessionLocal

        scan_jobs_worker = ScanJobRepository(db_session)
        await scan_jobs_worker.mark_completed(scan_job)

        # A brand-new session (fresh identity map) must see the committed
        # row immediately — proves _commit_and_publish actually committed
        # rather than merely flushing.
        async with AsyncSessionLocal() as other_session:
            other_repo = ScanJobRepository(other_session)
            reread = await other_repo.get(scan_job.id)
            assert reread is not None
            assert reread.status == ScanJobStatus.COMPLETED
            assert reread.progress_percent == 100

    async def test_stale_get_without_fresh_flag_returns_cached_object(self, db_session, scan_job):
        """
        Documents the identity-map trap `fresh=True` exists to route
        around: re-`get()`-ing an already-loaded object on the *same*
        session, after another session commits a change, returns the
        stale cached instance — this is the bug that made the WebSocket's
        "final snapshot" show pre-completion data.
        """
        from app.db.session import AsyncSessionLocal

        watcher_session = AsyncSessionLocal()
        try:
            watcher_repo = ScanJobRepository(watcher_session)
            # Load it once on the "WS" session — mirrors scan_progress_ws
            # loading `job` when the socket first connects.
            watched_job = await watcher_repo.get(scan_job.id)
            assert watched_job is not None
            assert watched_job.status == ScanJobStatus.QUEUED

            # A different session (the worker) completes the job.
            worker_repo = ScanJobRepository(db_session)
            await worker_repo.mark_completed(scan_job)

            # Same "WS" session, no fresh=True: identity map wins, stale data.
            stale_reread = await watcher_repo.get(scan_job.id)
            assert stale_reread is watched_job
            assert stale_reread.status == ScanJobStatus.QUEUED

            # fresh=True forces populate_existing — now it's actually fresh.
            fresh_reread = await watcher_repo.get(scan_job.id, fresh=True)
            assert fresh_reread.status == ScanJobStatus.COMPLETED
            assert fresh_reread.progress_percent == 100
        finally:
            await watcher_session.close()


class TestConcurrentScans:
    async def test_multiple_simultaneous_scans_update_independently(self, db_session, test_repository):
        """Two scan jobs for the same repository must not cross-contaminate
        each other's status/progress when updated interleaved — guards
        against any shared-state assumption creeping into the repository
        (e.g. accidentally updating "the last loaded job")."""
        scan_jobs = ScanJobRepository(db_session)

        job_a = await scan_jobs.create_queued(repository_id=test_repository.id)
        job_b = await scan_jobs.create_queued(repository_id=test_repository.id)
        await db_session.commit()

        await scan_jobs.mark_running(job_a)
        await scan_jobs.mark_running(job_b)
        await scan_jobs.update_progress(job_a, percent=10, stage="scanning")
        await scan_jobs.update_progress(job_b, percent=90, stage="aggregating")
        await scan_jobs.mark_completed(job_a)

        assert job_a.status == ScanJobStatus.COMPLETED
        assert job_a.progress_percent == 100
        assert job_b.status == ScanJobStatus.RUNNING
        assert job_b.progress_percent == 90

        reread_a = await scan_jobs.get(job_a.id, fresh=True)
        reread_b = await scan_jobs.get(job_b.id, fresh=True)
        assert reread_a.status == ScanJobStatus.COMPLETED
        assert reread_b.status == ScanJobStatus.RUNNING
