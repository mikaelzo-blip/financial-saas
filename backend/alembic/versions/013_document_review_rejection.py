"""013_document_review_rejection: add terminal document rejection state."""
from typing import Sequence, Union

from alembic import op

revision: str = "013_document_review_rejection"
down_revision: Union[str, None] = "012_retention_and_closure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_processing_status ADD VALUE IF NOT EXISTS 'REJECTED'")


def downgrade() -> None:
    # PostgreSQL enum labels are intentionally retained to avoid rewriting data.
    pass
