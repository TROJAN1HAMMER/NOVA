"""
NOVA — Repository Model
Represents a source code repository target for security scanning.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RepoProviderType

if TYPE_CHECKING:
    from app.models.scan_job import ScanJob
    from app.models.user import User

class Repository(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "repositories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    provider: Mapped[RepoProviderType] = mapped_column(
        Enum(
            RepoProviderType,
            name="repo_provider_type",
            native_enum=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RepoProviderType.UPLOAD,
    )
    default_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scheduled_scan_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    owner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[owner_id])
