"""Persistence for safe, tenant-scoped Hermes request correlation."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.core.database import Base


class HermesSubmission(Base):
    """Idempotent machine intake correlation; it is not a financial record."""

    __tablename__ = "hermes_submissions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "operation", "idempotency_key_hash",
            name="uq_hermes_submissions_org_operation_key",
        ),
        Index("ix_hermes_submissions_org_document", "organization_id", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    outcome_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACCEPTED")
    safe_error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
