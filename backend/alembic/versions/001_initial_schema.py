"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('legal_name', sa.String(length=255), nullable=False),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('default_payment_term_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('fiscal_year_start_month', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
        sa.UniqueConstraint('slug', name=op.f('uq_organizations_slug'))
    )
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)

    # 2. Create users
    user_role_enum = sa.Enum('ADMIN', 'MANAGER', 'OPERATOR', 'VIEWER', name='user_role')
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', user_role_enum, nullable=False, server_default='OPERATOR'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_users_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('organization_id', 'email', name='uq_users_org_email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
    op.create_index(op.f('ix_users_organization_id'), 'users', ['organization_id'], unique=False)

    # 3. Create counterparties
    op.create_table(
        'counterparties',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_customer', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_vendor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('contact_info', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('bank_accounts', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_counterparties_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_counterparties'))
    )
    op.create_index(op.f('ix_counterparties_name'), 'counterparties', ['name'], unique=False)
    op.create_index(op.f('ix_counterparties_organization_id'), 'counterparties', ['organization_id'], unique=False)

    # 4. Create chart_of_accounts
    account_type_enum = sa.Enum('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE', name='account_type')
    normal_balance_enum = sa.Enum('DEBIT', 'CREDIT', name='normal_balance')
    op.create_table(
        'chart_of_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('account_code', sa.String(length=20), nullable=False),
        sa.Column('account_name', sa.String(length=255), nullable=False),
        sa.Column('account_type', account_type_enum, nullable=False),
        sa.Column('normal_balance', normal_balance_enum, nullable=False),
        sa.Column('report_group', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_chart_of_accounts_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_chart_of_accounts')),
        sa.UniqueConstraint('organization_id', 'account_code', name='uq_coa_org_account_code')
    )
    op.create_index(op.f('ix_chart_of_accounts_account_code'), 'chart_of_accounts', ['account_code'], unique=False)
    op.create_index(op.f('ix_chart_of_accounts_organization_id'), 'chart_of_accounts', ['organization_id'], unique=False)

    # 5. Create payment_accounts
    op.create_table(
        'payment_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('coa_account_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('account_number', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['coa_account_id'], ['chart_of_accounts.id'], name=op.f('fk_payment_accounts_coa_account_id_chart_of_accounts'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_payment_accounts_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payment_accounts'))
    )
    op.create_index(op.f('ix_payment_accounts_coa_account_id'), 'payment_accounts', ['coa_account_id'], unique=False)
    op.create_index(op.f('ix_payment_accounts_organization_id'), 'payment_accounts', ['organization_id'], unique=False)

    # 6. Create audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('entity_name', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('old_values', sa.JSON(), nullable=True),
        sa.Column('new_values', sa.JSON(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_audit_logs_organization_id_organizations'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index('ix_audit_logs_org_entity', 'audit_logs', ['organization_id', 'entity_name', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_id'), 'audit_logs', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('payment_accounts')
    op.drop_table('chart_of_accounts')
    op.drop_table('counterparties')
    op.drop_table('users')
    op.drop_table('organizations')
    sa.Enum(name='normal_balance').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='account_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
