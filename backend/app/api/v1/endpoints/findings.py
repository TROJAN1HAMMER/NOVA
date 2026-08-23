"""
NOVA — Finding Intelligence Endpoints
Provides grounded, structured explanations and remediation guidance for detected findings.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.finding import Finding
from app.models.user import User
from app.schemas.finding_intelligence import FindingIntelligenceResponse
from app.services.finding_intelligence.intelligence_service import build_intelligence

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/findings", tags=["Finding Intelligence"])


@router.get("/{finding_id}/intelligence", response_model=FindingIntelligenceResponse, summary="Get Finding Intelligence")
async def get_finding_intelligence_endpoint(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FindingIntelligenceResponse:
    """Retrieve grounded, structured explanation of a finding via the knowledge base."""
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding '{finding_id}' not found")

    return await build_intelligence(db, finding_id=finding, user_id=current_user.id)
