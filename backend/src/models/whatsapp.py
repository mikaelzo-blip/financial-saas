"""SaaS-owned channel state. Never imported by the external adapter."""
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.database import Base, TimestampMixin


class WhatsAppSenderMapping(Base, TimestampMixin):
    __tablename__ = "whatsapp_sender_mappings"
    __table_args__ = (Index("idx_wa_sender_org", "organization_id", "is_active"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_in_org: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)


class WhatsAppMessageLog(Base):
    __tablename__ = "whatsapp_message_logs"
    __table_args__ = (
        UniqueConstraint("organization_id", "wamid", name="uq_wa_log_org_wamid"),
        Index("idx_wa_log_org_created", "organization_id", "created_at"),
        Index("idx_wa_log_phone", "phone_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    wamid: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    media_mime_type: Mapped[str | None] = mapped_column(String(64))
    media_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    hermes_submission_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hermes_submissions.id"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhatsAppClarificationSession(Base):
    __tablename__ = "whatsapp_clarification_sessions"
    __table_args__ = (
        Index("idx_wa_clarification_phone_status", "phone_number", "status", "expires_at"),
        Index("idx_wa_clarification_doc", "document_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    options_payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", server_default="PENDING", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(hours=24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
