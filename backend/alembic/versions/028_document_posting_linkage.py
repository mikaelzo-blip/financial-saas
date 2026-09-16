"""028_document_posting_linkage

Revision ID: 028_document_posting_linkage
Revises: 027_document_review_ready_to_post
Create Date: 2026-09-16

Adds POSTED to document_processing_status enum and durable converted_transaction_id linkage to documents.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "028_document_posting_linkage"
down_revision: Union[str, None] = "027_document_review_ready_to_post"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
        op.execute("ALTER TYPE document_processing_status ADD VALUE IF NOT EXISTS 'POSTED'")

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("converted_transaction_id", sa.UUID(), nullable=True))
        batch_op.create_index("ix_documents_converted_transaction_id", ["converted_transaction_id"], unique=True)
        batch_op.create_foreign_key(
            "fk_documents_converted_transaction_id",
            "transactions",
            ["converted_transaction_id"],
            ["id"],
            ondelete="RESTRICT"
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("fk_documents_converted_transaction_id", type_="foreignkey")
        batch_op.drop_index("ix_documents_converted_transaction_id")
        batch_op.drop_column("converted_transaction_id")
