"""019_p6_accounting_periods_and_fixed_assets

Revision ID: 019_p6_periods_and_assets
Revises: 018_remote_inbox
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '019_p6_periods_and_assets'
down_revision: Union[str, None] = '018_remote_inbox'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. accounting_periods
    op.create_table(
        'accounting_periods',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_name', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='OPEN'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_by', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('organization_id', 'period_name', name='uq_period_org_name')
    )
    op.create_index('ix_accounting_periods_org', 'accounting_periods', ['organization_id'])
    op.create_index('ix_period_org_dates', 'accounting_periods', ['organization_id', 'start_date', 'end_date'])

    # 2. fixed_assets
    op.create_table(
        'fixed_assets',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('asset_code', sa.String(50), nullable=False, unique=True),
        sa.Column('asset_name', sa.String(255), nullable=False),
        sa.Column('asset_category', sa.String(100), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('purchase_cost', sa.Numeric(18, 2), nullable=False),
        sa.Column('salvage_value', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('useful_life_months', sa.Integer(), nullable=False),
        sa.Column('depreciation_method', sa.String(50), nullable=False, server_default='STRAIGHT_LINE'),
        sa.Column('accumulated_depreciation', sa.Numeric(18, 2), nullable=False, server_default='0.00'),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('vendor_id', sa.UUID(), sa.ForeignKey('counterparties.id', ondelete='SET NULL'), nullable=True),
        sa.Column('document_id', sa.UUID(), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('asset_account_id', sa.UUID(), sa.ForeignKey('chart_of_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('depreciation_account_id', sa.UUID(), sa.ForeignKey('chart_of_accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    op.create_index('ix_fixed_assets_org', 'fixed_assets', ['organization_id'])
    op.create_index('ix_fixed_assets_category', 'fixed_assets', ['organization_id', 'asset_category'])


def downgrade() -> None:
    op.drop_table('fixed_assets')
    op.drop_table('accounting_periods')
