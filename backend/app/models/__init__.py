"""
AEKOF — Platform ORM Models
Import every model module here so `Base.metadata` (and Alembic) sees the full schema.
"""

from app.models.user import User
from app.models.report import Report
from app.models.audit_log import AuditLog
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.faq_rule import FAQRule
from app.models.system_setting import SystemSetting
from app.models.repository import Repository
from app.models.scan_job import ScanJob
from app.models.scan_result import ScanResult
from app.models.finding import Finding
from app.models.risk_config import BusinessModule, RiskFactorWeight
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeChunk,
    KnowledgeEntity,
    KnowledgeRelation,
    SearchAnalyticsLog,
    Feedback,
)

__all__ = [
    "User",
    "Report",
    "AuditLog",
    "ChatSession",
    "ChatMessage",
    "FAQRule",
    "SystemSetting",
    "Repository",
    "ScanJob",
    "ScanResult",
    "Finding",
    "BusinessModule",
    "RiskFactorWeight",
    "KnowledgeDocument",
    "KnowledgeChunk",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "SearchAnalyticsLog",
    "Feedback",
]
