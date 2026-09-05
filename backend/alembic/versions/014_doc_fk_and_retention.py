"""014_transaction_document_fk_and_retention_enum

Revision ID: 014_transaction_document_fk_and_retention_enum
Revises: 013_document_review_rejection
Create Date: 2026-09-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '014_doc_fk_and_retention'
down_revision: Union[str, None] = '013_document_review_rejection'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure RETENTION_RELEASE is present in transaction_type enum in PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE transaction_type ADD VALUE IF NOT EXISTS 'RETENTION_RELEASE'")

    # 2. Add foreign key from transaction_document_links.transaction_id to transactions.id
    op.create_foreign_key(
        'fk_transaction_document_links_transaction_id_transactions',
        'transaction_document_links',
        'transactions',
        ['transaction_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_transaction_document_links_transaction_id_transactions',
        'transaction_document_links',
        type_='foreignkey'
    )
