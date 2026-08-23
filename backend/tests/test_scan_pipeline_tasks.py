"""
NOVA — Unit & Task Orchestration Tests for Step 5 (Celery Pipeline)
Tests scan_tasks, scanner_tasks, aggregator_tasks, artifact resolution,
Redis status transitions, cancellation, error handling, and chord aggregation.
"""

import asyncio
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ScanJobPriority, ScanJobStatus
from app.orchestrator import scan_status
from app.tasks.aggregator_tasks import _aggregate, _cleanup_artifact
from app.tasks.scan_tasks import _resolve_artifact, dispatch_scan_job
from app.tasks.scanner_tasks import run_scanner_task


# ── 1. Scanner Task Tests ─────────────────────────────────────────────────────


def test_run_scanner_task_success(monkeypatch):
    job_id = str(uuid.uuid4())
    mock_scanner = MagicMock()
    mock_scanner.scan = AsyncMock(
        return_value={
            "scanner": "semgrep",
            "success": True,
            "findings": [
                {
                    "title": "SQL Injection",
                    "severity": "HIGH",
                    "category": "sql_injection",
                    "source": "semgrep",
                    "cvss": 8.5,
                }
            ],
        }
    )

    monkeypatch.setattr("app.tasks.scanner_tasks.get_scanner", lambda name: mock_scanner)
    monkeypatch.setattr("app.orchestrator.scan_status.register_task_id", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.set_status", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.is_cancelled", lambda *a, **kw: False)

    res = run_scanner_task.run("semgrep", job_id, "/tmp/fake-repo")
    assert res["scanner"] == "semgrep"
    assert res["success"] is True
    assert len(res["findings"]) == 1
    assert res["findings"][0]["title"] == "SQL Injection"


def test_run_scanner_task_cancellation(monkeypatch):
    job_id = str(uuid.uuid4())
    monkeypatch.setattr("app.orchestrator.scan_status.register_task_id", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.set_status", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.is_cancelled", lambda *a, **kw: True)

    res = run_scanner_task.run("semgrep", job_id, "/tmp/fake-repo")
    assert res["scanner"] == "semgrep"
    assert res["success"] is False
    assert res.get("cancelled") is True


def test_run_scanner_task_exception_handling(monkeypatch):
    job_id = str(uuid.uuid4())
    mock_scanner = MagicMock()
    mock_scanner.scan = AsyncMock(side_effect=RuntimeError("Tool crashed unexpectedly"))

    monkeypatch.setattr("app.tasks.scanner_tasks.get_scanner", lambda name: mock_scanner)
    monkeypatch.setattr("app.orchestrator.scan_status.register_task_id", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.set_status", lambda *a, **kw: None)
    monkeypatch.setattr("app.orchestrator.scan_status.is_cancelled", lambda *a, **kw: False)

    res = run_scanner_task.run("semgrep", job_id, "/tmp/fake-repo")
    assert res["scanner"] == "semgrep"
    assert res["success"] is False
    assert "Tool crashed unexpectedly" in res.get("error", "")


# ── 2. Scan Intake & Artifact Resolution Tests ────────────────────────────────


def test_dispatch_scan_job(monkeypatch):
    mock_prepare = MagicMock()
    monkeypatch.setattr("app.tasks.scan_tasks.prepare_scan_task.apply_async", mock_prepare)

    mock_job = MagicMock()
    mock_job.id = uuid.uuid4()
    mock_job.priority = ScanJobPriority.CRITICAL

    dispatch_scan_job(mock_job)
    mock_prepare.assert_called_once()
    kwargs = mock_prepare.call_args.kwargs
    assert kwargs.get("queue") == "NOVA.critical"
    assert mock_prepare.call_args.kwargs["queue"] == "NOVA.critical"


@pytest.mark.asyncio
async def test_resolve_artifact_zip_extraction():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / "repo.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app/main.py", "print('hello')\n")
            zf.writestr("requirements.txt", "fastapi==0.115.0\n")

        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.artifact_path = str(zip_path)
        mock_job.repository_id = None

        mock_db = AsyncMock()
        extracted_dir = await _resolve_artifact(mock_job, mock_db)

        try:
            assert extracted_dir.exists()
            assert (extracted_dir / "app" / "main.py").exists()
            assert (extracted_dir / "requirements.txt").exists()
        finally:
            _cleanup_artifact(str(extracted_dir))


# ── 3. Artifact Cleanup Tests ─────────────────────────────────────────────────


def test_cleanup_artifact():
    temp_dir = tempfile.mkdtemp(prefix="nova-scan-test-cleanup-")
    assert os.path.exists(temp_dir)

    _cleanup_artifact(temp_dir)
    assert not os.path.exists(temp_dir)


# ── 4. Aggregator Task Async Logic Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_cancelled_flow(monkeypatch):
    job_id = str(uuid.uuid4())
    mock_job = MagicMock()
    mock_job.id = uuid.UUID(job_id)
    mock_job.status = ScanJobStatus.RUNNING

    mock_scan_jobs = AsyncMock()
    mock_scan_jobs.get.return_value = mock_job

    monkeypatch.setattr("app.orchestrator.scan_status.is_cancelled", lambda *a, **kw: True)
    monkeypatch.setattr("app.orchestrator.scan_status.clear", lambda *a, **kw: None)

    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db
    monkeypatch.setattr("app.tasks.aggregator_tasks.AsyncSessionLocal", lambda: mock_db)
    monkeypatch.setattr("app.tasks.aggregator_tasks.ScanJobRepository", lambda db: mock_scan_jobs)

    res = await _aggregate([], job_id)
    assert res.get("status") == "cancelled"
    mock_scan_jobs.mark_cancelled.assert_awaited_once_with(mock_job)


@pytest.mark.asyncio
async def test_aggregate_full_success_flow(monkeypatch):
    job_id = str(uuid.uuid4())
    mock_job = MagicMock()
    mock_job.id = uuid.UUID(job_id)
    mock_job.repository_id = uuid.uuid4()
    mock_job.status = ScanJobStatus.RUNNING

    mock_scan_jobs = AsyncMock()
    mock_scan_jobs.get.return_value = mock_job

    mock_results_repo = AsyncMock()
    mock_reports_repo = AsyncMock()
    mock_notif_service = AsyncMock()

    monkeypatch.setattr("app.orchestrator.scan_status.is_cancelled", lambda *a, **kw: False)
    monkeypatch.setattr("app.orchestrator.scan_status.clear", lambda *a, **kw: None)
    monkeypatch.setattr("app.tasks.report_tasks.generate_reports_task.apply_async", MagicMock())
    monkeypatch.setattr("app.tasks.aggregator_tasks.get_notification_service", lambda: mock_notif_service)

    mock_db = AsyncMock()
    mock_db.__aenter__.return_value = mock_db

    # Mock DB query results for weights, modules, repo
    mock_scalar = MagicMock()
    mock_scalar.scalars.return_value.all.return_value = []
    mock_scalar.scalar_one_or_none.return_value = MagicMock(name="TestRepo")
    mock_db.execute.return_value = mock_scalar

    monkeypatch.setattr("app.tasks.aggregator_tasks.AsyncSessionLocal", lambda: mock_db)
    monkeypatch.setattr("app.tasks.aggregator_tasks.ScanJobRepository", lambda db: mock_scan_jobs)
    monkeypatch.setattr("app.tasks.aggregator_tasks.ScanResultRepository", lambda db: mock_results_repo)
    monkeypatch.setattr("app.tasks.aggregator_tasks.ReportRepository", lambda db: mock_reports_repo)

    synthetic_results = [
        {
            "scanner": "semgrep",
            "success": True,
            "findings": [
                {
                    "title": "Hardcoded Secret",
                    "severity": "CRITICAL",
                    "category": "hardcoded_secret",
                    "source": "semgrep",
                    "cvss": 9.1,
                    "file_path": "app/config.py",
                    "line_number": 42,
                    "description": "AWS Secret key",
                }
            ],
        },
        {"scanner": "ast-grep", "success": True, "findings": []},
        {"scanner": "joern", "success": False, "findings": []},
        {"scanner": "pip-audit", "success": True, "findings": []},
        {"scanner": "osv", "success": True, "findings": []},
        {"scanner": "nvd", "success": True, "findings": []},
        {"scanner": "secrets", "success": True, "findings": []},
        {"scanner": "docker", "success": True, "findings": []},
        {"scanner": "yaml", "success": True, "findings": []},
    ]

    res = await _aggregate(synthetic_results, job_id)
    assert res.get("status") == "completed"
    assert res.get("total_findings") == 1
    assert res.get("scan_brs") > 0.0

    mock_scan_jobs.mark_completed.assert_awaited_once_with(mock_job)
    mock_results_repo.create_or_update.assert_awaited_once()
    mock_notif_service.notify_scan_completed.assert_awaited_once()
