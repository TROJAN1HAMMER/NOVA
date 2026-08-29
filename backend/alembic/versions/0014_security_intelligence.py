"""Security Intelligence Schema Migration

Revision ID: 0014_security_intelligence
Revises: 0013_aekof_core_schema
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0014_security_intelligence'
down_revision = '0013_aekof_core_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create security_intel_assets
    op.create_table(
        'security_intel_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_name', sa.String(255), nullable=False),
        sa.Column('asset_type', sa.String(64), nullable=False),
        sa.Column('criticality', sa.String(32), nullable=False, server_default='MEDIUM'),
        sa.Column('owner', sa.String(128), nullable=True),
        sa.Column('location', sa.String(1024), nullable=True),
        sa.Column('attributes', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sec_intel_asset_name', 'security_intel_assets', ['asset_name'])
    op.create_index('idx_sec_intel_asset_type', 'security_intel_assets', ['asset_type'])

    # 2. Create security_intel_observations
    op.create_table(
        'security_intel_observations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('security_intel_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('observation_type', sa.String(64), nullable=False),
        sa.Column('location', sa.String(1024), nullable=False),
        sa.Column('attributes', postgresql.JSONB(), nullable=True),
        sa.Column('evidence_span', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.90'),
        sa.Column('provenance', sa.String(128), nullable=False, server_default='code_ast_fact'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sec_intel_obs_asset', 'security_intel_observations', ['asset_id'])
    op.create_index('idx_sec_intel_obs_type', 'security_intel_observations', ['observation_type'])

    # 3. Create security_intel_controls
    op.create_table(
        'security_intel_controls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('security_intel_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('control_type', sa.String(64), nullable=False),
        sa.Column('scope', sa.String(512), nullable=False),
        sa.Column('state', sa.String(32), nullable=False, server_default='UNKNOWN'),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.85'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sec_intel_ctrl_asset', 'security_intel_controls', ['asset_id'])
    op.create_index('idx_sec_intel_ctrl_type', 'security_intel_controls', ['control_type'])

    # 4. Create security_intel_risk_scenarios
    op.create_table(
        'security_intel_risk_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('security_intel_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scenario_type', sa.String(128), nullable=False),
        sa.Column('trust_boundary_crossed', sa.String(128), nullable=False),
        sa.Column('attack_path', postgresql.JSONB(), nullable=False),
        sa.Column('exposure_signal', sa.String(255), nullable=False),
        sa.Column('control_status', sa.String(255), nullable=False),
        sa.Column('potential_impact', sa.Text(), nullable=False),
        sa.Column('verification_state', sa.String(32), nullable=False, server_default='CANDIDATE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sec_intel_scenario_asset', 'security_intel_risk_scenarios', ['asset_id'])

    # 5. Create security_intel_assessments
    op.create_table(
        'security_intel_assessments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('security_intel_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('risk_type', sa.String(128), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.90'),
        sa.Column('affected_scope', sa.String(512), nullable=False),
        sa.Column('evidence_chain', postgresql.JSONB(), nullable=False),
        sa.Column('attack_path', postgresql.JSONB(), nullable=False),
        sa.Column('controls_evaluated', postgresql.JSONB(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('remediation', sa.Text(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='OPEN'),
        sa.Column('commit_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sec_intel_assess_asset', 'security_intel_assessments', ['asset_id'])
    op.create_index('idx_sec_intel_assess_risk', 'security_intel_assessments', ['risk_type'])
    op.create_index('idx_sec_intel_assess_severity', 'security_intel_assessments', ['severity'])


def downgrade() -> None:
    op.drop_table('security_intel_assessments')
    op.drop_table('security_intel_risk_scenarios')
    op.drop_table('security_intel_controls')
    op.drop_table('security_intel_observations')
    op.drop_table('security_intel_assets')
