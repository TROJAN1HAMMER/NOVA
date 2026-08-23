"""
NOVA — Celery Parallel Scanner Tasks
Executes each of the 9 independent security scanners (semgrep, ast-grep, joern,
pip-audit, osv, nvd, secrets, docker, yaml) in parallel as a worker task.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict

import structlog

from app.orchestrator import scan_status
from app.scanners.registry import get_scanner
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="NOVA.run_scanner",
    max_retries=0,
    acks_late=True,
)
def run_scanner_task(
    self,
    scanner_name: str,
    scan_job_id: str,
    artifact_path: str,
) -> Dict[str, Any]:
    """Execute a single security scanner against artifact_path."""
    req = getattr(self, "request", None)
    task_id = getattr(req, "id", None) or "local-task"
    scan_status.register_task_id(scan_job_id, task_id)
    scan_status.set_status(scan_job_id, scanner_name, "running", task_id=task_id)

    # Check if scan job was cancelled before or during execution
    if scan_status.is_cancelled(scan_job_id):
        logger.info("scanner_task.cancelled", scanner=scanner_name, scan_job_id=scan_job_id)
        scan_status.set_status(scan_job_id, scanner_name, "cancelled", task_id=task_id)
        return {
            "scanner": scanner_name,
            "success": False,
            "findings": [],
            "cancelled": True,
        }

    try:
        scanner = get_scanner(scanner_name)
        result = asyncio.run(scanner.scan(Path(artifact_path)))

        if scan_status.is_cancelled(scan_job_id):
            scan_status.set_status(scan_job_id, scanner_name, "cancelled", task_id=task_id)
            return {
                "scanner": scanner_name,
                "success": False,
                "findings": [],
                "cancelled": True,
            }

        success = result.get("success", True)
        findings = result.get("findings", [])
        findings_count = len(findings)

        if success:
            scan_status.set_status(
                scan_job_id,
                scanner_name,
                "completed",
                task_id=task_id,
                findings_count=findings_count,
            )
        else:
            scan_status.set_status(
                scan_job_id,
                scanner_name,
                "failed",
                task_id=task_id,
                error=result.get("error", "Scanner reported failure"),
                findings_count=findings_count,
            )

        return {
            "scanner": scanner_name,
            "success": success,
            "findings": findings,
            "error": result.get("error"),
        }

    except Exception as exc:
        logger.error(
            "scanner_task.failed",
            scanner=scanner_name,
            scan_job_id=scan_job_id,
            error=str(exc),
        )
        scan_status.set_status(
            scan_job_id,
            scanner_name,
            "failed",
            task_id=task_id,
            error=str(exc),
        )
        return {
            "scanner": scanner_name,
            "success": False,
            "findings": [],
            "error": str(exc),
        }
