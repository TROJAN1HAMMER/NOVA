"""report generation — async status lifecycle + S3/MinIO storage

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-17

Widens `reports.report_type` from String(16) to String(32) — it already
silently exceeded 16 characters in practice ("compliance_report" is 17
chars; this had never been caught because no live Postgres write had been
exercised against this column yet).

Adds:
  - `status` (pending|generating|completed|failed) — report_tasks.py
    creates a row in "pending" status as soon as a scan finishes
    aggregating, before any file has been rendered, and updates it in
    place as generation proceeds. Backfilled to "completed" for any
    pre-existing rows, since every row that existed before this migration
    necessarily already has a file on disk.
  - `storage_backend` (local|s3) + `storage_key` — see
    app/services/reports/storage.py. Backfilled to "local" for existing
    rows, storage_key left null (local reads go through file_path).
  - `error_message` — populated on a failed generation attempt.
  - `file_path` becomes nullable (a pending/generating row has no file yet).
  - A unique constraint on (scan_job_id, report_type) so retrying a failed
    generation updates the existing row rather than the previous
    insert-only `ReportRepository.create()` accumulating duplicates.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("reports", "report_type", type_=sa.String(length=32), existing_type=sa.String(length=16))
    op.alter_column("reports", "file_path", existing_type=sa.String(length=1024), nullable=True)

    op.add_column(
        "reports",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="completed"),
    )
    op.add_column(
        "reports",
        sa.Column("storage_backend", sa.String(length=16), nullable=False, server_default="local"),
    )
    op.add_column("reports", sa.Column("storage_key", sa.String(length=1024), nullable=True))
    op.add_column("reports", sa.Column("error_message", sa.Text(), nullable=True))

    # The server_default above is only for backfilling existing rows during
    # this migration; new rows always specify status/storage_backend
    # explicitly (report_repository.py). `existing_server_default` must be
    # passed here (not left to its own None default) or Alembic sees no
    # change from its own assumed prior state and silently skips emitting
    # the DROP DEFAULT DDL entirely.
    op.alter_column("reports", "status", server_default=None, existing_server_default="completed")
    op.alter_column("reports", "storage_backend", server_default=None, existing_server_default="local")

    op.create_unique_constraint(
        "uq_reports_scan_job_id_report_type", "reports", ["scan_job_id", "report_type"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_reports_scan_job_id_report_type", "reports", type_="unique")
    op.drop_column("reports", "error_message")
    op.drop_column("reports", "storage_key")
    op.drop_column("reports", "storage_backend")
    op.drop_column("reports", "status")
    op.alter_column("reports", "file_path", existing_type=sa.String(length=1024), nullable=False)
    op.alter_column("reports", "report_type", type_=sa.String(length=16), existing_type=sa.String(length=32))
