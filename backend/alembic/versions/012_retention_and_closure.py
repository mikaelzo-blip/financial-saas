"""012_retention_and_closure

Revision ID: 012_retention_and_closure
Revises: 011_ai_insights
Create Date: 2026-09-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '012_retention_and_closure'
down_revision: Union[str, None] = '011_ai_insights'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add retention columns to customer_invoices table
    op.add_column('customer_invoices', sa.Column('retention_rate', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.0000'))
    op.add_column('customer_invoices', sa.Column('retention_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0.00'))
    op.add_column('customer_invoices', sa.Column('retention_released_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0.00'))
    op.add_column('customer_invoices', sa.Column('retention_paid_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0.00'))

    # 2. Add retention columns to transactions table
    op.add_column('transactions', sa.Column('retention_rate', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.0000'))
    op.add_column('transactions', sa.Column('retention_amount', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0.00'))

    # 3. Create customer_retention_releases table
    op.create_table(
        'customer_retention_releases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('invoice_id', sa.UUID(), nullable=False),
        sa.Column('release_code', sa.String(length=50), nullable=False),
        sa.Column('release_date', sa.Date(), nullable=False),
        sa.Column('release_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('release_amount > 0', name='ck_crr_amount_positive'),
        sa.ForeignKeyConstraint(['invoice_id'], ['customer_invoices.id'], name=op.f('fk_customer_retention_releases_invoice_id_customer_invoices'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_customer_retention_releases_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_customer_retention_releases')),
        sa.UniqueConstraint('organization_id', 'release_code', name='uq_customer_retention_releases_org_code')
    )
    op.create_index('ix_customer_retention_releases_org_inv', 'customer_retention_releases', ['organization_id', 'invoice_id'], unique=False)
    op.create_index(op.f('ix_customer_retention_releases_invoice_id'), 'customer_retention_releases', ['invoice_id'], unique=False)
    op.create_index(op.f('ix_customer_retention_releases_organization_id'), 'customer_retention_releases', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_table('customer_retention_releases')
    op.drop_column('transactions', 'retention_amount')
    op.drop_column('transactions', 'retention_rate')
    op.drop_column('customer_invoices', 'retention_paid_amount')
    op.drop_column('customer_invoices', 'retention_released_amount')
    op.drop_column('customer_invoices', 'retention_amount')
    op.drop_column('customer_invoices', 'retention_rate')
