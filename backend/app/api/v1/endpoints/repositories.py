"""
NOVA — Repository Management Endpoints
Lists registered repositories and manages nightly re-scan scheduling configurations.
"""

import uuid
from typing import List

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.core.exceptions import NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models.repository import Repository
from app.models.user import User
from app.schemas.repository import RepositoryResponse, ScheduledScanUpdateRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=List[RepositoryResponse], summary="List Repositories")
async def list_repositories(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[RepositoryResponse]:
    """List the current user's submitted repositories."""
    query = (
        select(Repository)
        .where(Repository.owner_id == current_user.id)
        .order_by(Repository.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    repos = result.scalars().all()
    return [RepositoryResponse.model_validate(r) for r in repos]


@router.patch("/{repository_id}/scheduled-scan", response_model=RepositoryResponse, summary="Update Scheduled Scan")
async def update_scheduled_scan(
    repository_id: uuid.UUID,
    body: ScheduledScanUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> RepositoryResponse:
    """Opt a repository in to (or out of) nightly re-scanning."""
    repo = await db.get(Repository, repository_id)
    if repo is None or (repo.owner_id and repo.owner_id != current_user.id):
        raise NotFoundError(f"Repository '{repository_id}' not found")

    if body.enabled and not repo.url:
        raise ValidationAppError("Only URL-based repositories can be scheduled for recurring scans")

    repo.scheduled_scan_enabled = body.enabled
    await db.commit()
    await db.refresh(repo)

    logger.info(
        "repositories.scheduled_scan_updated",
        repository_id=str(repo.id),
        enabled=body.enabled,
    )
    return RepositoryResponse.model_validate(repo)
