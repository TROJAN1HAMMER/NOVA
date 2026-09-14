"""architecture_intelligence migration

Revision ID: 0018_architecture_intelligence
Revises: 0017_security_intel_scans
Create Date: 2026-09-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0018_architecture_intelligence'
down_revision = '0017_security_intel_scans'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. architecture_snapshots
    if 'architecture_snapshots' not in tables:
        op.create_table(
            'architecture_snapshots',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('scan_id', sa.String(length=64), nullable=True),
            sa.Column('project_name', sa.String(length=255), nullable=False, server_default='Default Project'),
            sa.Column('target_scope', sa.String(length=512), nullable=False, server_default='.'),
            sa.Column('commit_hash', sa.String(length=64), nullable=True),
            sa.Column('total_components', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_dependencies', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('circular_dependency_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('avg_instability', sa.Float(), nullable=True),
            sa.Column('hotspot_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('summary_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        )
        op.create_index(op.f('ix_architecture_snapshots_scan_id'), 'architecture_snapshots', ['scan_id'], unique=False)
        op.create_index(op.f('ix_architecture_snapshots_project_name'), 'architecture_snapshots', ['project_name'], unique=False)
        op.create_index(op.f('ix_architecture_snapshots_target_scope'), 'architecture_snapshots', ['target_scope'], unique=False)
        op.create_index(op.f('ix_architecture_snapshots_owner_id'), 'architecture_snapshots', ['owner_id'], unique=False)

    # 2. architecture_components
    if 'architecture_components' not in tables:
        op.create_table(
            'architecture_components',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('architecture_snapshots.id', ondelete='CASCADE'), nullable=False),
            sa.Column('component_id', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('component_type', sa.String(length=64), nullable=False),
            sa.Column('file_path', sa.String(length=1024), nullable=False),
            sa.Column('line_number', sa.Integer(), nullable=True),
            sa.Column('fan_in', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('fan_out', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('afferent_coupling', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('efferent_coupling', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('instability', sa.Float(), nullable=True),
            sa.Column('cohesion_score', sa.Float(), nullable=True),
            sa.Column('cohesion_status', sa.String(length=64), nullable=True),
            sa.Column('is_god_candidate', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_hotspot', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('hotspot_score', sa.Float(), nullable=True),
            sa.Column('hotspot_reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('blast_radius_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.create_index(op.f('ix_architecture_components_snapshot_id'), 'architecture_components', ['snapshot_id'], unique=False)
        op.create_index(op.f('ix_architecture_components_component_id'), 'architecture_components', ['component_id'], unique=False)
        op.create_index(op.f('ix_architecture_components_name'), 'architecture_components', ['name'], unique=False)
        op.create_index(op.f('ix_architecture_components_component_type'), 'architecture_components', ['component_type'], unique=False)
        op.create_index(op.f('ix_architecture_components_is_hotspot'), 'architecture_components', ['is_hotspot'], unique=False)

    # 3. architecture_dependencies
    if 'architecture_dependencies' not in tables:
        op.create_table(
            'architecture_dependencies',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('architecture_snapshots.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_component_id', sa.String(length=255), nullable=False),
            sa.Column('target_component_id', sa.String(length=255), nullable=False),
            sa.Column('relation_type', sa.String(length=64), nullable=False),
            sa.Column('evidence', sa.Text(), nullable=True),
            sa.Column('line_number', sa.Integer(), nullable=True),
            sa.Column('file_path', sa.String(length=1024), nullable=True),
            sa.Column('is_circular', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        )
        op.create_index(op.f('ix_architecture_dependencies_snapshot_id'), 'architecture_dependencies', ['snapshot_id'], unique=False)
        op.create_index(op.f('ix_architecture_dependencies_source_component_id'), 'architecture_dependencies', ['source_component_id'], unique=False)
        op.create_index(op.f('ix_architecture_dependencies_target_component_id'), 'architecture_dependencies', ['target_component_id'], unique=False)
        op.create_index(op.f('ix_architecture_dependencies_relation_type'), 'architecture_dependencies', ['relation_type'], unique=False)

    # 4. architecture_traceability_links
    if 'architecture_traceability_links' not in tables:
        op.create_table(
            'architecture_traceability_links',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('architecture_snapshots.id', ondelete='CASCADE'), nullable=False),
            sa.Column('component_id', sa.String(length=255), nullable=False),
            sa.Column('requirement_doc_id', sa.String(length=255), nullable=True),
            sa.Column('knowledge_chunk_id', sa.String(length=255), nullable=True),
            sa.Column('graph_entity_id', sa.String(length=255), nullable=True),
            sa.Column('control_id', sa.String(length=255), nullable=True),
            sa.Column('finding_id', sa.String(length=255), nullable=True),
            sa.Column('risk_scenario_id', sa.String(length=255), nullable=True),
            sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.create_index(op.f('ix_architecture_traceability_links_snapshot_id'), 'architecture_traceability_links', ['snapshot_id'], unique=False)
        op.create_index(op.f('ix_architecture_traceability_links_component_id'), 'architecture_traceability_links', ['component_id'], unique=False)


def downgrade() -> None:
    op.drop_table('architecture_traceability_links')
    op.drop_table('architecture_dependencies')
    op.drop_table('architecture_components')
    op.drop_table('architecture_snapshots')
