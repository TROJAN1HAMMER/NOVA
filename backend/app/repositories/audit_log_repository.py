"""
NOVA — Audit Log Repository
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: Optional[uuid.UUID],
        user_email: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def list(
        self,
        *,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        query = select(AuditLog)
        query = self._apply_filters(query, user_id=user_id, action=action, status=status, since=since, until=until)
        query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> int:
        query = select(func.count(AuditLog.id))
        query = self._apply_filters(query, user_id=user_id, action=action, status=status, since=since, until=until)
        result = await self.db.execute(query)
        return result.scalar_one()

    @staticmethod
    def _apply_filters(
        query,
        *,
        user_id: Optional[uuid.UUID],
        action: Optional[str],
        status: Optional[str],
        since: Optional[datetime],
        until: Optional[datetime],
    ):
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if status is not None:
            query = query.where(AuditLog.status == status)
        if since is not None:
            query = query.where(AuditLog.created_at >= since)
        if until is not None:
            query = query.where(AuditLog.created_at <= until)
        return query
