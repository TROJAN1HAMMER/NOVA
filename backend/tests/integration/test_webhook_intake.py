"""
NOVA — Integration Test: GitHub Webhook Intake
Exercises `POST /api/v1/webhooks/github` against the real app (ASGI
transport, no mocks) and the real Postgres — signature verification,
event-type routing, and the get-or-create Repository/ScanJob path shared
with `POST /scan/repository` (app/services/scan_intake.py). The dispatched
scan job is cancelled during cleanup rather than left to run against a
nonexistent GitHub repo against the real worker pool this environment
runs (see the cleanup block below).
"""

import hashlib
import hmac
import json
import uuid

import httpx
import pytest
from sqlalchemy import delete, select

from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.orchestrator import scan_status
from app.repositories.scan_job_repository import ScanJobRepository

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "test-webhook-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def github_webhook_configured(override_settings):
    with override_settings(github_webhook_secret=WEBHOOK_SECRET, github_webhook_scan_all_branches=True) as settings:
        yield settings


@pytest.fixture
async def client():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _push_payload(full_name: str, clone_url: str, deleted: bool = False, ref: str = "refs/heads/main") -> bytes:
    return json.dumps(
        {
            "ref": ref,
            "deleted": deleted,
            "repository": {
                "name": full_name.split("/")[1],
                "full_name": full_name,
                "clone_url": clone_url,
                "html_url": f"https://github.com/{full_name}",
                "default_branch": "main",
            },
        }
    ).encode("utf-8")


async def test_missing_signature_rejected(client, github_webhook_configured):
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=_push_payload("acme/x", "https://github.com/acme/x.git"),
        headers={"X-GitHub-Event": "push"},
    )
    assert resp.status_code == 401


async def test_invalid_signature_rejected(client, github_webhook_configured):
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=_push_payload("acme/x", "https://github.com/acme/x.git"),
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert resp.status_code == 401


async def test_unconfigured_secret_returns_503(client, override_settings):
    with override_settings(github_webhook_secret=""):
        resp = await client.post(
            "/api/v1/webhooks/github",
            content=_push_payload("acme/x", "https://github.com/acme/x.git"),
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=anything"},
        )
    assert resp.status_code == 503


async def test_ping_event_acknowledged_without_scan(client, github_webhook_configured):
    body = json.dumps({"zen": "Speak like a human."}).encode("utf-8")
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ping_ok"


async def test_unhandled_event_type_ignored(client, github_webhook_configured):
    body = _push_payload("acme/x", "https://github.com/acme/x.git")
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


async def test_branch_deletion_ignored(client, github_webhook_configured):
    body = _push_payload("acme/x", "https://github.com/acme/x.git", deleted=True, ref="refs/heads/feature-x")
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


async def test_push_event_queues_scan_and_reuses_repository(client, github_webhook_configured, db_session):
    full_name = f"acme/webhook-test-{uuid.uuid4().hex[:8]}"
    clone_url = f"https://github.com/{full_name}.git"
    body = _push_payload(full_name, clone_url)

    resp1 = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp1.status_code == 200
    payload1 = resp1.json()
    assert payload1["status"] == "scan_queued"
    repository_id = payload1["repository_id"]
    first_job_id = payload1["scan_job_id"]

    repo = await db_session.get(Repository, uuid.UUID(repository_id))
    assert repo is not None and repo.url == clone_url
    job = await db_session.get(ScanJob, uuid.UUID(first_job_id))
    assert job is not None and job.ref == "main" and job.owner_id is None

    # A second push to the same repo must reuse the same Repository row.
    resp2 = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp2.status_code == 200
    payload2 = resp2.json()
    assert payload2["repository_id"] == repository_id
    assert payload2["scan_job_id"] != first_job_id

    # Cleanup: cancel first — these were dispatched to the real running
    # Celery worker pool, which will otherwise retry a nonexistent GitHub
    # repo a few times before giving up.
    scan_jobs = ScanJobRepository(db_session)
    result = await db_session.execute(select(ScanJob).where(ScanJob.repository_id == uuid.UUID(repository_id)))
    for job in result.scalars().all():
        scan_status.mark_cancelled(str(job.id))
        await scan_jobs.mark_cancelled(job)
    await db_session.commit()
    await db_session.execute(delete(ScanJob).where(ScanJob.repository_id == uuid.UUID(repository_id)))
    await db_session.execute(delete(Repository).where(Repository.id == uuid.UUID(repository_id)))
    await db_session.commit()
