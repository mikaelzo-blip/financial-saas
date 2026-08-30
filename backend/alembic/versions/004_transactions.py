"""004_transactions

Revision ID: 004_transactions
Revises: 003_documents
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004_transactions'
down_revision: Union[str, None] = '003_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum types
    transaction_type_enum = sa.Enum(
        'DIRECT_PURCHASE', 'VENDOR_BILL', 'PAY_VENDOR_BILL', 'VENDOR_ADVANCE',
        'SETTLE_VENDOR_ADVANCE', 'SUBCONTRACTOR_BILL', 'PAY_SUBCONTRACTOR',
        'EMPLOYEE_ADVANCE', 'EMPLOYEE_SETTLEMENT', 'CUSTOMER_ADVANCE',
        'REIMBURSEMENT', 'PAY_REIMBURSEMENT', 'PETTY_CASH_EXPENSE',
        'TOPUP_PETTY_CASH', 'RETURN_PETTY_CASH', 'BANK_TO_CASH', 'CASH_TO_BANK',
        'INTERBANK_TRANSFER', 'ASSET_PURCHASE', 'INVENTORY_PURCHASE',
        'INVENTORY_USAGE', 'CUSTOMER_INVOICE', 'CUSTOMER_PAYMENT',
        'REVENUE_RECOGNITION', 'CUSTOMER_REFUND', 'VENDOR_REFUND',
        'OWNER_CONTRIBUTION', 'OWNER_WITHDRAWAL', 'LOAN_RECEIVED', 'LOAN_PAYMENT',
        'BANK_CHARGE', 'OTHER_INCOME', 'OTHER_EXPENSE', 'JOURNAL_ADJUSTMENT', 'REVERSAL',
        name='transaction_type'
    )
    workflow_status_enum = sa.Enum(
        'CAPTURED', 'EXTRACTED', 'STAGED', 'REVIEW_REQUIRED',
        'APPROVED', 'POSTED', 'RECONCILED', 'REVERSED',
        name='workflow_status'
    )
    review_flag_enum = sa.Enum(
        'OCR_LOW_CONFIDENCE', 'MISSING_DOCUMENT', 'DUPLICATE_SUSPECTED',
        'PROJECT_UNKNOWN', 'VENDOR_UNKNOWN', 'CUSTOMER_UNKNOWN',
        'AMOUNT_MISMATCH', 'DATE_MISMATCH', 'TAX_REVIEW', 'ACCOUNT_REVIEW',
        'RELATED_PARTY_REVIEW',
        name='review_flag'
    )

    # 2. Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('transaction_code', sa.String(length=50), nullable=False),
        sa.Column('transaction_type', transaction_type_enum, nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='IDR', nullable=False),
        sa.Column('workflow_status', workflow_status_enum, server_default='STAGED', nullable=False),
        sa.Column('counterparty_id', sa.UUID(), nullable=True),
        sa.Column('payment_account_id', sa.UUID(), nullable=True),
        sa.Column('reference_no', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('source_channel', sa.String(length=50), server_default='WEB', nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reversal_of_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_transactions_amount_positive'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_transactions_approved_by_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['counterparty_id'], ['counterparties.id'], name=op.f('fk_transactions_counterparty_id_counterparties'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_transactions_created_by_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_transactions_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_account_id'], ['payment_accounts.id'], name=op.f('fk_transactions_payment_account_id_payment_accounts'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reversal_of_id'], ['transactions.id'], name=op.f('fk_transactions_reversal_of_id_transactions'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transactions')),
        sa.UniqueConstraint('organization_id', 'transaction_code', name='uq_transactions_org_code')
    )
    op.create_index('ix_transactions_org_date', 'transactions', ['organization_id', 'transaction_date'], unique=False)
    op.create_index('ix_transactions_org_status', 'transactions', ['organization_id', 'workflow_status'], unique=False)
    op.create_index(op.f('ix_transactions_counterparty_id'), 'transactions', ['counterparty_id'], unique=False)
    op.create_index(op.f('ix_transactions_organization_id'), 'transactions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_transactions_payment_account_id'), 'transactions', ['payment_account_id'], unique=False)
    op.create_index(op.f('ix_transactions_transaction_code'), 'transactions', ['transaction_code'], unique=False)

    # 3. Create transaction_allocations table
    cost_category_enum = postgresql.ENUM(name='cost_category', create_type=False)
    expense_category_enum = sa.Enum(
        'SALARY', 'FEE', 'OFFICE_ADMIN', 'TRAVEL_OFFICE', 'PERMITS',
        'PROFESSIONAL_SERVICE', 'BANK_CHARGES', 'DEPRECIATION', 'OTHER_OPERATIONAL',
        name='expense_category'
    )

    op.create_table(
        'transaction_allocations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('cost_category', cost_category_enum, nullable=True),
        sa.Column('expense_category', expense_category_enum, nullable=True),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.CheckConstraint('amount > 0', name='ck_allocations_amount_positive'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_transaction_allocations_project_id_projects'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_transaction_allocations_transaction_id_transactions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transaction_allocations'))
    )
    op.create_index(op.f('ix_transaction_allocations_project_id'), 'transaction_allocations', ['project_id'], unique=False)
    op.create_index(op.f('ix_transaction_allocations_transaction_id'), 'transaction_allocations', ['transaction_id'], unique=False)

    # 4. Create transaction_review_flags table
    op.create_table(
        'transaction_review_flags',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column('flag', review_flag_enum, nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='WARNING', nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resolved_by', sa.UUID(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], name=op.f('fk_transaction_review_flags_resolved_by_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_transaction_review_flags_transaction_id_transactions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_transaction_review_flags'))
    )
    op.create_index(op.f('ix_transaction_review_flags_transaction_id'), 'transaction_review_flags', ['transaction_id'], unique=False)


def downgrade() -> None:
    op.drop_table('transaction_review_flags')
    op.drop_table('transaction_allocations')
    op.drop_table('transactions')
    sa.Enum(name='expense_category').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='review_flag').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='workflow_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='transaction_type').drop(op.get_bind(), checkfirst=True)
