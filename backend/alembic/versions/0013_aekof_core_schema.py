"""AEKOF Core Schema Migration

Revision ID: 0013_aekof_core_schema
Revises: 0012_production_hardening
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0013_aekof_core_schema'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Skip dropping Security Tables so they co-exist with new schema

    # 2. Create chat_sessions
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(256), nullable=False, server_default='New Chat'),
        sa.Column('context_summary', sa.Text(), nullable=True),
        sa.Column('active_entities', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_sessions_user', 'chat_sessions', ['user_id'])

    # 3. Create chat_messages
    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citations', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('confidence_vector', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('calibrated_trust_score', sa.Float(), nullable=True),
        sa.Column('reasoning_trace', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('consensus_matrix', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_messages_session', 'chat_messages', ['session_id'])

    # 4. Create faq_rules
    op.create_table(
        'faq_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('keyword', sa.String(256), unique=True, nullable=False),
        sa.Column('response', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_draft', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source_query_cluster', sa.Text(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_faq_kw', 'faq_rules', ['keyword'])

    # 5. Create system_settings
    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(128), primary_key=True),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # 6. Create GraphRAG tables
    op.create_table(
        'knowledge_entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_name', sa.String(256), nullable=False),
        sa.Column('entity_type', sa.String(64), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    op.create_table(
        'knowledge_relations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relation_type', sa.String(128), nullable=False),
        sa.Column('chunk_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_chunks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # 7. Extend knowledge_documents and search_analytics_logs
    op.add_column('knowledge_documents', sa.Column('health_status', sa.String(16), nullable=False, server_default='active'))
    op.add_column('knowledge_documents', sa.Column('freshness_decay_factor', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('search_analytics_logs', sa.Column('fallback_triggered', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('search_analytics_logs', sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('chat_sessions.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_table('knowledge_relations')
    op.drop_table('knowledge_entities')
    op.drop_table('system_settings')
    op.drop_table('faq_rules')
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
