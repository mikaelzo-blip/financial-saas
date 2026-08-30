"""Add tenant-scoped advisory insight cache and conversations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '011_ai_insights'
down_revision = '010_whatsapp_integration'
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table('ai_insight_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('insight_type', sa.String(32), nullable=False),
        sa.Column('period_key', sa.String(64), nullable=False),
        sa.Column('prompt_payload_hash', sa.String(64), nullable=False),
        sa.Column('response_json', json_type, nullable=False),
        sa.Column('provider_used', sa.String(32), nullable=False),
        sa.Column('tokens_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('latency_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('idx_ai_cache_lookup', 'ai_insight_logs', ['organization_id', 'prompt_payload_hash', 'expires_at'])
    op.create_index('idx_ai_insight_org_type', 'ai_insight_logs', ['organization_id', 'insight_type', 'created_at'])
    op.create_table('ai_conversation_sessions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('session_title', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('idx_ai_session_user', 'ai_conversation_sessions', ['user_id', 'updated_at'])
    op.create_index('idx_ai_session_org', 'ai_conversation_sessions', ['organization_id'])
    op.create_table('ai_conversation_messages',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('session_id', sa.UUID(), sa.ForeignKey('ai_conversation_sessions.id'), nullable=False),
        sa.Column('sender', sa.String(16), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('context_intent', sa.String(32)),
        sa.Column('source_references', json_type),
        sa.Column('tokens_used', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('idx_ai_message_session', 'ai_conversation_messages', ['session_id', 'created_at'])


def downgrade():
    op.drop_table('ai_conversation_messages')
    op.drop_table('ai_conversation_sessions')
    op.drop_table('ai_insight_logs')
