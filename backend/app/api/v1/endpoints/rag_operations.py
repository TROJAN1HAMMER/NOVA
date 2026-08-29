"""
NOVA — RAG Operations Routes (Milestone 5)
Consolidates the benchmark trigger, search-analytics summary, and
feedback submission/summary into one router — all three back the same
admin-facing frontend page (RAG Operations), not because they share
implementation.

Permission choice: `Permission.TEAM_ANALYTICS_READ` (Security Manager +
Admin) gates the three operational/aggregate views — the same persona
already reviewing team scan activity is the natural audience for "how is
the RAG system performing," and this avoids adding a new Permission enum
member for a hardening milestone. `/feedback` submission itself is any
authenticated user — giving feedback on an answer you just saw doesn't
need a special permission.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.auth.permissions import Permission, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag_operations import (
    BenchmarkResultSchema,
    FeedbackSubmitRequest,
    FeedbackSummaryResponse,
    SearchAnalyticsSummaryResponse,
)
from app.services.benchmark import benchmark_service
from app.services.feedback import feedback_service
from app.services.search_analytics import analytics_service

router = APIRouter()


@router.post("/rag-operations/benchmark", response_model=BenchmarkResultSchema)
async def run_benchmark(
    _current_user: Annotated[User, Depends(require_permission(Permission.KNOWLEDGE_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Triggers a live embed/search/rerank/(LLM) timing probe against the
    knowledge base as it exists right now — see benchmark_service.py."""
    result = await benchmark_service.run_benchmark(db)
    return BenchmarkResultSchema(
        ran_at=result.ran_at,
        stages=[
            {"stage": s.stage, "avg_duration_ms": s.avg_duration_ms, "detail": s.detail} for s in result.stages
        ],
        total_duration_ms=result.total_duration_ms,
        documents_indexed=result.documents_indexed,
        llm_configured=result.llm_configured,
    )


@router.get("/rag-operations/search-analytics", response_model=SearchAnalyticsSummaryResponse)
async def get_search_analytics(
    _current_user: Annotated[User, Depends(require_permission(Permission.TEAM_ANALYTICS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    feature: Optional[str] = None,
):
    return SearchAnalyticsSummaryResponse(**await analytics_service.get_summary(db, feature=feature))


@router.post("/feedback", status_code=201)
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry = await feedback_service.submit_feedback(
        db,
        feature=payload.feature,
        reference_id=payload.reference_id,
        rating=payload.rating,
        comment=payload.comment,
        user_id=current_user.id,
    )
    await db.commit()
    return {"id": str(entry.id), "status": "recorded"}


@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    _current_user: Annotated[User, Depends(require_permission(Permission.TEAM_ANALYTICS_READ))],
    db: Annotated[AsyncSession, Depends(get_db)],
    feature: Optional[str] = None,
):
    return FeedbackSummaryResponse(**await feedback_service.get_summary(db, feature=feature))
