"""distributed scan orchestrator — repositories, scan_jobs, scan_results

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-07-15

Supersedes the flat `scans` table with `repositories` (scan target) +
`scan_jobs` (queue/lifecycle: status, priority, retries, timeout,
heartbeat, progress) + `scan_results` (computed BRS/zero-day outcome,
1:1 with a job). `findings`/`reports` move their FK from `scans.id` to
`scan_jobs.id`.

DATA-DESTRUCTIVE: this drops `scans`, `findings`, and `reports` and
recreates them rather than attempting in-place `ALTER TABLE` migrations.
That's a deliberate call, not an oversight — no live Postgres instance has
been available in this environment at any point in this project (confirmed
repeatedly — no network access to even `pip install` a DB driver to test
against one), so migration 0001 has never actually run against real data.
If you've since applied 0001 to a real database with scans you care about,
back it up before running this — `pg_dump` the `scans`/`findings`/`reports`
tables, or write a data-migration step here to backfill `repositories` and
`scan_jobs` from the old `scans` rows before dropping them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False on all three: each is explicitly .create()'d once
# below (checkfirst=True) and then reused as a column type in
# create_table() calls further down. Without create_type=False, the
# column's own DDL event *also* tries to create the enum type when its
# owning table is created, regardless of the explicit call's
# checkfirst=True — Postgres then rejects the second CREATE TYPE with
# "already exists" (confirmed by actually running this migration against
# a real Postgres instance for the first time in this project's history —
# this bug was latent and undetected until then).
scan_job_status_enum = postgresql.ENUM(
    "queued", "running", "completed", "failed", "cancelled", name="scan_job_status", create_type=False
)
scan_job_priority_enum = postgresql.ENUM(
    "low", "normal", "high", "critical", name="scan_job_priority", create_type=False
)
repo_provider_enum = postgresql.ENUM(
    "upload", "github", "gitlab", "bitbucket", name="repo_provider_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    scan_job_status_enum.create(bind, checkfirst=True)
    scan_job_priority_enum.create(bind, checkfirst=True)
    repo_provider_enum.create(bind, checkfirst=True)

    # Drop children before parent (FK order), then the old parent table.
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_reports_scan_id", table_name="reports")
    op.drop_table("reports")
    op.drop_table("scans")

    op.create_table(
        "repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("provider", repo_provider_enum, nullable=False, server_default="upload"),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "scan_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", scan_job_status_enum, nullable=False, server_default="queued"),
        sa.Column("priority", scan_job_priority_enum, nullable=False, server_default="normal"),
        sa.Column("ref", sa.String(length=255), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_scan_jobs_repository_id", "scan_jobs", ["repository_id"])
    op.create_index("ix_scan_jobs_status", "scan_jobs", ["status"])
    op.create_index("ix_scan_jobs_priority", "scan_jobs", ["priority"])
    op.create_index("ix_scan_jobs_celery_task_id", "scan_jobs", ["celery_task_id"])

    op.create_table(
        "scan_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brs_score", sa.Float(), nullable=True),
        sa.Column("brs_risk_level", sa.String(length=16), nullable=True),
        sa.Column("zero_day_risk_score", sa.Float(), nullable=True),
        sa.Column("zero_day_risk_level", sa.String(length=16), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("compliance_summary", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_scan_results_scan_job_id", "scan_results", ["scan_job_id"], unique=True)

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("cvss", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brs_risk_level", sa.String(length=16), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("package", sa.String(length=255), nullable=True),
        sa.Column("package_version", sa.String(length=64), nullable=True),
        sa.Column("cve", sa.String(length=32), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_business_impact", sa.Text(), nullable=True),
        sa.Column("ai_remediation", sa.Text(), nullable=True),
        sa.Column("rbi_clause", sa.String(length=64), nullable=True),
        sa.Column("pci_clause", sa.String(length=64), nullable=True),
        sa.Column("swift_clause", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_findings_scan_job_id", "findings", ["scan_job_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scan_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
    )
    op.create_index("ix_reports_scan_job_id", "reports", ["scan_job_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_scan_job_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_scan_job_id", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_scan_results_scan_job_id", table_name="scan_results")
    op.drop_table("scan_results")

    op.drop_index("ix_scan_jobs_celery_task_id", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_priority", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_status", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_repository_id", table_name="scan_jobs")
    op.drop_table("scan_jobs")

    op.drop_table("repositories")

    bind = op.get_bind()
    repo_provider_enum.drop(bind, checkfirst=True)
    scan_job_priority_enum.drop(bind, checkfirst=True)
    scan_job_status_enum.drop(bind, checkfirst=True)

    # Restore the 0001 shape (scans / findings / reports).
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("repo_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("total_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brs_score", sa.Float(), nullable=True),
        sa.Column("brs_risk_level", sa.String(length=16), nullable=True),
        sa.Column("zero_day_risk_score", sa.Float(), nullable=True),
        sa.Column("zero_day_risk_level", sa.String(length=16), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("cvss", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brs", sa.Float(), nullable=False, server_default="0"),
        sa.Column("brs_risk_level", sa.String(length=16), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("package", sa.String(length=255), nullable=True),
        sa.Column("package_version", sa.String(length=64), nullable=True),
        sa.Column("cve", sa.String(length=32), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_business_impact", sa.Text(), nullable=True),
        sa.Column("ai_remediation", sa.Text(), nullable=True),
        sa.Column("rbi_clause", sa.String(length=64), nullable=True),
        sa.Column("pci_clause", sa.String(length=64), nullable=True),
        sa.Column("swift_clause", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
    )
    op.create_index("ix_reports_scan_id", "reports", ["scan_id"])
