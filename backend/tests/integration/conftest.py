"""
NOVA — Integration Test Fixtures
Unlike tests/test_brs_engine.py (pure functions, no I/O), everything under
tests/integration/ exercises real infrastructure: the same Postgres/Redis
instances a dev environment already runs against (DATABASE_URL/REDIS_URL
from the environment — see backend/.env), with Celery switched to eager
mode so task chains (chords, `.apply_async()` dispatches) execute
synchronously in-process instead of needing separate worker processes.

What's deliberately NOT mocked, because it doesn't need to be:
  - The AI engine (`generate_batch_insights`) — falls back to its
    built-in template insights with no provider configured, so it runs
    for real without needing an API key.
  - Report generation — pure local rendering (reportlab/jinja/csv), no
    external services, real files land in a temp reports_dir per test.
  - The notification service's severity-gating/dispatch logic — only the
    actual network transport is a local capture server, not a mock.

What IS out of scope here: the 9 real scanner tools (semgrep, joern,
docker, ...) themselves. Those aren't guaranteed to be installed in every
environment this test suite runs in, so scanner *results* are supplied as
realistic synthetic data (exactly the dict shape `scanner_tasks.py`'s
chord produces) rather than invoking the tools — see
test_pipeline_aggregation.py's docstring for the exact seam this cuts at.
"""

import uuid
from contextlib import contextmanager

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db_session():
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def celery_eager():
    """
    Runs Celery tasks synchronously, in-process, using the real Redis
    result backend (so chords — which need a real backend to track group
    completion — still work correctly, just without a separate worker
    process). Restored to its prior value afterward so this doesn't leak
    into other tests or, worse, a real worker process that happened to
    import the same settings object in-process.
    """
    from app.workers.celery_app import celery_app

    prior_eager = celery_app.conf.task_always_eager
    prior_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        yield celery_app
    finally:
        celery_app.conf.task_always_eager = prior_eager
        celery_app.conf.task_eager_propagates = prior_propagates


@contextmanager
def _override_settings(**overrides):
    from app.config import get_settings

    settings = get_settings()
    original = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        setattr(settings, key, value)
    try:
        yield settings
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


@pytest.fixture
def override_settings():
    """Usage: `with override_settings(notifications_enabled=True): ...`"""
    return _override_settings


@pytest.fixture
def webhook_capture_server():
    """
    A minimal local HTTP server that records every POST it receives —
    stands in for a real Slack/webhook receiver so the notification
    service's outbound HTTP call (HMAC signature and all) can be verified
    for real instead of mocked away.
    """
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            received.append({"body": json.loads(raw), "raw": raw, "headers": dict(self.headers)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield {"url": f"http://127.0.0.1:{port}/hook", "received": received}
    finally:
        server.shutdown()
        server.server_close()


@pytest_asyncio.fixture
async def test_repository(db_session):
    """A throwaway Repository row, deleted after the test regardless of outcome."""
    from app.models.enums import RepoProviderType
    from app.models.repository import Repository

    repo = Repository(name=f"integration-test-{uuid.uuid4().hex[:8]}", provider=RepoProviderType.UPLOAD)
    db_session.add(repo)
    await db_session.flush()
    await db_session.commit()

    yield repo

    from sqlalchemy import delete

    from app.models.scan_job import ScanJob

    await db_session.execute(delete(ScanJob).where(ScanJob.repository_id == repo.id))
    await db_session.execute(delete(Repository).where(Repository.id == repo.id))
    await db_session.commit()
