"""015_coa_report_section

Revision ID: 015_coa_report_section
Revises: 014_doc_fk_and_retention
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '015_coa_report_section'
down_revision: Union[str, None] = '014_doc_fk_and_retention'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chart_of_accounts', sa.Column('report_section', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('chart_of_accounts', 'report_section')
