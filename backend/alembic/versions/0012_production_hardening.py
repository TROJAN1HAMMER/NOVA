"""production hardening: document versioning + search analytics + feedback

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-20

RAG Milestone 5. Three additions:

  1. `knowledge_documents.document_group_id` / `.is_latest` — version-chain
     support (app/models/knowledge.py's docstring explains the scheme).
     Existing rows are backfilled to be their own group's (only) version:
     `document_group_id = id`, `is_latest = true`.
  2. `search_analytics_logs` — persists what was previously only an
     ephemeral structlog line per search/chat/ask call.
  3. `feedback_entries` — user-submitted relevance signal on a RAG output.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("document_group_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # Backfill: every existing document becomes its own single-version group.
    op.execute("UPDATE knowledge_documents SET document_group_id = id WHERE document_group_id IS NULL")
    op.alter_column("knowledge_documents", "document_group_id", nullable=False)
    op.create_index("ix_knowledge_documents_document_group_id", "knowledge_documents", ["document_group_id"])

    op.create_table(
        "search_analytics_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature", sa.String(32), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("top_score", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_analytics_logs_feature", "search_analytics_logs", ["feature"])
    op.create_index("ix_search_analytics_logs_created_at", "search_analytics_logs", ["created_at"])

    op.create_table(
        "feedback_entries",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("feature", sa.String(32), nullable=False),
        sa.Column("reference_id", sa.String(255), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_entries_feature", "feedback_entries", ["feature"])
    op.create_index("ix_feedback_entries_created_at", "feedback_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_entries_created_at", table_name="feedback_entries")
    op.drop_index("ix_feedback_entries_feature", table_name="feedback_entries")
    op.drop_table("feedback_entries")

    op.drop_index("ix_search_analytics_logs_created_at", table_name="search_analytics_logs")
    op.drop_index("ix_search_analytics_logs_feature", table_name="search_analytics_logs")
    op.drop_table("search_analytics_logs")

    op.drop_index("ix_knowledge_documents_document_group_id", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "is_latest")
    op.drop_column("knowledge_documents", "document_group_id")
