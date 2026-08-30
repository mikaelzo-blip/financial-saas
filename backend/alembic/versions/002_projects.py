"""002_projects

Revision ID: 002_projects
Revises: 001_initial_schema
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_projects'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create enum types
    project_status_enum = sa.Enum(
        'PLANNED', 'ACTIVE', 'ON_HOLD', 'COMPLETED', 'CLOSED', 'CANCELLED',
        name='project_status'
    )
    cost_category_enum = sa.Enum(
        'MAT', 'SUB', 'LAB', 'TRN', 'TRV', 'LOG', 'EQP', 'SIT', 'OTH',
        name='cost_category'
    )

    # 2. Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('project_code', sa.String(length=50), nullable=False),
        sa.Column('project_name', sa.String(length=255), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('po_spk_no', sa.String(length=100), nullable=True),
        sa.Column('po_spk_date', sa.Date(), nullable=True),
        sa.Column('original_contract_value', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('variation_order_value', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('revised_contract_value', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('target_end_date', sa.Date(), nullable=True),
        sa.Column('actual_end_date', sa.Date(), nullable=True),
        sa.Column('pic_user_id', sa.UUID(), nullable=True),
        sa.Column('project_status', project_status_enum, server_default='PLANNED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('original_contract_value >= 0', name='ck_projects_original_contract_value_positive'),
        sa.CheckConstraint('revised_contract_value >= 0', name='ck_projects_revised_contract_value_positive'),
        sa.ForeignKeyConstraint(['customer_id'], ['counterparties.id'], name=op.f('fk_projects_customer_id_counterparties'), ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_projects_organization_id_organizations'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pic_user_id'], ['users.id'], name=op.f('fk_projects_pic_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
        sa.UniqueConstraint('organization_id', 'project_code', name='uq_projects_org_project_code')
    )
    op.create_index(op.f('ix_projects_customer_id'), 'projects', ['customer_id'], unique=False)
    op.create_index(op.f('ix_projects_organization_id'), 'projects', ['organization_id'], unique=False)
    op.create_index(op.f('ix_projects_pic_user_id'), 'projects', ['pic_user_id'], unique=False)
    op.create_index(op.f('ix_projects_project_code'), 'projects', ['project_code'], unique=False)

    # 3. Create project_budgets table
    op.create_table(
        'project_budgets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('cost_category', cost_category_enum, nullable=False),
        sa.Column('budget_amount', sa.Numeric(precision=18, scale=2), server_default='0.00', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.CheckConstraint('budget_amount >= 0', name='ck_project_budgets_amount_positive'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_budgets_project_id_projects'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_project_budgets')),
        sa.UniqueConstraint('project_id', 'cost_category', name='uq_project_budgets_project_category')
    )
    op.create_index(op.f('ix_project_budgets_project_id'), 'project_budgets', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_table('project_budgets')
    op.drop_table('projects')
    sa.Enum(name='cost_category').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='project_status').drop(op.get_bind(), checkfirst=True)
