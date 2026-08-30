import uuid
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import (
    String,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    JSON, Integer, Text,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.models.enums import DocumentType, DocumentProcessingStatus

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.user import User


class Document(Base):
    """
    Immutable raw document record preserving evidentiary hash and storage reference.
    """
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "file_hash", name="uq_documents_org_file_hash"),
        UniqueConstraint("organization_id", "document_code", name="uq_documents_org_document_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="document_type"),
        nullable=False
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    source_channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="WEB_UPLOAD"
    )
    source_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    raw_extraction: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        SAEnum(DocumentProcessingStatus, name="document_processing_status"),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED,
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    matching_results: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    confidence_scores: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    candidate_transaction: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    review_flags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    failure_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    uploader: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<Document {self.document_code} - {self.file_name} ({self.document_type.value})>"


class ProjectDocumentLink(Base):
    """Many-to-many link between projects and contracts/documents."""
    __tablename__ = "project_document_links"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )


class TransactionDocumentLink(Base):
    """Many-to-many link between transactions and evidentiary documents."""
    __tablename__ = "transaction_document_links"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )


class DocumentCorrection(Base):
    """Append-only reviewer correction; source document bytes remain immutable."""
    __tablename__ = "document_corrections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True)
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    old_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
