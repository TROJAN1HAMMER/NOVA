"""nightly scheduled scans — repositories.scheduled_scan_enabled

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-18

Adds `repositories.scheduled_scan_enabled` (default false) — see
app/tasks/scheduled_scan_tasks.py's nightly beat task, which re-scans
every repository with this flag set (and a non-null `url`, enforced at
the API layer rather than the DB, since a one-time zip upload has no
re-fetchable source).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column("scheduled_scan_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("repositories", "scheduled_scan_enabled")
