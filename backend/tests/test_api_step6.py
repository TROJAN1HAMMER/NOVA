"""
NOVA — Step 6 Unit & Endpoint API Tests
Validates scan intake service, scan endpoints, repository endpoints,
finding intelligence endpoints, risk endpoints, and GitHub webhook handling.
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_active_user
from app.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.enums import AuthProvider, RepoProviderType, ScanJobPriority, ScanJobStatus, UserRole
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.risk_config import BusinessModule, RiskFactorWeight
from app.models.scan_job import ScanJob
from app.models.user import User
from app.services.scan_intake import (
    resolve_repo_provider_and_name,
    submit_premade,
    submit_repository,
)

# ── Mock User Fixture ─────────────────────────────────────────────────────────

MOCK_USER_ID = uuid.uuid4()
MOCK_USER = User(
    id=MOCK_USER_ID,
    email="testuser@nova.local",
    full_name="Test User",
    role=UserRole.SECURITY_ENGINEER,
    auth_provider=AuthProvider.LOCAL,
    is_active=True,
)


@pytest.fixture
def mock_active_user():
    app.dependency_overrides[get_current_active_user] = lambda: MOCK_USER
    yield MOCK_USER
    app.dependency_overrides.pop(get_current_active_user, None)


# ── 1. Scan Intake Service Tests ──────────────────────────────────────────────


def test_resolve_repo_provider_and_name():
    provider, name = resolve_repo_provider_and_name("https://github.com/acme/payment-gateway.git")
    assert provider == RepoProviderType.GITHUB
    assert name == "acme/payment-gateway"

    provider, name = resolve_repo_provider_and_name("https://gitlab.com/banking/auth-service")
    assert provider == RepoProviderType.GITLAB
    assert name == "banking/auth-service"

    provider, name = resolve_repo_provider_and_name("https://bitbucket.org/corp/core-api.git")
    assert provider == RepoProviderType.BITBUCKET
    assert name == "corp/core-api"


@pytest.mark.asyncio
async def test_submit_repository_service(monkeypatch):
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_dispatch = MagicMock()
    monkeypatch.setattr("app.services.scan_intake.dispatch_scan_job", mock_dispatch)

    repo, job = await submit_repository(
        mock_db,
        repo_url="https://github.com/acme/test-service.git",
        ref="main",
        priority=ScanJobPriority.HIGH,
        owner_id=MOCK_USER_ID,
    )

    assert repo.name == "acme/test-service"
    assert repo.provider == RepoProviderType.GITHUB
    assert job.priority == ScanJobPriority.HIGH
    assert job.status == ScanJobStatus.QUEUED
    mock_dispatch.assert_called_once_with(job)


@pytest.mark.asyncio
async def test_submit_premade_service(monkeypatch):
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_dispatch = MagicMock()
    monkeypatch.setattr("app.services.scan_intake.dispatch_scan_job", mock_dispatch)

    repo, job = await submit_premade(
        mock_db,
        risk_level="very_low",
        priority=ScanJobPriority.NORMAL,
        owner_id=MOCK_USER_ID,
    )

    assert "benchmark" in repo.name
    assert job.artifact_path is not None
    assert job.status == ScanJobStatus.QUEUED
    mock_dispatch.assert_called_once_with(job)


# ── 2. Scan API Endpoints Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_submit_repository(mock_active_user, monkeypatch):
    mock_repo = Repository(
        id=uuid.uuid4(),
        name="acme/web-app",
        url="https://github.com/acme/web-app.git",
        provider=RepoProviderType.GITHUB,
        default_branch="main",
        owner_id=MOCK_USER_ID,
    )
    mock_job = ScanJob(
        id=uuid.uuid4(),
        repository_id=mock_repo.id,
        status=ScanJobStatus.QUEUED,
        priority=ScanJobPriority.NORMAL,
    )

    monkeypatch.setattr(
        "app.api.v1.endpoints.scan.submit_repository",
        AsyncMock(return_value=(mock_repo, mock_job)),
    )

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/scan/repository",
                json={"repo_url": "https://github.com/acme/web-app.git", "priority": "normal"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["scan_job_id"] == str(mock_job.id)
            assert data["repository_id"] == str(mock_repo.id)
            assert data["status"] == "queued"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_get_scan_status(mock_active_user, monkeypatch):
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    mock_job = ScanJob(
        id=job_id,
        repository_id=repo_id,
        status=ScanJobStatus.RUNNING,
        priority=ScanJobPriority.NORMAL,
        progress_percent=45,
        current_stage="scanning",
        retry_count=0,
        max_retries=2,
        timeout_seconds=900,
    )
    mock_repo = Repository(id=repo_id, name="acme/repo", url="https://github.com/acme/repo")

    mock_db = AsyncMock()
    mock_db.get.side_effect = lambda model, ident: mock_repo if model == Repository else mock_job

    mock_scan_jobs = AsyncMock()
    mock_scan_jobs.get.return_value = mock_job
    monkeypatch.setattr("app.api.v1.endpoints.scan.ScanJobRepository", lambda db: mock_scan_jobs)
    monkeypatch.setattr("app.orchestrator.scan_status.get_worker_status", lambda jid: {"semgrep": {"status": "running", "updated_at": 100.0}})

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/scan/{job_id}")
            assert res.status_code == 200
            data = res.json()
            assert data["scan_job_id"] == str(job_id)
            assert data["repository_name"] == "acme/repo"
            assert data["status"] == "running"
            assert "semgrep" in data["worker_status"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_cancel_scan_job(mock_active_user, monkeypatch):
    job_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    mock_job = ScanJob(
        id=job_id,
        repository_id=repo_id,
        status=ScanJobStatus.RUNNING,
        priority=ScanJobPriority.NORMAL,
        progress_percent=50,
        retry_count=0,
        max_retries=2,
        timeout_seconds=900,
    )
    mock_repo = Repository(id=repo_id, name="acme/repo", url="https://github.com/acme/repo")

    mock_db = AsyncMock()
    mock_db.get.side_effect = lambda model, ident: mock_repo if model == Repository else mock_job

    mock_scan_jobs = AsyncMock()
    mock_scan_jobs.get.return_value = mock_job

    async def _mock_mark_cancelled(j):
        j.status = ScanJobStatus.CANCELLED

    mock_scan_jobs.mark_cancelled.side_effect = _mock_mark_cancelled

    monkeypatch.setattr("app.api.v1.endpoints.scan.ScanJobRepository", lambda db: mock_scan_jobs)
    monkeypatch.setattr("app.orchestrator.scan_status.mark_cancelled", lambda jid: None)
    monkeypatch.setattr("app.orchestrator.scan_status.get_all_task_ids", lambda jid: set())
    monkeypatch.setattr("app.orchestrator.scan_status.get_worker_status", lambda jid: {})

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/scan/{job_id}/cancel")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "cancelled"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_get_scan_findings(mock_active_user, monkeypatch):
    job_id = uuid.uuid4()
    mock_job = ScanJob(id=job_id, repository_id=uuid.uuid4(), status=ScanJobStatus.COMPLETED)
    mock_finding = Finding(
        id=uuid.uuid4(),
        scan_job_id=job_id,
        title="SQL Injection in auth",
        severity="CRITICAL",
        category="sql_injection",
        source="semgrep",
        sources=["semgrep"],
        occurrence_count=1,
        cvss=9.0,
        brs=85.0,
        description="Raw SQL query concatenation",
    )

    mock_db = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalars.return_value.all.return_value = [mock_finding]
    mock_db.execute.return_value = mock_scalar

    mock_scan_jobs = AsyncMock()
    mock_scan_jobs.get.return_value = mock_job
    monkeypatch.setattr("app.api.v1.endpoints.scan.ScanJobRepository", lambda db: mock_scan_jobs)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/scan/{job_id}/findings")
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["findings"][0]["title"] == "SQL Injection in auth"
            assert data["findings"][0]["severity"] == "CRITICAL"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── 3. Repository Endpoints Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_list_repositories(mock_active_user):
    mock_repo = Repository(
        id=uuid.uuid4(),
        name="acme/payments",
        url="https://github.com/acme/payments.git",
        provider=RepoProviderType.GITHUB,
        default_branch="main",
        scheduled_scan_enabled=True,
        owner_id=MOCK_USER_ID,
    )

    mock_db = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalars.return_value.all.return_value = [mock_repo]
    mock_db.execute.return_value = mock_scalar

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/repositories")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["name"] == "acme/payments"
            assert data[0]["scheduled_scan_enabled"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_update_scheduled_scan(mock_active_user):
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        name="acme/payments",
        url="https://github.com/acme/payments.git",
        provider=RepoProviderType.GITHUB,
        default_branch="main",
        scheduled_scan_enabled=False,
        owner_id=MOCK_USER_ID,
    )

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_repo
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.patch(
                f"/api/v1/repositories/{repo_id}/scheduled-scan",
                json={"enabled": True},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["scheduled_scan_enabled"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── 4. Finding Intelligence Endpoint Tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_api_get_finding_intelligence(mock_active_user, monkeypatch):
    finding_id = uuid.uuid4()
    mock_finding = Finding(
        id=finding_id,
        scan_job_id=uuid.uuid4(),
        title="Hardcoded AWS API Key",
        severity="CRITICAL",
        category="hardcoded_secret",
        source="secrets",
        sources=["secrets"],
        occurrence_count=1,
        cvss=9.0,
        brs=80.0,
        description="Exposed AKIA key",
    )

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_finding

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(f"/api/v1/findings/{finding_id}/intelligence")
            assert res.status_code == 200
            data = res.json()
            assert data["finding_id"] == str(finding_id)
            assert "plain_english_explanation" in data
            assert "business_impact" in data
            assert data["why_detected"] != ""
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── 5. Risk Configuration Endpoints Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_api_risk_modules_and_preview(mock_active_user):
    mock_module = BusinessModule(
        id=uuid.uuid4(),
        name="Payments",
        keywords=["payment", "checkout", "transfer"],
        criticality_weight=9.5,
        asset_value=9.0,
        is_internet_facing_default=True,
        is_default=False,
    )
    mock_weight = RiskFactorWeight(
        id=uuid.uuid4(),
        factor_name="cvss",
        weight=0.30,
    )

    mock_db = AsyncMock()

    async def _mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement)
        scalar_mock = MagicMock()
        if "risk_factor_weights" in stmt_str or "RiskFactorWeight" in stmt_str:
            scalar_mock.scalars.return_value.all.return_value = [mock_weight]
        else:
            scalar_mock.scalars.return_value.all.return_value = [mock_module]
        return scalar_mock

    mock_db.execute.side_effect = _mock_execute

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. List modules
            res = await ac.get("/api/v1/risk/modules")
            assert res.status_code == 200
            assert len(res.json()) == 1

            # 2. Preview Score
            preview_res = await ac.post(
                "/api/v1/risk/preview",
                json={
                    "title": "SQL Injection in payment processor",
                    "severity": "CRITICAL",
                    "category": "sql_injection",
                    "cvss": 9.2,
                    "file_path": "app/payments/checkout.py",
                },
            )
            assert preview_res.status_code == 200
            preview_data = preview_res.json()
            assert preview_data["brs"] > 0.0
            assert preview_data["module"] == "Payments"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── 6. GitHub Webhook Endpoint Tests ──────────────────────────────────────────


WEBHOOK_SECRET = "test-webhook-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_missing_and_invalid_signatures(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "github_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr("app.api.v1.endpoints.webhooks.get_settings", lambda: settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        body = json.dumps({"zen": "Keep it simple."}).encode("utf-8")

        # 1. Missing signature -> 401
        res = await ac.post("/api/v1/webhooks/github", content=body, headers={"X-GitHub-Event": "ping"})
        assert res.status_code == 401

        # 2. Invalid signature -> 401
        res = await ac.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=invalid"},
        )
        assert res.status_code == 401

        # 3. Valid signature for ping -> 200 ping_ok
        res = await ac.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": _sign(body)},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "ping_ok"


@pytest.mark.asyncio
async def test_webhook_push_triggers_scan(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "github_webhook_secret", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "github_webhook_scan_all_branches", True)
    monkeypatch.setattr("app.api.v1.endpoints.webhooks.get_settings", lambda: settings)

    mock_repo = Repository(id=uuid.uuid4(), name="acme/service", url="https://github.com/acme/service.git")
    mock_job = ScanJob(id=uuid.uuid4(), repository_id=mock_repo.id, status=ScanJobStatus.QUEUED)

    monkeypatch.setattr(
        "app.api.v1.endpoints.webhooks.submit_repository",
        AsyncMock(return_value=(mock_repo, mock_job)),
    )

    payload = {
        "ref": "refs/heads/main",
        "deleted": False,
        "repository": {
            "name": "service",
            "full_name": "acme/service",
            "clone_url": "https://github.com/acme/service.git",
            "default_branch": "main",
        },
    }
    body = json.dumps(payload).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": _sign(body)},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "scan_queued"
        assert data["scan_job_id"] == str(mock_job.id)
        assert data["repository_id"] == str(mock_repo.id)
