"""security_intel_posture_snapshots migration

Revision ID: 0016_security_posture_snapshots
Revises: 0015_remove_legacy_scanner_tables
Create Date: 2026-08-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0016_security_posture_snapshots'
down_revision = '0015_remove_legacy_scanner_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'security_intel_posture_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('analysis_run_id', sa.String(length=64), nullable=False),
        sa.Column('target_scope', sa.String(length=512), nullable=False, server_default='.'),
        sa.Column('commit_hash', sa.String(length=64), nullable=True),
        sa.Column('posture_score', sa.Float(), nullable=False),
        sa.Column('posture_rating', sa.String(length=32), nullable=False),
        sa.Column('control_coverage_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_assets_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unresolved_risks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_risks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_risks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_risks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_risks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('verified_fixed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delta_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('trend_direction', sa.String(length=32), nullable=False, server_default='UNCHANGED'),
        sa.Column('risk_evolution_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_security_intel_posture_snapshots_analysis_run_id'), 'security_intel_posture_snapshots', ['analysis_run_id'], unique=False)
    op.create_index(op.f('ix_security_intel_posture_snapshots_target_scope'), 'security_intel_posture_snapshots', ['target_scope'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_security_intel_posture_snapshots_target_scope'), table_name='security_intel_posture_snapshots')
    op.drop_index(op.f('ix_security_intel_posture_snapshots_analysis_run_id'), table_name='security_intel_posture_snapshots')
    op.drop_table('security_intel_posture_snapshots')
