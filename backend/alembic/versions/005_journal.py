"""005_journal

Revision ID: 005_journal
Revises: 004_transactions
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '005_journal'
down_revision: Union[str, None] = '004_transactions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create journal_entries table
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('entry_number', sa.String(length=50), nullable=False),
        sa.Column('transaction_id', sa.UUID(), nullable=False),
        sa.Column('posting_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('total_debit', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('total_credit', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('is_balanced', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_reversed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reversal_entry_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('total_debit > 0', name='ck_je_total_debit_positive'),
        sa.CheckConstraint('total_credit > 0', name='ck_je_total_credit_positive'),
        sa.CheckConstraint('total_debit = total_credit', name='ck_je_balanced'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_journal_entries_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reversal_entry_id'], ['journal_entries.id'], name=op.f('fk_journal_entries_reversal_entry_id_journal_entries'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name=op.f('fk_journal_entries_transaction_id_transactions'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_journal_entries')),
        sa.UniqueConstraint('organization_id', 'entry_number', name='uq_je_org_entry_number'),
        sa.UniqueConstraint('transaction_id', name='uq_je_transaction_id')
    )
    op.create_index('ix_je_org_posting_date', 'journal_entries', ['organization_id', 'posting_date'], unique=False)
    op.create_index(op.f('ix_journal_entries_entry_number'), 'journal_entries', ['entry_number'], unique=False)
    op.create_index(op.f('ix_journal_entries_organization_id'), 'journal_entries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_journal_entries_transaction_id'), 'journal_entries', ['transaction_id'], unique=False)

    # 2. Create journal_lines table
    cost_category_enum = postgresql.ENUM(name='cost_category', create_type=False)
    expense_category_enum = postgresql.ENUM(name='expense_category', create_type=False)

    op.create_table(
        'journal_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('journal_entry_id', sa.UUID(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('debit_amount', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('credit_amount', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('counterparty_id', sa.UUID(), nullable=True),
        sa.Column('cost_category', cost_category_enum, nullable=True),
        sa.Column('expense_category', expense_category_enum, nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.CheckConstraint('debit_amount >= 0', name='ck_jl_debit_non_negative'),
        sa.CheckConstraint('credit_amount >= 0', name='ck_jl_credit_non_negative'),
        sa.CheckConstraint('(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)', name='ck_jl_one_sided_amount'),
        sa.ForeignKeyConstraint(['account_id'], ['chart_of_accounts.id'], name=op.f('fk_journal_lines_account_id_chart_of_accounts'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['counterparty_id'], ['counterparties.id'], name=op.f('fk_journal_lines_counterparty_id_counterparties'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], name=op.f('fk_journal_lines_journal_entry_id_journal_entries'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_journal_lines_project_id_projects'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_journal_lines'))
    )
    op.create_index('ix_jl_account_id', 'journal_lines', ['account_id'], unique=False)
    op.create_index('ix_jl_counterparty_id', 'journal_lines', ['counterparty_id'], unique=False)
    op.create_index('ix_jl_project_id', 'journal_lines', ['project_id'], unique=False)
    op.create_index(op.f('ix_journal_lines_journal_entry_id'), 'journal_lines', ['journal_entry_id'], unique=False)


def downgrade() -> None:
    op.drop_table('journal_lines')
    op.drop_table('journal_entries')
