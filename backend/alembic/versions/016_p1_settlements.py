"""016_p1_payment_account_and_settlements

Revision ID: 016_p1_payment_account_and_settlements
Revises: 015_coa_report_section
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '016_p1_settlements'
down_revision: Union[str, None] = '015_coa_report_section'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add destination_payment_account_id to transactions
    op.add_column(
        'transactions',
        sa.Column('destination_payment_account_id', sa.UUID(), sa.ForeignKey('payment_accounts.id', ondelete='RESTRICT'), nullable=True)
    )
    op.create_index('ix_transactions_destination_payment_account_id', 'transactions', ['destination_payment_account_id'])

    # 2. Add payment_account_id to journal_lines
    op.add_column(
        'journal_lines',
        sa.Column('payment_account_id', sa.UUID(), sa.ForeignKey('payment_accounts.id', ondelete='RESTRICT'), nullable=True)
    )
    op.create_index('ix_journal_lines_payment_account_id', 'journal_lines', ['payment_account_id'])

    # 3. Create Enums for MoneyMovement and Settlement
    direction_enum = postgresql.ENUM('IN', 'OUT', name='movement_direction')
    direction_enum.create(op.get_bind(), checkfirst=True)

    source_type_enum = postgresql.ENUM('TRANSFER_PROOF', 'BANK_STATEMENT', 'MANUAL', name='movement_source_type')
    source_type_enum.create(op.get_bind(), checkfirst=True)

    settlement_type_enum = postgresql.ENUM(
        'INVOICE_PAYMENT', 'PROJECT_ALLOCATION', 'INTERBANK_TRANSFER', 'DIRECT_EXPENSE',
        name='settlement_type'
    )
    settlement_type_enum.create(op.get_bind(), checkfirst=True)

    # 4. Create money_movements table
    op.create_table(
        'money_movements',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('movement_code', sa.String(50), nullable=False, unique=True),
        sa.Column('payment_account_id', sa.UUID(), sa.ForeignKey('payment_accounts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('direction', postgresql.ENUM('IN', 'OUT', name='movement_direction', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('movement_date', sa.Date(), nullable=False),
        sa.Column('source_type', postgresql.ENUM('TRANSFER_PROOF', 'BANK_STATEMENT', 'MANUAL', name='movement_source_type', create_type=False), nullable=False),
        sa.Column('reference_no', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_money_movements_organization_id', 'money_movements', ['organization_id'])
    op.create_index('ix_money_movements_payment_account_id', 'money_movements', ['payment_account_id'])

    # 5. Create settlements table
    op.create_table(
        'settlements',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('settlement_code', sa.String(50), nullable=False, unique=True),
        sa.Column('money_movement_id', sa.UUID(), sa.ForeignKey('money_movements.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('transaction_id', sa.UUID(), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('settlement_type', postgresql.ENUM('INVOICE_PAYMENT', 'PROJECT_ALLOCATION', 'INTERBANK_TRANSFER', 'DIRECT_EXPENSE', name='settlement_type', create_type=False), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_settlements_organization_id', 'settlements', ['organization_id'])
    op.create_index('ix_settlements_money_movement_id', 'settlements', ['money_movement_id'])
    op.create_index('ix_settlements_transaction_id', 'settlements', ['transaction_id'])

    # 6. Create settlement_allocations table
    op.create_table(
        'settlement_allocations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('settlement_id', sa.UUID(), sa.ForeignKey('settlements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.UUID(), sa.ForeignKey('projects.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('invoice_id', sa.UUID(), sa.ForeignKey('transactions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('cost_category', postgresql.ENUM('MAT', 'SUB', 'LAB', 'TRN', 'TRV', 'LOG', 'EQP', 'SIT', 'OTH', name='cost_category', create_type=False), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_index('ix_settlement_allocations_settlement_id', 'settlement_allocations', ['settlement_id'])
    op.create_index('ix_settlement_allocations_project_id', 'settlement_allocations', ['project_id'])
    op.create_index('ix_settlement_allocations_invoice_id', 'settlement_allocations', ['invoice_id'])


def downgrade() -> None:
    op.drop_table('settlement_allocations')
    op.drop_table('settlements')
    op.drop_table('money_movements')
    op.drop_index('ix_journal_lines_payment_account_id', 'journal_lines')
    op.drop_column('journal_lines', 'payment_account_id')
    op.drop_index('ix_transactions_destination_payment_account_id', 'transactions')
    op.drop_column('transactions', 'destination_payment_account_id')
