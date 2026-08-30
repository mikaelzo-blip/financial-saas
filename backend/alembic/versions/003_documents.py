"""003_documents

Revision ID: 003_documents
Revises: 002_projects
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003_documents'
down_revision: Union[str, None] = '002_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create document_type enum
    document_type_enum = sa.Enum(
        'INVOICE', 'RECEIPT', 'KUITANSI', 'NOTA', 'SURAT_JALAN', 'SPK',
        'KONTRAK', 'BAST', 'PROGRESS_CLAIM', 'REKENING_KORAN', 'BUKTI_POTONG_PPH',
        'FAKTUR_PAJAK', 'SLIP_GAJI', 'PROPOSAL', 'PURCHASE_ORDER', 'PAYMENT_VOUCHER',
        'PETTY_CASH_VOUCHER', 'REIMBURSEMENT_FORM', 'TAX_INVOICE', 'LOAN_AGREEMENT',
        'OTHER',
        name='document_type'
    )

    # 2. Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('document_code', sa.String(length=50), nullable=False),
        sa.Column('document_type', document_type_enum, nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('source_channel', sa.String(length=50), server_default='WEB_UPLOAD', nullable=False),
        sa.Column('source_metadata', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('raw_extraction', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_documents_created_by_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_documents_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
        sa.UniqueConstraint('organization_id', 'document_code', name='uq_documents_org_document_code'),
        sa.UniqueConstraint('organization_id', 'file_hash', name='uq_documents_org_file_hash')
    )
    op.create_index(op.f('ix_documents_document_code'), 'documents', ['document_code'], unique=False)
    op.create_index(op.f('ix_documents_file_hash'), 'documents', ['file_hash'], unique=False)
    op.create_index(op.f('ix_documents_organization_id'), 'documents', ['organization_id'], unique=False)

    # 3. Create project_document_links table
    op.create_table(
        'project_document_links',
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_project_document_links_document_id_documents'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_document_links_project_id_projects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('project_id', 'document_id', name=op.f('pk_project_document_links'))
    )

    # 4. Create transaction_document_links table
    op.create_table(
        'transaction_document_links',
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_transaction_document_links_document_id_documents'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('transaction_id', 'document_id', name=op.f('pk_transaction_document_links'))
    )


def downgrade() -> None:
    op.drop_table('transaction_document_links')
    op.drop_table('project_document_links')
    op.drop_table('documents')
    sa.Enum(name='document_type').drop(op.get_bind(), checkfirst=True)
