"""enterprise auth — RBAC roles, SSO-ready user fields, audit log

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-17

Replaces `users.role` (a free-form `String(32)` defaulting to the now-
retired `"analyst"`) with a Postgres-native `user_role` enum matching the
5 fixed RBAC roles in `app.models.enums.UserRole` — see
`app/auth/permissions.py` for what each role can do.

DATA-DESTRUCTIVE on the `role` column specifically (drop + re-add rather
than an `ALTER COLUMN ... USING` cast): no live Postgres instance has ever
been exercised against this schema at any point in this project (same
situation migration 0002 documented), so there is no real `role` data to
preserve, and "analyst" isn't a member of the new enum anyway — a USING
cast would need to invent a mapping for a value that's being retired, not
preserve one that still means something.

Also adds:
  - `hashed_password` becomes nullable — SSO-provisioned users
    (OAuth2/SAML/LDAP) authenticate via their identity provider and never
    have a local password.
  - `auth_provider` (local|oauth2|saml|ldap) + `external_subject` — see
    `app/models/user.py`'s docstring. A partial unique index enforces
    uniqueness only where `external_subject is not null`, so any number
    of local users can all have it null.
  - `audit_logs` — see `app/models/audit_log.py`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False on both: each is explicitly .create()'d once below
# (checkfirst=True) and then reused as a column type in add_column()
# calls further down. Without this, the column's own DDL event also tries
# to create the enum type when the column is added, and Postgres rejects
# the second CREATE TYPE with "already exists" — see migration 0002's
# scan_job_status_enum for the same fix, applied there after actually
# running these migrations against a real Postgres surfaced the bug.
user_role_enum = postgresql.ENUM(
    "admin", "auditor", "developer", "security_engineer", "read_only", name="user_role", create_type=False
)
auth_provider_enum = postgresql.ENUM(
    "local", "oauth2", "saml", "ldap", name="auth_provider", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)
    auth_provider_enum.create(bind, checkfirst=True)

    op.drop_column("users", "role")
    op.add_column(
        "users",
        sa.Column("role", user_role_enum, nullable=False, server_default="read_only"),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)

    op.add_column(
        "users",
        sa.Column("auth_provider", auth_provider_enum, nullable=False, server_default="local"),
    )
    op.add_column("users", sa.Column("external_subject", sa.String(length=512), nullable=True))
    op.create_index(
        "uq_users_auth_provider_external_subject",
        "users",
        ["auth_provider", "external_subject"],
        unique=True,
        postgresql_where=sa.text("external_subject IS NOT NULL"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("uq_users_auth_provider_external_subject", table_name="users")
    op.drop_column("users", "external_subject")
    op.drop_column("users", "auth_provider")

    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)

    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="analyst"),
    )

    auth_provider_enum.drop(op.get_bind(), checkfirst=True)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
