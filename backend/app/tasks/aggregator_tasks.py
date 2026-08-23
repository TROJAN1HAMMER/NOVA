"""
NOVA — Celery Scan Aggregator Callback Task
Executes as the fan-in chord callback: aggregates findings from all 9 parallel scanners,
computes risk and compliance scores, populates AI intelligence, persists results,
dispatches report generation, and sends notifications.
"""

import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.enums import ScanJobStatus
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.risk_config import BusinessModule, RiskFactorWeight
from app.models.scan_job import ScanJob
from app.orchestrator import scan_status
from app.repositories.report_repository import ReportRepository
from app.repositories.scan_job_repository import ScanJobRepository
from app.repositories.scan_result_repository import ScanResultRepository
from app.services.aggregation.aggregator import aggregate_scanner_results
from app.services.ai.templates import get_template
from app.services.finding_intelligence.intelligence_service import (
    build_intelligence,
    build_why_detected,
)
from app.services.notifications.notification_service import get_notification_service
from app.services.reports import report_generator
from app.tasks.report_tasks import generate_reports_task
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="NOVA.aggregate_scan_results",
    max_retries=1,
    default_retry_delay=10,
    acks_late=True,
)
def aggregate_scan_results_task(
    self,
    scanner_results: List[Dict[str, Any]],
    scan_job_id: str,
    artifact_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Celery chord fan-in callback for all 9 parallel scanner tasks."""
    return asyncio.run(
        _aggregate(scanner_results=scanner_results, scan_job_id=scan_job_id, artifact_path=artifact_path)
    )


def _cleanup_artifact(artifact_path: Optional[str]) -> None:
    """Safely delete temporary extracted scan directory if marked for cleanup."""
    if not artifact_path:
        return
    try:
        p = Path(artifact_path)
        if p.exists() and "nova-scan-" in p.name:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                os.remove(p)
            logger.info("aggregator.cleanup_artifact_completed", path=str(p))
    except Exception as exc:
        logger.warning("aggregator.cleanup_artifact_failed", path=str(artifact_path), error=str(exc))


async def _aggregate(
    scanner_results: List[Dict[str, Any]],
    scan_job_id: str,
    artifact_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Async execution of findings aggregation, BRS scoring, AI enrichment, and persistence."""
    job_uuid = uuid.UUID(scan_job_id)

    async with AsyncSessionLocal() as db:
        scan_jobs = ScanJobRepository(db)
        job = await scan_jobs.get(job_uuid, fresh=True)
        if job is None:
            logger.error("aggregator.job_not_found", scan_job_id=scan_job_id)
            _cleanup_artifact(artifact_path)
            return {"error": "Job not found"}

        # Handle cancellation
        if scan_status.is_cancelled(scan_job_id) or job.status == ScanJobStatus.CANCELLED:
            logger.info("aggregator.job_cancelled", scan_job_id=scan_job_id)
            await scan_jobs.mark_cancelled(job)
            scan_status.clear(scan_job_id)
            _cleanup_artifact(artifact_path)
            return {"status": "cancelled"}

        repo_name = "Repository"
        if job.repository_id:
            repo_res = await db.execute(select(Repository).where(Repository.id == job.repository_id))
            repo_obj = repo_res.scalar_one_or_none()
            if repo_obj and repo_obj.name:
                repo_name = repo_obj.name

        try:
            # 1. Fetch risk factor weights & custom business modules
            weights_res = await db.execute(select(RiskFactorWeight))
            weights = list(weights_res.scalars().all())

            modules_res = await db.execute(select(BusinessModule))
            custom_modules = list(modules_res.scalars().all())

            # 2. Run Aggregator Core
            (
                enriched_findings,
                severity_counts,
                scan_brs,
                scan_risk_level,
                compliance_summary,
            ) = aggregate_scanner_results(
                scanner_results=scanner_results,
                modules=custom_modules,
                factor_weights=weights,
            )

            # 3. Calculate Attack Surface Exposure
            critical_count = severity_counts.get("CRITICAL", 0)
            exposure_score = min(100.0, round(float(len(enriched_findings)) * 5.0 + (critical_count * 15.0), 2))
            exposure_level = "High" if exposure_score >= 60.0 else ("Medium" if exposure_score >= 30.0 else "Low")

            # 4. Generate AI explanations and persist Finding entities
            for finding_data in enriched_findings:
                category = finding_data.get("category", "unknown")
                why_detected = build_why_detected(finding_data)

                # Generate AI insights with template fallback
                ai_explanation = None
                ai_business_impact = None
                ai_remediation = None

                try:
                    intel_resp = await build_intelligence(db, finding_data)
                    ai_explanation = intel_resp.plain_english_explanation
                    ai_business_impact = intel_resp.business_impact
                    ai_remediation = intel_resp.recommended_remediation
                except Exception as ai_exc:
                    logger.debug("aggregator.ai_intelligence_fallback", error=str(ai_exc))
                    # Fallback to category templates
                    tmpl = get_template(category)
                    ai_explanation = tmpl.get("explanation") or tmpl.get("plain_english", "")
                    ai_business_impact = tmpl.get("business_impact", "")
                    ai_remediation = tmpl.get("remediation") or tmpl.get("recommended_remediation", "")

                finding_row = Finding(
                    scan_job_id=job_uuid,
                    title=finding_data.get("title", ""),
                    severity=finding_data.get("severity", "MEDIUM"),
                    category=category,
                    source=finding_data.get("source", "unknown"),
                    sources=finding_data.get("sources", [finding_data.get("source")]),
                    occurrence_count=finding_data.get("occurrence_count", 1),
                    cvss=finding_data.get("cvss", 0.0),
                    brs=finding_data.get("brs", 0.0),
                    brs_risk_level=finding_data.get("brs_risk_level"),
                    module=finding_data.get("module"),
                    file_path=finding_data.get("file_path"),
                    line_number=finding_data.get("line_number"),
                    description=finding_data.get("description", ""),
                    package=finding_data.get("package"),
                    package_version=finding_data.get("package_version"),
                    cve=finding_data.get("cve"),
                    cwe_id=finding_data.get("cwe_id"),
                    cwe_name=finding_data.get("cwe_name"),
                    owasp_category=finding_data.get("owasp_category"),
                    owasp_name=finding_data.get("owasp_name"),
                    mitre_technique_ids=finding_data.get("mitre_technique_ids"),
                    rbi_clause=finding_data.get("rbi_clause"),
                    pci_clause=finding_data.get("pci_clause"),
                    swift_clause=finding_data.get("swift_clause"),
                    ai_explanation=ai_explanation,
                    ai_business_impact=ai_business_impact,
                    ai_remediation=ai_remediation,
                )
                db.add(finding_row)

            await db.flush()

            # 5. Persist ScanResult
            results_repo = ScanResultRepository(db)
            await results_repo.create_or_update(
                scan_job_id=job_uuid,
                total_findings=len(enriched_findings),
                brs_score=scan_brs,
                brs_risk_level=scan_risk_level,
                attack_surface_exposure_score=exposure_score,
                attack_surface_exposure_level=exposure_level,
                summary=severity_counts,
                compliance_summary=compliance_summary,
            )

            # 6. Create Pending Report rows
            reports_repo = ReportRepository(db)
            for r_type in report_generator.REPORT_BUILDERS.keys():
                await reports_repo.create_pending(scan_job_id=job_uuid, report_type=r_type)

            await db.flush()

            # 7. Dispatch Report Generation Task
            generate_reports_task.apply_async(
                kwargs={
                    "scan_job_id": scan_job_id,
                    "repo_name": repo_name,
                    "findings": enriched_findings,
                    "brs_score": scan_brs,
                    "brs_risk_level": scan_risk_level,
                    "attack_surface_exposure_score": exposure_score,
                    "attack_surface_exposure_level": exposure_level,
                    "compliance_summary": compliance_summary,
                    "summary": severity_counts,
                    "sbom": None,
                    "unified_json":{"findings": enriched_findings, "summary": severity_counts},
                    "compliance_json": compliance_summary,
                }
            )

            # 8. Mark ScanJob COMPLETED
            await scan_jobs.mark_completed(job)

            # 9. Send Notifications
            await get_notification_service().notify_scan_completed(
                scan_job_id=scan_job_id,
                repository_name=repo_name,
                brs_score=scan_brs,
                risk_level=scan_risk_level,
                severity_counts=severity_counts,
            )

            # 10. Clean up Redis status and temporary files
            scan_status.clear(scan_job_id)
            _cleanup_artifact(artifact_path)

            logger.info(
                "aggregator.pipeline_completed",
                scan_job_id=scan_job_id,
                findings_count=len(enriched_findings),
                scan_brs=scan_brs,
                risk_level=scan_risk_level,
            )

            return {
                "scan_job_id": scan_job_id,
                "total_findings": len(enriched_findings),
                "scan_brs": scan_brs,
                "risk_level": scan_risk_level,
                "status": "completed",
            }

        except Exception as exc:
            logger.error("aggregator.execution_failed", scan_job_id=scan_job_id, error=str(exc))
            if scan_jobs.should_retry(job):
                await scan_jobs.prepare_retry(job)
            else:
                await scan_jobs.mark_failed(job, error_message=f"Aggregation pipeline failed: {exc}")
            await db.commit()
            _cleanup_artifact(artifact_path)
            raise
