import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    BigInteger,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.models.enums import InboxMessageStatus, SessionMatchStatus


class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    external_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[InboxMessageStatus] = mapped_column(
        String(50),
        default=InboxMessageStatus.RECEIVED,
        nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attachments: Mapped[List["InboxAttachment"]] = relationship(
        "InboxAttachment",
        back_populates="inbox_message",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "external_message_id", name="uq_inbox_message_external_id"),
        Index("ix_inbox_messages_org", "organization_id"),
        Index("ix_inbox_messages_phone", "sender_phone"),
        Index("ix_inbox_messages_org_status", "organization_id", "status"),
    )


class InboxAttachment(Base):
    __tablename__ = "inbox_attachments"
    __table_args__ = (
        Index("ix_inbox_attachments_msg", "inbox_message_id"),
        Index("ix_inbox_attachments_org", "organization_id"),
        Index("ix_inbox_attachments_hash", "file_hash_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inbox_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inbox_messages.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inbox_message: Mapped["InboxMessage"] = relationship(
        "InboxMessage",
        back_populates="attachments"
    )


class DocumentSession(Base):
    __tablename__ = "document_sessions"
    __table_args__ = (
        Index("ix_document_sessions_org", "organization_id"),
        Index("ix_document_sessions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    session_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[SessionMatchStatus] = mapped_column(
        String(50),
        default=SessionMatchStatus.PENDING,
        nullable=False
    )
    inbox_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("inbox_messages.id", ondelete="SET NULL"),
        nullable=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inbox_message: Mapped[Optional["InboxMessage"]] = relationship("InboxMessage")
    document: Mapped[Optional["Document"]] = relationship("Document")

    evidences: Mapped[List["MatchEvidence"]] = relationship(
        "MatchEvidence",
        back_populates="document_session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class MatchEvidence(Base):
    __tablename__ = "match_evidences"
    __table_args__ = (
        Index("ix_match_evidences_session", "document_session_id"),
        Index("ix_match_evidences_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_sessions.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1.0000"), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document_session: Mapped["DocumentSession"] = relationship(
        "DocumentSession",
        back_populates="evidences"
    )
