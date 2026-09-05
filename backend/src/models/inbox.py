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
        nullable=False,
        index=True
    )
    external_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[InboxMessageStatus] = mapped_column(
        String(50),
        default=InboxMessageStatus.RECEIVED,
        nullable=False,
        index=True
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
        Index("ix_inbox_messages_org_status", "organization_id", "status"),
    )


class InboxAttachment(Base):
    __tablename__ = "inbox_attachments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    inbox_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inbox_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    inbox_message: Mapped["InboxMessage"] = relationship(
        "InboxMessage",
        back_populates="attachments"
    )


class DocumentSession(Base):
    __tablename__ = "document_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    session_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[SessionMatchStatus] = mapped_column(
        String(50),
        default=SessionMatchStatus.PENDING,
        nullable=False,
        index=True
    )
    inbox_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("inbox_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
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

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
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
