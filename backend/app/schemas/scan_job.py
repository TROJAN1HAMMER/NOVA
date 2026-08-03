"""
NOVA — ScanJob Pydantic Schemas
Request / response DTOs for the distributed scan orchestrator's endpoints.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.enums import ScanJobPriority, ScanJobStatus


class ScannerStatus(BaseModel):
    """One entry per independent scanner task (semgrep, ast-grep, joern,
    pip-audit, osv, nvd, secrets, docker, yaml) — see
    app/orchestrator/scan_status.py, the Redis-backed store this is read
    from."""

    status: str  # queued | running | completed | failed | cancelled
    updated_at: float
    task_id: Optional[str] = None
    error: Optional[str] = None
    findings_count: Optional[int] = None


class ScanJobSubmitRequest(BaseModel):
    """Body for `POST /scan/repository` — submit a repo URL to be scanned."""

    repo_url: str = Field(..., min_length=1, description="GitHub, GitLab, or Bitbucket repository URL")
    ref: Optional[str] = Field(
        default=None, description="Branch, tag, or commit SHA — defaults to the provider's default branch"
    )
    priority: ScanJobPriority = ScanJobPriority.NORMAL
    max_retries: int = Field(default=2, ge=0, le=10)
    timeout_seconds: int = Field(default=900, ge=30, le=7200)


class ScanJobCreateResponse(BaseModel):
    scan_job_id: uuid.UUID
    repository_id: uuid.UUID
    status: ScanJobStatus
    priority: ScanJobPriority
    message: str = "Scan job queued"


class ScanJobStatusResponse(BaseModel):
    scan_job_id: uuid.UUID
    repository_id: uuid.UUID
    repository_name: str
    status: ScanJobStatus
    priority: ScanJobPriority

    progress_percent: int
    current_stage: Optional[str] = None

    retry_count: int
    max_retries: int
    timeout_seconds: int

    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Populated only once a ScanResult exists (status == COMPLETED)
    total_findings: Optional[int] = None
    brs_score: Optional[float] = None
    brs_risk_level: Optional[str] = None
    attack_surface_exposure_score: Optional[float] = None
    attack_surface_exposure_level: Optional[str] = None
    # The same dict app/services/scanning/aggregator.py's
    # summarize_findings() builds and app/tasks/aggregator_tasks.py
    # augments further, stored verbatim on ScanResult.summary — exposed
    # here so dashboards can show a severity breakdown without an extra
    # per-scan findings fetch. Deliberately `dict[str, Any]`, not
    # `dict[str, int]`: alongside the five per-severity integer counts and
    # `total`, it also carries `by_category`/`by_source` (dict[str, int]),
    # `scanner_status` (dict[str, str]), and `aggregation` (a nested
    # dict) — a genuinely heterogeneous structure, not a flat counter map.
    summary: Optional[dict[str, Any]] = None

    # Live per-scanner progress while RUNNING — empty once the job reaches
    # a terminal state and app/orchestrator/scan_status.py's Redis keys
    # have expired/been cleared by the aggregator.
    worker_status: dict[str, ScannerStatus] = Field(default_factory=dict)


class ScanJobListResponse(BaseModel):
    total: int
    scan_jobs: list[ScanJobStatusResponse]
