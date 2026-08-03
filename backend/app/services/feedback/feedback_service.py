"""
NOVA — Feedback Service
Unlike search-analytics logging, feedback submission IS the primary
action of its own request (not a side-effect of something else), so this
uses the caller's normal request-scoped session/transaction rather than
its own short-lived one.
"""

import uuid
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import record_feedback
from app.models.knowledge import Feedback


async def submit_feedback(
    db: AsyncSession,
    *,
    feature: str,
    reference_id: str,
    rating: int,
    comment: Optional[str],
    user_id: Optional[uuid.UUID],
) -> Feedback:
    entry = Feedback(
        feature=feature,
        reference_id=reference_id,
        rating=rating,
        comment=comment,
        user_id=user_id,
    )
    db.add(entry)
    await db.flush()
    record_feedback(feature, positive=rating > 0)
    return entry


async def get_summary(db: AsyncSession, *, feature: Optional[str] = None) -> dict:
    query = select(
        func.count(Feedback.id),
        func.sum(case((Feedback.rating > 0, 1), else_=0)),
    )
    if feature:
        query = query.where(Feedback.feature == feature)
    total, positive = (await db.execute(query)).one()
    total = total or 0
    positive = int(positive or 0)
    negative = total - positive

    return {
        "total_feedback": total,
        "positive_count": positive,
        "negative_count": negative,
        "positive_rate": round(positive / total, 4) if total else None,
    }
