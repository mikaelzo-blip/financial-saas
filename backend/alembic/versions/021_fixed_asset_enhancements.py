"""021_fixed_asset_enhancements

Revision ID: 021_fixed_asset_enhancements
Revises: 020_p7_background_jobs
Create Date: 2026-09-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '021_fixed_asset_enhancements'
down_revision: Union[str, None] = '020_p7_background_jobs'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add enhancement columns to fixed_assets
    op.add_column('fixed_assets', sa.Column('available_for_use_date', sa.Date(), nullable=True))
    op.add_column('fixed_assets', sa.Column('fiscal_asset_group', sa.String(50), nullable=True))
    op.add_column('fixed_assets', sa.Column('fiscal_depreciation_method', sa.String(50), nullable=True))
    op.add_column('fixed_assets', sa.Column('fiscal_useful_life_months', sa.Integer(), nullable=True))

    # 2. Create fixed_asset_depreciations table
    op.create_table(
        'fixed_asset_depreciations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_id', sa.UUID(), sa.ForeignKey('fixed_assets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_date', sa.Date(), nullable=False),
        sa.Column('depreciation_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('accumulated_after', sa.Numeric(18, 2), nullable=False),
        sa.Column('book_value_after', sa.Numeric(18, 2), nullable=False),
        sa.Column('transaction_id', sa.UUID(), sa.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('journal_entry_id', sa.UUID(), sa.ForeignKey('journal_entries.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('asset_id', 'period_date', name='uq_asset_depr_period')
    )
    op.create_index('ix_asset_depr_org', 'fixed_asset_depreciations', ['organization_id'])
    op.create_index('ix_asset_depr_asset', 'fixed_asset_depreciations', ['asset_id'])


def downgrade() -> None:
    op.drop_table('fixed_asset_depreciations')
    op.drop_column('fixed_assets', 'fiscal_useful_life_months')
    op.drop_column('fixed_assets', 'fiscal_depreciation_method')
    op.drop_column('fixed_assets', 'fiscal_asset_group')
    op.drop_column('fixed_assets', 'available_for_use_date')
