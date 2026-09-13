"""026_document_inbox_queue_slice1

Revision ID: 026_document_inbox_queue
Revises: 025_transaction_rejected
Create Date: 2026-09-13

Adds QUEUED to document_processing_status enum and idempotency_key to background_jobs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "026_document_inbox_queue"
down_revision: Union[str, None] = "025_transaction_rejected"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE document_processing_status ADD VALUE IF NOT EXISTS 'QUEUED'")

    with op.batch_alter_table("background_jobs") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(255), nullable=True))
        batch_op.create_index("ix_jobs_idempotency_key", ["idempotency_key"])
        batch_op.create_index(
            "uq_jobs_active_idempotency",
            ["organization_id", "job_type", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL AND status IN ('PENDING', 'RUNNING')"),
            sqlite_where=sa.text("idempotency_key IS NOT NULL AND status IN ('PENDING', 'RUNNING')"),
            postgresql_nulls_not_distinct=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("background_jobs") as batch_op:
        batch_op.drop_index("uq_jobs_active_idempotency")
        batch_op.drop_index("ix_jobs_idempotency_key")
        batch_op.drop_column("idempotency_key")
