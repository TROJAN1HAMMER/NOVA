"""
NOVA — Scan Management Endpoints
Handles submission, polling, cancellation, findings retrieval, compliance rollup,
streaming AI explanations, and live WebSocket progress for security scan jobs.
"""

import asyncio
import json
import uuid
from typing import Annotated, Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.enums import ScanJobPriority, ScanJobStatus
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.scan_result import ScanResult
from app.models.user import User
from app.orchestrator import scan_status
from app.repositories.scan_job_repository import ScanJobRepository
from app.schemas.compliance import ComplianceEngineResultSchema
from app.schemas.finding import FindingResponse, FindingsListResponse
from app.schemas.scan_job import (
    ScanJobCreateResponse,
    ScanJobListResponse,
    ScanJobStatusResponse,
    ScanJobSubmitRequest,
    ScannerStatus,
)
from app.services.compliance.compliance_engine import evaluate_compliance
from app.services.scan_intake import submit_premade, submit_repository, submit_upload
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/scan", tags=["Scanning"])


# ── Helper to build ScanJobStatusResponse ─────────────────────────────────────


async def _build_status_response(
    db: AsyncSession,
    job: ScanJob,
) -> ScanJobStatusResponse:
    repo_name = "Repository"
    if job.repository_id:
        repo = await db.get(Repository, job.repository_id)
        if repo and repo.name:
            repo_name = repo.name

    result_row = None
    if job.status == ScanJobStatus.COMPLETED:
        res = await db.execute(select(ScanResult).where(ScanResult.scan_job_id == job.id))
        result_row = res.scalar_one_or_none()

    # Read live worker statuses from Redis while running
    worker_status_dict: Dict[str, ScannerStatus] = {}
    if job.status in [ScanJobStatus.QUEUED, ScanJobStatus.RUNNING]:
        raw_worker_status = scan_status.get_worker_status(str(job.id))
        for scanner, status_info in raw_worker_status.items():
            if isinstance(status_info, dict):
                worker_status_dict[scanner] = ScannerStatus(
                    status=status_info.get("status", "queued"),
                    updated_at=status_info.get("updated_at", 0.0),
                    task_id=status_info.get("task_id"),
                    error=status_info.get("error"),
                    findings_count=status_info.get("findings_count"),
                )

    return ScanJobStatusResponse(
        scan_job_id=job.id,
        repository_id=job.repository_id or uuid.uuid4(),
        repository_name=repo_name,
        status=job.status,
        priority=job.priority,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        timeout_seconds=job.timeout_seconds,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        last_heartbeat_at=job.last_heartbeat_at,
        archived_at=job.archived_at,
        error_message=job.error_message,
        total_findings=result_row.total_findings if result_row else None,
        brs_score=result_row.brs_score if result_row else None,
        brs_risk_level=result_row.brs_risk_level if result_row else None,
        attack_surface_exposure_score=result_row.attack_surface_exposure_score if result_row else None,
        attack_surface_exposure_level=result_row.attack_surface_exposure_level if result_row else None,
        summary=result_row.summary if result_row else None,
        worker_status=worker_status_dict,
    )


# ── Scan Submission Endpoints ─────────────────────────────────────────────────


@router.post("", response_model=ScanJobCreateResponse, summary="Upload Repo")
async def upload_repo(
    file: UploadFile = File(...),
    priority: ScanJobPriority = Form(ScanJobPriority.NORMAL),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobCreateResponse:
    """Upload a repository ZIP file to start a security scan."""
    repo, job = await submit_upload(
        db,
        file=file,
        priority=priority,
        owner_id=current_user.id,
    )
    return ScanJobCreateResponse(
        scan_job_id=job.id,
        repository_id=repo.id,
        status=job.status,
        priority=job.priority,
        message="Scan job queued",
    )


@router.post("/repository", response_model=ScanJobCreateResponse, summary="Submit Repository")
async def submit_repository_endpoint(
    body: ScanJobSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobCreateResponse:
    """Submit a repository by URL to start an asynchronous scan."""
    repo, job = await submit_repository(
        db,
        repo_url=body.repo_url,
        ref=body.ref,
        priority=body.priority,
        owner_id=current_user.id,
        max_retries=body.max_retries,
        timeout_seconds=body.timeout_seconds,
    )
    return ScanJobCreateResponse(
        scan_job_id=job.id,
        repository_id=repo.id,
        status=job.status,
        priority=job.priority,
        message="Scan job queued",
    )


@router.post("/premade/{risk_level}", response_model=ScanJobCreateResponse, summary="Trigger Premade Scan")
async def trigger_premade_scan(
    risk_level: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobCreateResponse:
    """Trigger a scan for one of the pre-made benchmark repositories."""
    repo, job = await submit_premade(
        db,
        risk_level=risk_level,
        owner_id=current_user.id,
    )
    return ScanJobCreateResponse(
        scan_job_id=job.id,
        repository_id=repo.id,
        status=job.status,
        priority=job.priority,
        message="Scan job queued",
    )


# ── Scan Query & Lifecycle Endpoints ──────────────────────────────────────────


@router.get("", response_model=ScanJobListResponse, summary="List Scan Jobs")
async def list_scan_jobs(
    status: Optional[ScanJobStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobListResponse:
    """List the current user's scan jobs, optionally filtered by status."""
    query = select(ScanJob).where(ScanJob.owner_id == current_user.id)
    if status is not None:
        query = query.where(ScanJob.status == status)

    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar_one()

    query = query.order_by(ScanJob.created_at.desc()).limit(limit).offset(offset)
    jobs = (await db.execute(query)).scalars().all()

    items = []
    for job in jobs:
        items.append(await _build_status_response(db, job))

    return ScanJobListResponse(total=total, scan_jobs=items)


@router.get("/{scan_job_id}", response_model=ScanJobStatusResponse, summary="Get Scan Job Status")
async def get_scan_job_status(
    scan_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobStatusResponse:
    """Get the current status/progress of a scan job."""
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.get(scan_job_id, fresh=True)
    if job is None:
        raise NotFoundError(f"Scan job '{scan_job_id}' not found")

    return await _build_status_response(db, job)


@router.post("/{scan_job_id}/cancel", response_model=ScanJobStatusResponse, summary="Cancel Scan Job")
async def cancel_scan_job(
    scan_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ScanJobStatusResponse:
    """Cancel an active or queued scan job."""
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.get(scan_job_id, fresh=True)
    if job is None:
        raise NotFoundError(f"Scan job '{scan_job_id}' not found")

    if job.status not in [ScanJobStatus.COMPLETED, ScanJobStatus.FAILED, ScanJobStatus.CANCELLED]:
        scan_status.mark_cancelled(str(scan_job_id))
        task_ids = scan_status.get_all_task_ids(str(scan_job_id))
        for tid in task_ids:
            try:
                celery_app.control.revoke(tid, terminate=True)
            except Exception:
                pass
        await scan_jobs.mark_cancelled(job)

    return await _build_status_response(db, job)


from app.schemas.finding import ComplianceMappingSchema, FindingResponse, FindingsListResponse


def _to_finding_response(f: Finding) -> FindingResponse:
    compliance_obj = None
    if f.rbi_clause or f.pci_clause or f.swift_clause:
        compliance_obj = ComplianceMappingSchema(
            rbi_clause=f.rbi_clause,
            pci_clause=f.pci_clause,
            swift_clause=f.swift_clause,
        )
    return FindingResponse(
        id=f.id,
        scan_job_id=f.scan_job_id or uuid.uuid4(),
        title=f.title,
        severity=f.severity,
        category=f.category,
        source=f.source,
        sources=f.sources or [f.source],
        occurrence_count=f.occurrence_count or 1,
        cvss=f.cvss or 0.0,
        brs=f.brs or 0.0,
        brs_risk_level=f.brs_risk_level,
        file_path=f.file_path,
        line_number=f.line_number,
        description=f.description or "",
        package=f.package,
        package_version=f.package_version,
        cve=f.cve,
        cwe_id=f.cwe_id,
        cwe_name=f.cwe_name,
        owasp_category=f.owasp_category,
        owasp_name=f.owasp_name,
        mitre_technique_ids=f.mitre_technique_ids or [],
        ai_explanation=f.ai_explanation,
        ai_business_impact=f.ai_business_impact,
        ai_remediation=f.ai_remediation,
        compliance=compliance_obj,
    )


# ── Findings & Compliance Endpoints ───────────────────────────────────────────


@router.get("/{scan_job_id}/findings", response_model=FindingsListResponse, summary="Get Scan Job Findings")
async def get_scan_job_findings(
    scan_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FindingsListResponse:
    """Retrieve all findings for a given scan job."""
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.get(scan_job_id)
    if job is None:
        raise NotFoundError(f"Scan job '{scan_job_id}' not found")

    result = await db.execute(
        select(Finding).where(Finding.scan_job_id == scan_job_id).order_by(Finding.brs.desc())
    )
    findings = result.scalars().all()

    return FindingsListResponse(
        scan_job_id=scan_job_id,
        total=len(findings),
        findings=[_to_finding_response(f) for f in findings],
    )


@router.get("/{scan_job_id}/compliance", response_model=ComplianceEngineResultSchema, summary="Get Scan Job Compliance")
async def get_scan_job_compliance(
    scan_job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ComplianceEngineResultSchema:
    """Live regulatory compliance evaluation computed on demand from persisted findings."""
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.get(scan_job_id)
    if job is None:
        raise NotFoundError(f"Scan job '{scan_job_id}' not found")

    result = await db.execute(select(Finding).where(Finding.scan_job_id == scan_job_id))
    findings = result.scalars().all()

    findings_data = [
        {
            "title": f.title,
            "severity": f.severity,
            "category": f.category,
            "source": f.source,
            "cvss": f.cvss,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "cwe_id": f.cwe_id,
            "cve": f.cve,
            "description": f.description,
        }
        for f in findings
    ]

    report = evaluate_compliance(findings_data, scan_job_id=str(scan_job_id))
    return ComplianceEngineResultSchema(
        scan_job_id=report.scan_job_id,
        frameworks=[
            {
                "framework_name": f.framework_name,
                "short_code": f.short_code,
                "version": f.version,
                "controls": [
                    {
                        "requirement_id": c.requirement_id,
                        "title": c.title,
                        "description": c.description,
                        "status": c.status,
                        "evidence": [
                            {
                                "finding_title": ev.finding_title,
                                "severity": ev.severity,
                                "file_path": ev.file_path,
                                "line_number": ev.line_number,
                                "source": ev.source,
                            }
                            for ev in c.evidence
                        ],
                        "recommendation": c.recommendation,
                    }
                    for c in f.controls
                ],
                "total_controls": f.total_controls,
                "passed_controls": f.passed_controls,
                "failed_controls": f.failed_controls,
                "compliance_percentage": f.compliance_percentage,
            }
            for f in report.frameworks
        ],
        overall_compliance_percentage=report.overall_compliance_percentage,
    )


@router.get("/{scan_job_id}/findings/{finding_id}/explain/stream", summary="Stream Finding Explanation")
async def stream_finding_explanation(
    scan_job_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    """Server-Sent Events stream of an AI-generated explanation for a single finding."""
    result = await db.execute(
        select(Finding).where(Finding.id == finding_id, Finding.scan_job_id == scan_job_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise NotFoundError(f"Finding '{finding_id}' not found in scan job '{scan_job_id}'")

    async def event_generator():
        # Stream plain explanation words
        explanation = finding.ai_explanation or f"Vulnerability detected: {finding.title}"
        for word in explanation.split(" "):
            yield f"data: {json.dumps({'chunk': word + ' '})}\n\n"
            await asyncio.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Live WebSocket Progress Endpoint ──────────────────────────────────────────


@router.websocket("/ws/{scan_job_id}")
async def websocket_scan_progress(
    websocket: WebSocket,
    scan_job_id: uuid.UUID,
) -> None:
    """Real-time scan job progress and status push stream over WebSocket."""
    await websocket.accept()
    import redis.asyncio as redis_asyncio
    from app.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    job_id_str = str(scan_job_id)
    r_client = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
    pubsub = r_client.pubsub()
    channel = scan_status.updates_channel(job_id_str)

    try:
        await pubsub.subscribe(channel)

        # Send initial full status snapshot
        async with AsyncSessionLocal() as db:
            job = await db.get(ScanJob, scan_job_id)
            if job:
                resp = await _build_status_response(db, job)
                await websocket.send_text(resp.model_dump_json())

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                await websocket.send_text(str(message["data"]))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.debug("websocket.disconnected", scan_job_id=job_id_str)
    except Exception as exc:
        logger.warning("websocket.error", scan_job_id=job_id_str, error=str(exc))
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await r_client.close()
        except Exception:
            pass
