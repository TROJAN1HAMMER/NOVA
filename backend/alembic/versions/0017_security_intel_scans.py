"""security_intel_scans migration

Revision ID: 0017_security_intel_scans
Revises: 0016_security_posture_snapshots
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0017_security_intel_scans'
down_revision = '0016_security_posture_snapshots'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'security_intel_scans' not in tables:
        op.create_table(
            'security_intel_scans',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('project_name', sa.String(length=255), nullable=False),
            sa.Column('source_type', sa.String(length=32), nullable=False),
            sa.Column('source_identifier', sa.String(length=1024), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='QUEUED'),
            sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('stage', sa.String(length=128), nullable=False, server_default='QUEUED'),
            sa.Column('workspace_path', sa.String(length=1024), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('posture_score', sa.Float(), nullable=True),
            sa.Column('posture_rating', sa.String(length=32), nullable=True),
            sa.Column('delta_score', sa.Float(), nullable=True),
            sa.Column('trend_direction', sa.String(length=32), nullable=False, server_default='UNCHANGED'),
            sa.Column('result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index(op.f('ix_security_intel_scans_project_name'), 'security_intel_scans', ['project_name'], unique=False)
        op.create_index(op.f('ix_security_intel_scans_source_type'), 'security_intel_scans', ['source_type'], unique=False)
        op.create_index(op.f('ix_security_intel_scans_status'), 'security_intel_scans', ['status'], unique=False)
        op.create_index(op.f('ix_security_intel_scans_owner_id'), 'security_intel_scans', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_security_intel_scans_owner_id'), table_name='security_intel_scans')
    op.drop_index(op.f('ix_security_intel_scans_status'), table_name='security_intel_scans')
    op.drop_index(op.f('ix_security_intel_scans_source_type'), table_name='security_intel_scans')
    op.drop_index(op.f('ix_security_intel_scans_project_name'), table_name='security_intel_scans')
    op.drop_table('security_intel_scans')
