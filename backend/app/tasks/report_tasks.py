"""
NOVA — Async Report Generation

Dispatched as its own Celery task, separate from
`app.tasks.aggregator_tasks.aggregate_scan_results_task`, specifically so
report rendering (reportlab PDF layout across 2 report types, CSV/JSON
writes, S3/MinIO upload latency) never delays `ScanJob.mark_completed()`.
Findings become visible to the user the moment aggregation finishes;
reports finish shortly after. `GET /reports/{scan_job_id}` tracks each
artifact's status (pending -> generating -> completed|failed)
independently, so a client polls instead of guessing when a report is
ready — see `app/models/report.py` and `ReportRepository`'s lifecycle
methods.

Every report type is generated and persisted independently: one type
failing (a bad chart edge case, an S3 hiccup) doesn't block the others —
same per-item fault isolation the rest of the pipeline already uses for
the 9 parallel scanners.

All the data this task needs (findings as plain dicts, BRS/compliance/AI
results already computed) is passed in as task arguments rather than
re-derived from the database — it was already computed once during
aggregation, so recomputing it here would just be duplicate work for data
that doesn't change.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

import structlog

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.repositories.report_repository import ReportRepository
from app.services.reports import report_generator
from app.services.reports.report_generator import ReportContext
from app.services.reports.storage import get_storage
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(
    bind=True,
    name="NOVA.generate_reports",
    max_retries=1,
    default_retry_delay=15,
    acks_late=True,
)
def generate_reports_task(
    self,
    scan_job_id: str,
    repo_name: str,
    findings: list[dict],
    brs_score: float,
    brs_risk_level: str,
    attack_surface_exposure_score: float,
    attack_surface_exposure_level: str,
    compliance_summary: dict,
    summary: dict,
    sbom: Optional[dict],
    unified_json: dict,
    compliance_json: dict,
) -> dict:
    return asyncio.run(
        _generate_reports(
            scan_job_id=scan_job_id,
            repo_name=repo_name,
            findings=findings,
            brs_score=brs_score,
            brs_risk_level=brs_risk_level,
            attack_surface_exposure_score=attack_surface_exposure_score,
            attack_surface_exposure_level=attack_surface_exposure_level,
            compliance_summary=compliance_summary,
            summary=summary,
            sbom=sbom,
            unified_json=unified_json,
            compliance_json=compliance_json,
        )
    )


async def _generate_reports(
    *,
    scan_job_id: str,
    repo_name: str,
    findings: list[dict],
    brs_score: float,
    brs_risk_level: str,
    attack_surface_exposure_score: float,
    attack_surface_exposure_level: str,
    compliance_summary: dict,
    summary: dict,
    sbom: Optional[dict],
    unified_json: dict,
    compliance_json: dict,
) -> dict:
    reports_dir = Path(settings.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    storage = get_storage()
    job_uuid = uuid.UUID(scan_job_id)

    ctx = ReportContext(
        scan_id=scan_job_id,
        repo_name=repo_name,
        findings=findings,
        brs_score=brs_score,
        brs_risk_level=brs_risk_level,
        attack_surface_exposure_score=attack_surface_exposure_score,
        attack_surface_exposure_level=attack_surface_exposure_level,
        compliance_summary=compliance_summary,
        summary=summary,
        sbom=sbom,
        unified_json=unified_json,
        compliance_json=compliance_json,
    )

    results: dict[str, Optional[str]] = {}

    async with AsyncSessionLocal() as db:
        reports_repo = ReportRepository(db)

        for report_type, builder in report_generator.REPORT_BUILDERS.items():
            report = await reports_repo.get_by_type(job_uuid, report_type)
            if report is None:
                # The aggregator creates every "pending" row up front; this
                # is just a safety net if that ever didn't happen.
                report = await reports_repo.create_pending(scan_job_id=job_uuid, report_type=report_type)
                await db.commit()

            try:
                await reports_repo.mark_generating(report.id)
                await db.commit()

                local_path = await asyncio.to_thread(builder, ctx, reports_dir)

                if local_path is None:
                    await reports_repo.mark_failed(
                        report.id, error_message="No data was available to generate this report type."
                    )
                    await db.commit()
                    results[report_type] = None
                    logger.info("report_tasks.report_skipped", report_type=report_type, scan_job_id=scan_job_id)
                    continue

                storage_key = f"reports/{scan_job_id}/{local_path.name}"
                stored_reference = await asyncio.to_thread(storage.upload_report, local_path, storage_key)

                await reports_repo.mark_completed(
                    report.id,
                    file_path=str(local_path),
                    storage_backend=storage.backend,
                    storage_key=stored_reference if storage.is_s3() else None,
                )
                await db.commit()
                results[report_type] = str(local_path)
                logger.info("report_tasks.report_ready", report_type=report_type, scan_job_id=scan_job_id)

            except Exception as exc:
                logger.exception(
                    "report_tasks.report_failed", report_type=report_type, scan_job_id=scan_job_id, error=str(exc)
                )
                await reports_repo.mark_failed(report.id, error_message=str(exc))
                await db.commit()
                results[report_type] = None

    logger.info(
        "report_tasks.complete",
        scan_job_id=scan_job_id,
        succeeded=[k for k, v in results.items() if v],
        failed=[k for k, v in results.items() if not v],
    )
    return results
