"""scan job archive support

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scan_jobs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The nightly archive sweep filters on "terminal, unarchived, old
    # enough" — this index makes that scan cheap even once the table holds
    # years of history, instead of a full-table scan every night.
    op.create_index(
        "ix_scan_jobs_archived_at_finished_at",
        "scan_jobs",
        ["archived_at", "finished_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_jobs_archived_at_finished_at", table_name="scan_jobs")
    op.drop_column("scan_jobs", "archived_at")
