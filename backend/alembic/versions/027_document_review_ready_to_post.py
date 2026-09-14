"""027_document_review_ready_to_post

Revision ID: 027_document_review_ready_to_post
Revises: 026_document_inbox_queue
Create Date: 2026-09-14

Adds READY_TO_POST to document_processing_status enum.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "027_document_review_ready_to_post"
down_revision: Union[str, None] = "026_document_inbox_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
        op.execute("ALTER TYPE document_processing_status ADD VALUE IF NOT EXISTS 'READY_TO_POST'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type safely.
    pass
