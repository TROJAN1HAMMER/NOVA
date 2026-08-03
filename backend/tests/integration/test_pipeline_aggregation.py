"""
NOVA — Integration Test: Aggregation → Risk → Compliance → AI →
Reports → Notifications

Drives `app.tasks.aggregator_tasks._aggregate()` directly with synthetic
scanner results — the exact `{"scanner": ..., "success": ..., "findings":
[...]}` dict shape `scanner_tasks.py`'s chord produces — rather than
running the 9 real scanner tools. Those tools (semgrep, joern, docker,
...) aren't guaranteed to be installed in every environment this suite
runs in; supplying their *output* shape directly cuts the seam at exactly
the chord boundary, so everything downstream of it — cross-tool
aggregation, BRS scoring, compliance mapping, AI insight generation,
report rendering, and the notification dispatch — is real code exercised
against a real Postgres/Redis, not mocked.
"""

import asyncio
import uuid
from pathlib import Path

import pytest

from app.models.enums import ScanJobPriority, ScanJobStatus
from app.models.finding import Finding
from app.models.scan_job import ScanJob
from app.models.scan_result import ScanResult
from app.repositories.report_repository import ReportRepository
from app.repositories.scan_job_repository import ScanJobRepository
from app.repositories.scan_result_repository import ScanResultRepository
from app.tasks.aggregator_tasks import _aggregate

pytestmark = pytest.mark.integration


def _make_scanner_result(scanner: str, findings: list[dict], success: bool = True) -> dict:
    return {"scanner": scanner, "success": success, "findings": findings}


SYNTHETIC_RESULTS = [
    _make_scanner_result(
        "semgrep",
        [
            {
                "title": "Hardcoded AWS secret key",
                "severity": "CRITICAL",
                "category": "hardcoded_secret",
                "source": "semgrep",
                "cvss": 9.1,
                "file_path": "app/config.py",
                "line_number": 42,
                "description": "An AWS secret access key is hardcoded in source.",
            },
            {
                "title": "SQL built via string concatenation",
                "severity": "HIGH",
                "category": "sql_injection",
                "source": "semgrep",
                "cvss": 8.2,
                "file_path": "app/db/queries.py",
                "line_number": 17,
                "description": "User input is concatenated directly into a SQL query.",
            },
        ],
    ),
    _make_scanner_result(
        "secrets",
        [
            {
                "title": "Private key committed to repository",
                "severity": "CRITICAL",
                "category": "hardcoded_secret",
                "source": "secrets",
                "cvss": 9.8,
                "file_path": "certs/id_rsa",
                "description": "An RSA private key file was found committed to the repository.",
            }
        ],
    ),
    _make_scanner_result(
        "pip-audit",
        [
            {
                "title": "Known vulnerability in requests<2.31.0",
                "severity": "MEDIUM",
                "category": "vulnerable_dependency",
                "source": "pip-audit",
                "cvss": 5.3,
                "package": "requests",
                "package_version": "2.28.0",
                "cve": "CVE-2023-32681",
                "description": "requests before 2.31.0 leaks Proxy-Authorization headers on redirect.",
            }
        ],
    ),
    _make_scanner_result("ast-grep", []),
    _make_scanner_result("joern", [], success=False),  # Joern "not installed" is a realistic failure mode
    _make_scanner_result("osv", []),
    _make_scanner_result("nvd", []),
    _make_scanner_result("docker", []),
    _make_scanner_result("yaml", []),
]


@pytest.fixture
async def running_scan_job(db_session, test_repository):
    job = ScanJob(
        repository_id=test_repository.id,
        status=ScanJobStatus.RUNNING,
        priority=ScanJobPriority.NORMAL,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.commit()
    return job


async def test_full_pipeline_aggregation_to_notification(
    db_session, test_repository, running_scan_job, override_settings, webhook_capture_server
):
    """
    One synthetic scanner-result batch, pushed through the real pipeline:
    aggregation → BRS → compliance → AI (real template fallback, no key
    needed) → ScanResult/ScanJob persistence → notification (a real signed
    HTTP POST to a local capture server) → report generation.

    Report generation is deliberately NOT run in Celery eager mode here:
    `_aggregate()` dispatches it via `generate_reports_task.apply_async()`
    from *inside* its own already-running event loop, and eager mode would
    execute that task inline — straight into the same
    "asyncio.run() cannot be called from a running event loop" wall
    `report_tasks.py`'s own `asyncio.run(_generate_reports(...))` hits the
    moment it's invoked from a coroutine instead of a fresh Celery worker
    thread. Real (non-eager) dispatch has no such problem — it just
    publishes to Redis — so this test lets the real worker pool already
    running in this environment pick it up, and polls for completion the
    same way a real client would.
    """
    # Captured before dispatch: `_aggregate()` runs through its own,
    # separate `AsyncSessionLocal()` — once it commits, this test's
    # `db_session` fixture would need to expire `running_scan_job` to see
    # the change, but expiring an ORM object also expires its own `.id`,
    # which then can't be read as plain sync attribute access on an
    # AsyncSession without triggering SQLAlchemy's greenlet-bridge lazy
    # load machinery outside of an awaited context. Simplest correct fix:
    # keep the plain UUID, never touch the (now-stale) ORM object again.
    job_id = running_scan_job.id

    with override_settings(
        notifications_enabled=True,
        notify_min_severity="CRITICAL",
        webhook_url=webhook_capture_server["url"],
        webhook_secret="test-pipeline-secret",
        slack_webhook_url="",
        email_smtp_host="",
    ):
        await _aggregate([r for r in SYNTHETIC_RESULTS], str(job_id))

    # Targeted, not `expire_all()`: forces the next `.get()` to re-query
    # instead of returning this session's stale cached `running_scan_job`
    # (still showing RUNNING) from its identity map — without touching
    # `test_repository`'s object, which its own fixture teardown still
    # needs to read plain attributes off of.
    db_session.expire(running_scan_job)

    # ── ScanJob reached COMPLETED ──
    scan_jobs = ScanJobRepository(db_session)
    job = await scan_jobs.get(job_id)
    assert job.status == ScanJobStatus.COMPLETED, job.error_message
    print(f"PASS: ScanJob {job.id} marked COMPLETED")

    # ── Findings persisted with BRS + compliance + AI fields ──
    from sqlalchemy import select

    result = await db_session.execute(select(Finding).where(Finding.scan_job_id == job_id))
    findings = list(result.scalars().all())
    assert len(findings) >= 3, f"expected at least the 3 non-empty synthetic findings, got {len(findings)}"
    assert all(f.brs is not None for f in findings), "every persisted finding should carry a BRS contribution"
    assert any(f.ai_explanation for f in findings), "AI insight generation should have populated ai_explanation"
    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    assert len(critical_findings) == 2, "both synthetic CRITICAL findings should be present"
    print(f"PASS: {len(findings)} findings persisted, all BRS-scored, AI explanations present")

    # ── ScanResult persisted with real BRS/compliance summary ──
    results_repo = ScanResultRepository(db_session)
    scan_result = await results_repo.get_by_scan_job(job_id)
    assert scan_result is not None
    assert scan_result.total_findings == len(findings)
    assert scan_result.brs_score is not None and scan_result.brs_score > 0
    assert scan_result.summary.get("CRITICAL") == 2
    assert scan_result.compliance_summary, "compliance engine should have produced a non-empty snapshot"
    print(
        f"PASS: ScanResult persisted — BRS {scan_result.brs_score:.1f} "
        f"({scan_result.brs_risk_level}), summary={scan_result.summary}"
    )

    # ── Report rows created immediately (pending), before generation finishes ──
    reports_repo = ReportRepository(db_session)
    reports = await reports_repo.list_by_scan_job(job_id)
    assert reports, "aggregation should have created Report rows and dispatched generation"
    print(f"PASS: {len(reports)} Report rows created (pending) and generation dispatched to the real worker pool")

    # ── Reports actually generated to real local files, by the real
    #     Celery worker pool already running in this environment — poll
    #     rather than assert immediately, since generation is genuinely
    #     asynchronous relative to scan completion (see the test's own
    #     docstring for why this isn't run in eager mode). ──
    # Generous window: the same worker pool this test relies on is shared
    # with the rest of the suite (e.g. test_webhook_intake.py dispatches
    # real, expected-to-fail scans against nonexistent repos, which
    # occupy worker concurrency slots retrying/failing in the background)
    # — real contention, not a bug, but worth padding for.
    deadline = asyncio.get_event_loop().time() + 60
    completed_reports: list = []
    while asyncio.get_event_loop().time() < deadline:
        await db_session.commit()  # end the current transaction so the next query sees the worker's committed writes
        reports = await reports_repo.list_by_scan_job(job_id)
        completed_reports = [r for r in reports if r.status == "completed"]
        if len(completed_reports) == len(reports):
            break
        await asyncio.sleep(1)

    assert completed_reports, f"expected at least one completed report within 30s, got statuses: {[r.status for r in reports]}"
    for report in completed_reports:
        if report.storage_backend == "local" and report.file_path:
            assert Path(report.file_path).exists(), f"{report.report_type} report file missing on disk"
    print(f"PASS: {len(completed_reports)}/{len(reports)} report types generated as real local files by the real worker pool")

    # ── Notification actually delivered — a real signed HTTP POST ──
    assert webhook_capture_server["received"], "CRITICAL findings should have triggered a webhook notification"
    delivered = webhook_capture_server["received"][0]
    assert delivered["body"]["scan_job_id"] == str(job_id)
    assert delivered["body"]["severity"] == "CRITICAL"
    sig_header = delivered["headers"].get("X-NOVA-Signature", "")
    assert sig_header.startswith("sha256="), "webhook delivery should be HMAC-signed"

    import hashlib
    import hmac

    # Verify against the exact raw bytes received, the same way a real
    # receiver must — never against a re-serialized reconstruction of the
    # parsed body, which isn't guaranteed to produce byte-identical output.
    expected_sig = "sha256=" + hmac.new(
        b"test-pipeline-secret", delivered["raw"], hashlib.sha256
    ).hexdigest()
    assert sig_header == expected_sig, "HMAC signature must match the exact raw payload bytes delivered"
    print("PASS: notification delivered via real signed HTTP POST, payload + signature verified")
