"""knowledge base: pgvector extension + documents/chunks tables

Revision ID: e3f4a5b6c7d8
Revises: d1e2f3a4b5c6
Create Date: 2026-07-19

RAG Milestone 1 (knowledge base infrastructure only — no AI integration
yet, see app/services/knowledge_base/). Enables the pgvector extension on
the existing Postgres instance (requires the pgvector/pgvector:pg16
image, see docker-compose.yml) and adds two tables:

  knowledge_documents — one row per uploaded document, metadata +
    ingestion status (pending -> processing -> indexed | failed).
  knowledge_chunks — the semantic chunks extracted from each document,
    each carrying its own embedding vector (384-dim, matching
    BAAI/bge-small-en-v1.5 — see app/config.py's knowledge_embedding_dim).

An HNSW index is used instead of IVFFlat for the vector similarity index:
IVFFlat's cluster centroids are trained from existing data at index-build
time, so building one against an empty table (as this migration always
does, since no documents exist yet) produces a degenerate, low-quality
index. HNSW builds incrementally and needs no pre-existing data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("document_type", sa.String(16), nullable=False),
        sa.Column("version", sa.String(32), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("author", sa.String(256), nullable=True),
        sa.Column("tags", sa.dialects.postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "uploaded_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_knowledge_documents_content_hash", "knowledge_documents", ["content_hash"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index("ix_knowledge_documents_document_type", "knowledge_documents", ["document_type"])
    op.create_index(
        "ix_knowledge_documents_tags_gin", "knowledge_documents", ["tags"], postgresql_using="gin"
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("heading", sa.String(512), nullable=True),
        sa.Column("section_path", sa.String(1024), nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_embedding_hnsw", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("ix_knowledge_documents_tags_gin", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_document_type", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_content_hash", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    # Extension deliberately left installed on downgrade — dropping it is
    # unnecessary risk if anything else ever comes to depend on it, and
    # `CREATE EXTENSION IF NOT EXISTS` on a future re-upgrade is a no-op
    # either way.
