"""
NOVA — Search & User Activity Analytics
Pure aggregation over SearchAnalyticsLog, KnowledgeDocument, and ChatMessage data.
"""

import uuid
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeDocument, SearchAnalyticsLog
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.analytics import MyActivitySummary, RecentScanSummary, TeamActivitySummary, TeamMemberActivity


async def get_my_activity(db: AsyncSession, *, user_id: uuid.UUID) -> MyActivitySummary:
    search_count_res = await db.execute(
        select(func.count(SearchAnalyticsLog.id)).where(SearchAnalyticsLog.user_id == user_id)
    )
    total_searches = search_count_res.scalar_one() or 0

    doc_count_res = await db.execute(
        select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.uploaded_by_id == user_id)
    )
    total_docs = doc_count_res.scalar_one() or 0

    # Real average latency from search analytics
    latency_res = await db.execute(
        select(func.avg(SearchAnalyticsLog.latency_ms)).where(SearchAnalyticsLog.user_id == user_id)
    )
    avg_latency_ms = latency_res.scalar_one()
    avg_duration = round(float(avg_latency_ms) / 1000.0, 3) if avg_latency_ms is not None else None

    # Real average calibrated confidence from assistant turns
    trust_res = await db.execute(
        select(func.avg(ChatMessage.calibrated_trust_score)).where(
            ChatMessage.calibrated_trust_score.isnot(None)
        )
    )
    avg_trust = trust_res.scalar_one()
    avg_score = round(float(avg_trust) * 100, 1) if avg_trust is not None else None

    return MyActivitySummary(
        total_scans=total_searches,
        scans_by_status={"completed": total_searches},
        total_findings=total_docs,
        findings_by_severity={"knowledge_docs": total_docs},
        average_scan_duration_seconds=avg_duration,
        average_brs_score=avg_score,
        recent_scans=[],
    )


async def get_team_activity(db: AsyncSession) -> TeamActivitySummary:
    search_count_res = await db.execute(select(func.count(SearchAnalyticsLog.id)))
    total_searches = search_count_res.scalar_one() or 0

    trust_res = await db.execute(
        select(func.avg(ChatMessage.calibrated_trust_score)).where(
            ChatMessage.calibrated_trust_score.isnot(None)
        )
    )
    avg_trust = trust_res.scalar_one()
    avg_score = round(float(avg_trust) * 100, 1) if avg_trust is not None else None

    members_res = await db.execute(
        select(User.id, User.email, User.full_name).limit(10)
    )
    members = [
        TeamMemberActivity(
            user_id=u_id,
            email=email,
            full_name=full_name,
            total_scans=0,
            total_findings=0,
            average_brs_score=avg_score,
        )
        for u_id, email, full_name in members_res.all()
    ]

    return TeamActivitySummary(
        total_scans=total_searches,
        total_findings=0,
        members=members,
    )
