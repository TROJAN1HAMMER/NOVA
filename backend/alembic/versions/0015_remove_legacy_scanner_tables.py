"""Remove Legacy Scanner Tables Migration

Revision ID: 0015_remove_legacy_scanner_tables
Revises: 0014_security_intelligence
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0015_remove_legacy_scanner_tables'
down_revision = '0014_security_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safely drop obsolete legacy scanner tables if they exist
    op.execute("DROP TABLE IF EXISTS findings CASCADE;")
    op.execute("DROP TABLE IF EXISTS scan_results CASCADE;")
    op.execute("DROP TABLE IF EXISTS scan_jobs CASCADE;")


def downgrade() -> None:
    # Re-create lightweight empty table structure for downgrade compatibility if required
    op.create_table(
        'scan_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_table(
        'findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
