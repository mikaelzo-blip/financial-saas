import uuid
from typing import Any, Dict, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.organization import Organization


class Counterparty(Base, TimestampMixin):
    """Represents an external entity (Customer, Vendor, Subcontractor, or Both)."""
    __tablename__ = "counterparties"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    is_customer: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    is_vendor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    contact_info: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    bank_accounts: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="counterparties"
    )

    def __repr__(self) -> str:
        roles = []
        if self.is_customer:
            roles.append("Customer")
        if self.is_vendor:
            roles.append("Vendor")
        return f"<Counterparty {self.name} [{' / '.join(roles) if roles else 'Unassigned'}]>"
