"""009_hermes_submissions: additive tenant-scoped Hermes idempotency correlation."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009_hermes_submissions"
down_revision: Union[str, None] = "008_document_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hermes_submissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("outcome_status", sa.String(length=50), server_default="RECEIVED", nullable=False),
        sa.Column("safe_error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "operation", "idempotency_key_hash", name="uq_hermes_submissions_org_operation_key"),
    )
    op.create_index("ix_hermes_submissions_organization_id", "hermes_submissions", ["organization_id"])
    op.create_index("ix_hermes_submissions_document_id", "hermes_submissions", ["document_id"])
    op.create_index("ix_hermes_submissions_org_document", "hermes_submissions", ["organization_id", "document_id"])


def downgrade() -> None:
    op.drop_table("hermes_submissions")
