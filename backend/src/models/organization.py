import uuid
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.counterparty import Counterparty
    from src.models.coa import ChartOfAccount, PaymentAccount
    from src.models.audit import AuditLog


class Organization(Base, TimestampMixin):
    """Represents a contractor company organization (tenant boundary)."""
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )
    legal_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )
    default_payment_term_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30
    )
    fiscal_year_start_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    counterparties: Mapped[List["Counterparty"]] = relationship(
        "Counterparty",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    chart_of_accounts: Mapped[List["ChartOfAccount"]] = relationship(
        "ChartOfAccount",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    payment_accounts: Mapped[List["PaymentAccount"]] = relationship(
        "PaymentAccount",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug} - {self.legal_name}>"
