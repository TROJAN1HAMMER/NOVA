"""
NOVA — Scan Activity Analytics Routes
Backs the Security Analyst / Security Manager role dashboards with
aggregations over existing scan data — see
app/services/analytics/activity_service.py for what's actually computed
and why finding-level workflow metrics (assigned issues, SLA status,
mean-time-to-resolve) aren't included yet.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import MyActivitySummary, TeamActivitySummary
from app.services.analytics import activity_service

router = APIRouter()


@router.get("/analytics/my-activity", response_model=MyActivitySummary)
async def get_my_activity(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    A user's own scan activity — always their own data, so any
    authenticated active user can read it (no extra permission beyond
    being logged in; there's nothing to over-privilege here).
    """
    return await activity_service.get_my_activity(db, user_id=current_user.id)


@router.get("/analytics/team-activity", response_model=TeamActivitySummary)
async def get_team_activity(
    _current_user: Annotated[User, Depends(require_permission(Permission.TEAM_ANALYTICS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Org-wide scan activity broken down per user — Security Manager/Admin only."""
    return await activity_service.get_team_activity(db)
