"""
NOVA — Audit Log Model
Append-only: rows are created once and never updated, so this uses
`UUIDPrimaryKeyMixin` alone rather than `TimestampMixin` — an `updated_at`
column would imply rows can change, which they shouldn't for an audit
trail. `created_at` is the single source of truth for when the event
happened.

Written by `app/services/audit/audit_logger.py`, which every entry point
that should be audited calls directly (auth events, RBAC permission
denials, admin actions) — see that module's docstring for the exact list
and the reasoning for why it's a deliberately curated subset of all
requests, not every request.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    # SET NULL (not CASCADE) — deleting a user must never delete the
    # historical record that they existed and did things; `user_email` is
    # a denormalized snapshot for exactly this reason, so the log stays
    # meaningful even after user_id goes null.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # e.g. "login", "login.failed", "register", "token.refresh",
    # "permission.denied", "user.role_changed", "user.deactivated"
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")  # success | failure | denied
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
