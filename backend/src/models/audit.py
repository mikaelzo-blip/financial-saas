import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.user import User


class AuditLog(Base):
    """
    Append-only immutable audit trail recording critical state changes.
    Never permits updates or deletes.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_entity", "organization_id", "entity_name", "entity_id"),
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
    entity_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="audit_logs"
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User"
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.entity_name}:{self.entity_id} at {self.timestamp}>"
