"""
NOVA — Repository Dependency Injection
Wires repositories to request-scoped `AsyncSession`.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.user_repository import UserRepository


def get_report_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> ReportRepository:
    return ReportRepository(db)


def get_user_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_audit_log_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> AuditLogRepository:
    return AuditLogRepository(db)


def get_knowledge_document_repository(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> KnowledgeDocumentRepository:
    return KnowledgeDocumentRepository(db)
