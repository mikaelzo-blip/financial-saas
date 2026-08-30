"""008_document_intelligence: additive document processing metadata and corrections."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_document_intelligence"
down_revision: Union[str, None] = "007_receivables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve legacy labels from 003 while making every locked Feature 005 label writable.
    for value in ("PO_CUSTOMER", "SPK", "CONTRACT", "VARIATION_ORDER", "PURCHASE_ORDER",
                  "QUOTATION", "VENDOR_INVOICE", "SUBCONTRACT_AGREEMENT", "TRANSFER_PROOF",
                  "RECEIPT", "BANK_STATEMENT", "PETTY_CASH_PROOF", "SURAT_JALAN", "BAST",
                  "PROGRESS_REPORT", "TIMESHEET", "CUSTOMER_INVOICE", "CUSTOMER_RECEIPT",
                  "TAX_INVOICE", "WITHHOLDING_DOCUMENT", "OTHER_TAX_DOCUMENT", "UNKNOWN"):
        op.execute(f"ALTER TYPE document_type ADD VALUE IF NOT EXISTS '{value}'")
    status = sa.Enum("UPLOADED", "HASHED", "EXTRACTING", "EXTRACTED", "MATCHING",
                     "REVIEW_REQUIRED", "READY_FOR_APPROVAL", "PROCESSED", "FAILED",
                     name="document_processing_status")
    status.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("processing_status", status, server_default="UPLOADED", nullable=False))
        batch.add_column(sa.Column("provider_name", sa.String(100), nullable=True))
        batch.add_column(sa.Column("provider_version", sa.String(50), nullable=True))
        batch.add_column(sa.Column("processing_attempts", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("extracted_data", sa.JSON(), server_default="{}", nullable=False))
        batch.add_column(sa.Column("matching_results", sa.JSON(), server_default="{}", nullable=False))
        batch.add_column(sa.Column("confidence_scores", sa.JSON(), server_default="{}", nullable=False))
        batch.add_column(sa.Column("candidate_transaction", sa.JSON(), server_default="{}", nullable=False))
        batch.add_column(sa.Column("review_flags", sa.JSON(), server_default="[]", nullable=False))
        batch.add_column(sa.Column("failure_code", sa.String(100), nullable=True))
        batch.add_column(sa.Column("failure_message", sa.Text(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_table("document_corrections",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False), sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True), sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False), sa.Column("corrected_by", sa.UUID(), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["corrected_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_document_corrections_organization_id", "document_corrections", ["organization_id"])
    op.create_index("ix_document_corrections_document_id", "document_corrections", ["document_id"])


def downgrade() -> None:
    op.drop_table("document_corrections")
    with op.batch_alter_table("documents") as batch:
        for name in ("updated_at", "failure_message", "failure_code", "review_flags", "candidate_transaction",
                     "confidence_scores", "matching_results", "extracted_data", "processing_attempts",
                     "provider_version", "provider_name", "processing_status"):
            batch.drop_column(name)
    sa.Enum(name="document_processing_status").drop(op.get_bind(), checkfirst=True)
