"""aggregation layer — finding enrichment columns

Revision ID: c3d4e5f6a7b8
Revises: f1e2d3c4b5a6
Create Date: 2026-07-16

Purely additive: new nullable columns (plus one with a server default) on
the existing `findings` table for the aggregation layer's cross-tool
provenance and CWE/OWASP/MITRE ATT&CK enrichment
(app/services/aggregation/). Unlike 0002, no drop-and-recreate needed —
this doesn't touch any existing column.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "f1e2d3c4b5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("sources", postgresql.JSONB(), nullable=True))
    op.add_column(
        "findings", sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("findings", sa.Column("cwe_id", sa.String(length=32), nullable=True))
    op.add_column("findings", sa.Column("cwe_name", sa.String(length=255), nullable=True))
    op.add_column("findings", sa.Column("owasp_category", sa.String(length=8), nullable=True))
    op.add_column("findings", sa.Column("owasp_name", sa.String(length=255), nullable=True))
    op.add_column("findings", sa.Column("mitre_technique_ids", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "mitre_technique_ids")
    op.drop_column("findings", "owasp_name")
    op.drop_column("findings", "owasp_category")
    op.drop_column("findings", "cwe_name")
    op.drop_column("findings", "cwe_id")
    op.drop_column("findings", "occurrence_count")
    op.drop_column("findings", "sources")
