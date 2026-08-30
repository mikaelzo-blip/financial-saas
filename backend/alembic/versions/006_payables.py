"""006_payables

Revision ID: 006_payables
Revises: 005_journal
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '006_payables'
down_revision: Union[str, None] = '005_journal'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create vendor_bills table
    op.create_table(
        'vendor_bills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('bill_code', sa.String(length=50), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('bill_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='UNPAID', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('total_amount > 0', name='ck_vendor_bills_amount_positive'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_vendor_bills_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_vendor_bills_project_id_projects'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_vendor_bills_transaction_id_transactions'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vendor_id'], ['counterparties.id'], name=op.f('fk_vendor_bills_vendor_id_counterparties'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vendor_bills')),
        sa.UniqueConstraint('organization_id', 'bill_code', name='uq_vendor_bills_org_code')
    )
    op.create_index('ix_vendor_bills_due_date', 'vendor_bills', ['organization_id', 'due_date'], unique=False)
    op.create_index('ix_vendor_bills_org_vendor', 'vendor_bills', ['organization_id', 'vendor_id'], unique=False)
    op.create_index(op.f('ix_vendor_bills_bill_code'), 'vendor_bills', ['bill_code'], unique=False)
    op.create_index(op.f('ix_vendor_bills_organization_id'), 'vendor_bills', ['organization_id'], unique=False)
    op.create_index(op.f('ix_vendor_bills_project_id'), 'vendor_bills', ['project_id'], unique=False)
    op.create_index(op.f('ix_vendor_bills_vendor_id'), 'vendor_bills', ['vendor_id'], unique=False)

    # 2. Create vendor_payment_allocations table
    op.create_table(
        'vendor_payment_allocations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('bill_id', sa.UUID(), nullable=False),
        sa.Column('payment_transaction_id', sa.UUID(), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('allocated_amount > 0', name='ck_vpa_amount_positive'),
        sa.ForeignKeyConstraint(['bill_id'], ['vendor_bills.id'], name=op.f('fk_vendor_payment_allocations_bill_id_vendor_bills'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_transaction_id'], ['transactions.id'], name=op.f('fk_vendor_payment_allocations_payment_transaction_id_transactions'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vendor_payment_allocations'))
    )
    op.create_index('ix_vpa_bill_id', 'vendor_payment_allocations', ['bill_id'], unique=False)
    op.create_index('ix_vpa_payment_trx_id', 'vendor_payment_allocations', ['payment_transaction_id'], unique=False)

    # 3. Create vendor_advances table
    op.create_table(
        'vendor_advances',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('advance_code', sa.String(length=50), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('advance_date', sa.Date(), nullable=False),
        sa.Column('original_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('settled_amount', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('remaining_balance', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('original_amount > 0', name='ck_vendor_advances_orig_positive'),
        sa.CheckConstraint('remaining_balance >= 0', name='ck_vendor_advances_rem_non_negative'),
        sa.CheckConstraint('settled_amount >= 0', name='ck_vendor_advances_settled_non_negative'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_vendor_advances_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_vendor_advances_project_id_projects'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_vendor_advances_transaction_id_transactions'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['vendor_id'], ['counterparties.id'], name=op.f('fk_vendor_advances_vendor_id_counterparties'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vendor_advances')),
        sa.UniqueConstraint('organization_id', 'advance_code', name='uq_vendor_advances_org_code')
    )
    op.create_index(op.f('ix_vendor_advances_organization_id'), 'vendor_advances', ['organization_id'], unique=False)
    op.create_index(op.f('ix_vendor_advances_project_id'), 'vendor_advances', ['project_id'], unique=False)
    op.create_index(op.f('ix_vendor_advances_vendor_id'), 'vendor_advances', ['vendor_id'], unique=False)


def downgrade() -> None:
    op.drop_table('vendor_advances')
    op.drop_table('vendor_payment_allocations')
    op.drop_table('vendor_bills')
