"""007_receivables

Revision ID: 007_receivables
Revises: 006_payables
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '007_receivables'
down_revision: Union[str, None] = '006_payables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create customer_invoices table
    op.create_table(
        'customer_invoices',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('invoice_code', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('due_date_override_reason', sa.Text(), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='UNPAID', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('total_amount > 0', name='ck_customer_invoices_amount_positive'),
        sa.ForeignKeyConstraint(['customer_id'], ['counterparties.id'], name=op.f('fk_customer_invoices_customer_id_counterparties'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_customer_invoices_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_customer_invoices_project_id_projects'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_customer_invoices_transaction_id_transactions'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_invoices')),
        sa.UniqueConstraint('organization_id', 'invoice_code', name='uq_customer_invoices_org_code')
    )
    op.create_index('ix_customer_invoices_due_date', 'customer_invoices', ['organization_id', 'due_date'], unique=False)
    op.create_index('ix_customer_invoices_org_customer', 'customer_invoices', ['organization_id', 'customer_id'], unique=False)
    op.create_index(op.f('ix_customer_invoices_customer_id'), 'customer_invoices', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_invoices_invoice_code'), 'customer_invoices', ['invoice_code'], unique=False)
    op.create_index(op.f('ix_customer_invoices_organization_id'), 'customer_invoices', ['organization_id'], unique=False)
    op.create_index(op.f('ix_customer_invoices_project_id'), 'customer_invoices', ['project_id'], unique=False)

    # 2. Create customer_payment_allocations table
    op.create_table(
        'customer_payment_allocations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('payment_transaction_id', sa.UUID(), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('allocated_amount > 0', name='ck_cpa_amount_positive'),
        sa.ForeignKeyConstraint(['invoice_id'], ['customer_invoices.id'], name=op.f('fk_customer_payment_allocations_invoice_id_customer_invoices'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_transaction_id'], ['transactions.id'], name=op.f('fk_customer_payment_allocations_payment_transaction_id_transactions'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_payment_allocations'))
    )
    op.create_index('ix_cpa_invoice_id', 'customer_payment_allocations', ['invoice_id'], unique=False)
    op.create_index('ix_cpa_payment_trx_id', 'customer_payment_allocations', ['payment_transaction_id'], unique=False)


def downgrade() -> None:
    op.drop_table('customer_payment_allocations')
    op.drop_table('customer_invoices')
