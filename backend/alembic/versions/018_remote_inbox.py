"""018_remote_inbox_and_document_session

Revision ID: 018_remote_inbox_and_document_session
Revises: 017_p2_bank_reconciliation
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '018_remote_inbox'
down_revision: Union[str, None] = '017_p2_bank_reconciliation'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. inbox_messages
    op.create_table(
        'inbox_messages',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_message_id', sa.String(128), nullable=False),
        sa.Column('sender_phone', sa.String(32), nullable=False),
        sa.Column('sender_name', sa.String(128), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='RECEIVED'),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('organization_id', 'external_message_id', name='uq_inbox_message_external_id')
    )
    op.create_index('ix_inbox_messages_org', 'inbox_messages', ['organization_id'])
    op.create_index('ix_inbox_messages_phone', 'inbox_messages', ['sender_phone'])
    op.create_index('ix_inbox_messages_org_status', 'inbox_messages', ['organization_id', 'status'])

    # 2. inbox_attachments
    op.create_table(
        'inbox_attachments',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('inbox_message_id', sa.UUID(), sa.ForeignKey('inbox_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(128), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('file_hash_sha256', sa.String(64), nullable=False),
        sa.Column('storage_path', sa.String(512), nullable=False),
        sa.Column('document_id', sa.UUID(), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_inbox_attachments_msg', 'inbox_attachments', ['inbox_message_id'])
    op.create_index('ix_inbox_attachments_org', 'inbox_attachments', ['organization_id'])
    op.create_index('ix_inbox_attachments_hash', 'inbox_attachments', ['file_hash_sha256'])

    # 3. document_sessions
    op.create_table(
        'document_sessions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_code', sa.String(64), nullable=False, unique=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('inbox_message_id', sa.UUID(), sa.ForeignKey('inbox_messages.id', ondelete='SET NULL'), nullable=True),
        sa.Column('document_id', sa.UUID(), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('transaction_id', sa.UUID(), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_document_sessions_org', 'document_sessions', ['organization_id'])
    op.create_index('ix_document_sessions_status', 'document_sessions', ['status'])

    # 4. match_evidences
    op.create_table(
        'match_evidences',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('document_session_id', sa.UUID(), sa.ForeignKey('document_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_type', sa.String(50), nullable=False),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('score', sa.Numeric(5, 4), nullable=False, server_default='1.0000'),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_match_evidences_session', 'match_evidences', ['document_session_id'])
    op.create_index('ix_match_evidences_org', 'match_evidences', ['organization_id'])


def downgrade() -> None:
    op.drop_table('match_evidences')
    op.drop_table('document_sessions')
    op.drop_table('inbox_attachments')
    op.drop_table('inbox_messages')
