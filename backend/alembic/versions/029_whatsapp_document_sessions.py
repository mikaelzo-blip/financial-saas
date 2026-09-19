"""029_whatsapp_document_sessions

Revision ID: 029_whatsapp_document_sessions
Revises: 028_document_posting_linkage
Create Date: 2026-09-18

Adds whatsapp_document_sessions table and session/provider timestamp tracking on whatsapp_message_logs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "029_whatsapp_document_sessions"
down_revision: Union[str, None] = "028_document_posting_linkage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_document_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("session_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("first_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hard_max_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ack_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ack_wamid", sa.String(128), nullable=True),
        sa.Column("document_ids", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), server_default="[]", nullable=False),
        sa.Column("message_wamids", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), server_default="[]", nullable=False),
        sa.Column("captions", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), server_default="[]", nullable=False),
        sa.Column("session_metadata", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "session_code", name="uq_wa_session_org_code"),
    )
    op.create_index("idx_wa_session_phone_status", "whatsapp_document_sessions", ["organization_id", "phone_number", "status"])
    op.create_index("idx_wa_session_window", "whatsapp_document_sessions", ["status", "window_expires_at"])

    with op.batch_alter_table("whatsapp_message_logs") as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column("provider_timestamp", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("media_id", sa.String(128), nullable=True))
        batch_op.create_foreign_key(
            "fk_wa_log_session_id",
            "whatsapp_document_sessions",
            ["session_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_message_logs") as batch_op:
        batch_op.drop_constraint("fk_wa_log_session_id", type_="foreignkey")
        batch_op.drop_column("media_id")
        batch_op.drop_column("provider_timestamp")
        batch_op.drop_column("session_id")

    op.drop_index("idx_wa_session_window", table_name="whatsapp_document_sessions")
    op.drop_index("idx_wa_session_phone_status", table_name="whatsapp_document_sessions")
    op.drop_table("whatsapp_document_sessions")
