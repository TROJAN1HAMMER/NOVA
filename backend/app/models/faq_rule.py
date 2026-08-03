import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class FAQRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "faq_rules"

    keyword: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_query_cluster: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_by: Mapped[Optional["User"]] = relationship()
