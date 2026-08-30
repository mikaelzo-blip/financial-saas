"""Add SaaS-owned WhatsApp mapping, audit and clarification state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010_whatsapp_integration"
down_revision = "009_hermes_submissions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("whatsapp_sender_mappings",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role_in_org", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_wa_sender_org", "whatsapp_sender_mappings", ["organization_id", "is_active"])
    op.create_table("whatsapp_message_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("wamid", sa.String(128), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("raw_text", sa.Text()), sa.Column("media_mime_type", sa.String(64)),
        sa.Column("media_size_bytes", sa.BigInteger()),
        sa.Column("hermes_submission_id", sa.UUID(), sa.ForeignKey("hermes_submissions.id")),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id")),
        sa.Column("delivery_status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "wamid", name="uq_wa_log_org_wamid"),
    )
    op.create_index("idx_wa_log_org_created", "whatsapp_message_logs", ["organization_id", "created_at"])
    op.create_index("idx_wa_log_phone", "whatsapp_message_logs", ["phone_number"])
    op.create_table("whatsapp_clarification_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("question_type", sa.String(32), nullable=False),
        sa.Column("options_payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("status", sa.String(16), server_default="PENDING", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_wa_clarification_phone_status", "whatsapp_clarification_sessions", ["phone_number", "status", "expires_at"])
    op.create_index("idx_wa_clarification_doc", "whatsapp_clarification_sessions", ["document_id"])


def downgrade():
    op.drop_table("whatsapp_clarification_sessions")
    op.drop_table("whatsapp_message_logs")
    op.drop_table("whatsapp_sender_mappings")
