"""017_p2_bank_reconciliation

Revision ID: 017_p2_bank_reconciliation
Revises: 016_p1_settlements
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '017_p2_bank_reconciliation'
down_revision: Union[str, None] = '016_p1_settlements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. bank_statement_imports
    op.create_table(
        'bank_statement_imports',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_account_id', sa.UUID(), sa.ForeignKey('payment_accounts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('source_file', sa.String(255), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(50), nullable=False, server_default='COMPLETED'),
        sa.UniqueConstraint('organization_id', 'file_hash', name='uq_bank_statement_import_file_hash')
    )
    op.create_index('ix_bank_statement_imports_org', 'bank_statement_imports', ['organization_id'])
    op.create_index('ix_bank_statement_imports_pa', 'bank_statement_imports', ['payment_account_id'])

    # 2. bank_statement_lines
    op.create_table(
        'bank_statement_lines',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('import_id', sa.UUID(), sa.ForeignKey('bank_statement_imports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('debit', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('credit', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('balance', sa.Numeric(18, 2), nullable=True),
        sa.Column('reference', sa.String(255), nullable=True),
        sa.Column('counterparty_name', sa.String(255), nullable=True),
        sa.Column('reconciliation_status', sa.String(50), nullable=False, server_default='UNMATCHED_BANK')
    )
    op.create_index('ix_bank_statement_lines_import', 'bank_statement_lines', ['import_id'])
    op.create_index('ix_bank_statement_lines_org', 'bank_statement_lines', ['organization_id'])
    op.create_index('ix_bank_statement_lines_date', 'bank_statement_lines', ['transaction_date'])
    op.create_index('ix_bank_statement_lines_status', 'bank_statement_lines', ['reconciliation_status'])

    # 3. bank_reconciliations
    op.create_table(
        'bank_reconciliations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('statement_line_id', sa.UUID(), sa.ForeignKey('bank_statement_lines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('journal_line_id', sa.UUID(), sa.ForeignKey('journal_lines.id', ondelete='SET NULL'), nullable=True),
        sa.Column('money_movement_id', sa.UUID(), sa.ForeignKey('money_movements.id', ondelete='SET NULL'), nullable=True),
        sa.Column('transaction_id', sa.UUID(), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='MATCHED'),
        sa.Column('matched_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('match_rule', sa.String(100), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('matched_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('matched_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )
    op.create_index('ix_bank_reconciliations_org', 'bank_reconciliations', ['organization_id'])
    op.create_index('ix_bank_reconciliations_line', 'bank_reconciliations', ['statement_line_id'])
    op.create_index('ix_bank_reconciliations_jl', 'bank_reconciliations', ['journal_line_id'])
    op.create_index('ix_bank_reconciliations_mm', 'bank_reconciliations', ['money_movement_id'])
    op.create_index('ix_bank_reconciliations_trx', 'bank_reconciliations', ['transaction_id'])


def downgrade() -> None:
    op.drop_table('bank_reconciliations')
    op.drop_table('bank_statement_lines')
    op.drop_table('bank_statement_imports')
