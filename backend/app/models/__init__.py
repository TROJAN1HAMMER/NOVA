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
    "KnowledgeDocument",
    "KnowledgeChunk",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "SearchAnalyticsLog",
    "Feedback",
]
