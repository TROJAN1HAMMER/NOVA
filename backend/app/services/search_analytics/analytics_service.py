"""
NOVA — Search Analytics Service
`log_search` uses its own short-lived DB session, never the caller's —
the same pattern app/services/audit/audit_logger.py already established
and for the same reason: an analytics write failing (or a Redis/DB blip)
must never affect the actual search/chat/ask response, and the log entry
must survive even if the caller's own transaction later rolls back for
an unrelated reason.
"""

import uuid
from typing import Optional

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.knowledge import SearchAnalyticsLog

logger = structlog.get_logger(__name__)

DEFAULT_RECENT_LIMIT = 20


async def log_search(
    *,
    feature: str,
    query: str,
    result_count: int,
    top_score: Optional[float],
    latency_ms: float,
    user_id: Optional[uuid.UUID],
) -> None:
    """Never raises — fails open, matching audit_logger.log_action."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                SearchAnalyticsLog(
                    feature=feature,
                    query=query,
                    result_count=result_count,
                    top_score=top_score,
                    latency_ms=latency_ms,
                    user_id=user_id,
                )
            )
            await db.commit()
    except Exception as exc:
        logger.warning("search_analytics.log_failed", feature=feature, error=str(exc))


async def get_summary(db: AsyncSession, *, feature: Optional[str] = None, recent_limit: int = DEFAULT_RECENT_LIMIT) -> dict:
    stats_query = select(
        func.count(SearchAnalyticsLog.id),
        func.avg(SearchAnalyticsLog.latency_ms),
        func.avg(SearchAnalyticsLog.result_count),
        func.sum(case((SearchAnalyticsLog.result_count == 0, 1), else_=0)),
    )
    if feature:
        stats_query = stats_query.where(SearchAnalyticsLog.feature == feature)
    total, avg_latency, avg_results, zero_result_count = (await db.execute(stats_query)).one()
    total = total or 0
    zero_result_count = int(zero_result_count or 0)

    recent_query = select(SearchAnalyticsLog).order_by(SearchAnalyticsLog.created_at.desc()).limit(recent_limit)
    if feature:
        recent_query = recent_query.where(SearchAnalyticsLog.feature == feature)
    recent_rows = (await db.execute(recent_query)).scalars().all()

    return {
        "total_searches": total,
        "average_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
        "average_result_count": round(float(avg_results), 2) if avg_results is not None else None,
        "zero_result_count": zero_result_count,
        # The signal that matters most: a sustained high zero-result rate
        # for a feature means the knowledge base has a coverage gap, not
        # that the retrieval pipeline is broken.
        "zero_result_rate": round(zero_result_count / total, 4) if total else None,
        "recent_searches": [
            {
                "feature": row.feature,
                "query": row.query,
                "result_count": row.result_count,
                "top_score": row.top_score,
                "latency_ms": row.latency_ms,
                "created_at": row.created_at.isoformat(),
            }
            for row in recent_rows
        ],
    }
