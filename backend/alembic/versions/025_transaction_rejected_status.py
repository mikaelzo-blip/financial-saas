"""025_transaction_rejected_status

Revision ID: 025_transaction_rejected
Revises: 024_recon_integrity_invariants
Create Date: 2026-09-13

Adds the approved terminal REJECTED state to the transaction workflow enum.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "025_transaction_rejected"
down_revision: Union[str, None] = "024_recon_integrity_invariants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE workflow_status ADD VALUE IF NOT EXISTS 'REJECTED'")


def downgrade() -> None:
    # PostgreSQL enum labels are retained to avoid rewriting transaction history.
    pass
