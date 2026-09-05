import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import (
    String,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    JSON,
    Text,
    func
)
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base


class BackgroundJob(Base):
    """
    Persistent background job queue in PostgreSQL for safe local asynchronous processing
    (e.g. document analysis backlog, batch extraction, sync retries).
    Does not require Redis on Windows PC.
    """
    __tablename__ = "background_jobs"
    __table_args__ = (
        Index("ix_jobs_status_available", "status", "available_at"),
        Index("ix_jobs_org_type", "organization_id", "job_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    job_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
