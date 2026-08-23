"""
NOVA — Scan Intake Service
Central service for validating repository sources, resolving/creating Repository
records, creating queued ScanJob rows, and dispatching to the Celery pipeline.
Shared between POST /scan/repository, POST /scan, POST /scan/premade/{risk_level},
and POST /api/v1/webhooks/github.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import structlog
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import RepoProviderType, ScanJobPriority
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.repositories.scan_job_repository import ScanJobRepository
from app.tasks.scan_tasks import dispatch_scan_job
from app.utils.payload_generator import (
    CRITICAL_RISK_FILES,
    HIGH_RISK_FILES,
    LOW_RISK_FILES,
    MEDIUM_RISK_FILES,
    VERY_LOW_RISK_FILES,
    _create_zip_file,
)

logger = structlog.get_logger(__name__)
settings = get_settings()

PREMADE_BENCHMARKS = {
    "very_low": VERY_LOW_RISK_FILES,
    "very_low_risk": VERY_LOW_RISK_FILES,
    "low": LOW_RISK_FILES,
    "low_risk": LOW_RISK_FILES,
    "medium": MEDIUM_RISK_FILES,
    "medium_risk": MEDIUM_RISK_FILES,
    "high": HIGH_RISK_FILES,
    "high_risk": HIGH_RISK_FILES,
    "critical": CRITICAL_RISK_FILES,
    "critical_risk": CRITICAL_RISK_FILES,
}


def resolve_repo_provider_and_name(repo_url: str) -> Tuple[RepoProviderType, str]:
    """Parse a Git URL into its provider type and clean repository name."""
    parsed = urlparse(repo_url)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]

    if not path:
        raise ValidationAppError(f"Invalid repository URL path: {repo_url}")

    name = path
    if "gitlab" in host:
        provider = RepoProviderType.GITLAB
    elif "bitbucket" in host:
        provider = RepoProviderType.BITBUCKET
    else:
        provider = RepoProviderType.GITHUB

    return provider, name


async def submit_repository(
    db: AsyncSession,
    *,
    repo_url: str,
    ref: Optional[str] = None,
    priority: ScanJobPriority = ScanJobPriority.NORMAL,
    owner_id: Optional[uuid.UUID] = None,
    max_retries: int = 2,
    timeout_seconds: int = 900,
) -> Tuple[Repository, ScanJob]:
    """Submit a repository URL for asynchronous scanning.

    Reuses existing Repository row matching repo_url if present.
    """
    provider, name = resolve_repo_provider_and_name(repo_url)

    # 1. Reuse existing Repository or create new one
    result = await db.execute(select(Repository).where(Repository.url == repo_url))
    repo = result.scalar_one_or_none()

    if repo is None:
        clean_ref = ref.replace("refs/heads/", "") if ref else "main"
        repo = Repository(
            id=uuid.uuid4(),
            name=name,
            url=repo_url,
            provider=provider,
            default_branch=clean_ref,
            owner_id=owner_id,
        )
        db.add(repo)
        await db.flush()

    clean_ref = ref.replace("refs/heads/", "") if ref else (repo.default_branch or "main")

    # 2. Create queued ScanJob
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.create_queued(
        repository_id=repo.id,
        priority=priority,
        owner_id=owner_id,
        ref=clean_ref,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )

    # 3. Commit DB so job row is queryable by Celery worker
    await db.commit()

    # 4. Dispatch Celery task
    dispatch_scan_job(job)
    logger.info(
        "scan_intake.repository_submitted",
        repository_id=str(repo.id),
        scan_job_id=str(job.id),
        url=repo_url,
        ref=clean_ref,
        priority=priority.value if hasattr(priority, "value") else str(priority),
    )

    return repo, job


async def submit_upload(
    db: AsyncSession,
    *,
    file: UploadFile,
    priority: ScanJobPriority = ScanJobPriority.NORMAL,
    owner_id: Optional[uuid.UUID] = None,
    max_retries: int = 2,
    timeout_seconds: int = 900,
) -> Tuple[Repository, ScanJob]:
    """Submit a ZIP upload for asynchronous scanning."""
    filename = file.filename or "upload.zip"
    if not filename.lower().endswith(".zip"):
        raise ValidationAppError("Only .zip archives are supported for repository uploads")

    upload_dir = Path(getattr(settings, "upload_dir", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / f"nova-upload-{uuid.uuid4().hex}.zip"

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    clean_name = filename[:-4] if filename.lower().endswith(".zip") else filename

    # 1. Create upload Repository
    repo = Repository(
        id=uuid.uuid4(),
        name=clean_name,
        url=None,
        provider=RepoProviderType.UPLOAD,
        default_branch="main",
        owner_id=owner_id,
    )
    db.add(repo)
    await db.flush()

    # 2. Create queued ScanJob with artifact_path
    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.create_queued(
        repository_id=repo.id,
        priority=priority,
        owner_id=owner_id,
        ref="main",
        artifact_path=str(target_path),
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )

    await db.commit()
    dispatch_scan_job(job)
    logger.info(
        "scan_intake.upload_submitted",
        repository_id=str(repo.id),
        scan_job_id=str(job.id),
        filename=filename,
        artifact_path=str(target_path),
        priority=priority.value if hasattr(priority, "value") else str(priority),
    )

    return repo, job


async def submit_premade(
    db: AsyncSession,
    *,
    risk_level: str,
    priority: ScanJobPriority = ScanJobPriority.NORMAL,
    owner_id: Optional[uuid.UUID] = None,
) -> Tuple[Repository, ScanJob]:
    """Submit a pre-made benchmark test suite for scanning."""
    normalized_key = risk_level.lower().replace("-", "_")
    files_dict = PREMADE_BENCHMARKS.get(normalized_key)
    if not files_dict:
        valid_options = ", ".join(["very_low", "low", "medium", "high", "critical"])
        raise NotFoundError(f"Premade benchmark '{risk_level}' not found. Available: {valid_options}")

    upload_dir = Path(getattr(settings, "upload_dir", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = upload_dir / f"premade_{normalized_key}_{uuid.uuid4().hex[:8]}.zip"
    _create_zip_file(files_dict, zip_path)

    repo_name = f"benchmark-{normalized_key.replace('_risk', '')}"
    repo = Repository(
        id=uuid.uuid4(),
        name=repo_name,
        url=None,
        provider=RepoProviderType.UPLOAD,
        default_branch="main",
        owner_id=owner_id,
    )
    db.add(repo)
    await db.flush()

    scan_jobs = ScanJobRepository(db)
    job = await scan_jobs.create_queued(
        repository_id=repo.id,
        priority=priority,
        owner_id=owner_id,
        ref="main",
        artifact_path=str(zip_path),
    )

    await db.commit()
    dispatch_scan_job(job)
    logger.info(
        "scan_intake.premade_submitted",
        repository_id=str(repo.id),
        scan_job_id=str(job.id),
        risk_level=risk_level,
    )

    return repo, job
