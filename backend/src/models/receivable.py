import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.counterparty import Counterparty
    from src.models.project import Project
    from src.models.transaction import Transaction


class CustomerInvoice(Base, TimestampMixin):
    """
    Customer Invoice tracking Accounts Receivable sub-ledger.
    Due date is determined by explicit date, customer terms, or organization default.
    """
    __tablename__ = "customer_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_code", name="uq_customer_invoices_org_code"),
        CheckConstraint("total_amount > 0", name="ck_customer_invoices_amount_positive"),
        Index("ix_customer_invoices_org_customer", "organization_id", "customer_id"),
        Index("ix_customer_invoices_due_date", "organization_id", "due_date"),
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
    invoice_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    invoice_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    due_date_override_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="UNPAID"
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    customer: Mapped["Counterparty"] = relationship("Counterparty")
    project: Mapped["Project"] = relationship("Project")
    allocations: Mapped[List["CustomerPaymentAllocation"]] = relationship(
        "CustomerPaymentAllocation",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    def calculate_paid_amount(self) -> Decimal:
        if "allocations" in self.__dict__ and self.allocations:
            return sum(a.allocated_amount for a in self.allocations)
        return Decimal("0.00")

    def calculate_outstanding_amount(self) -> Decimal:
        if self.status == "CANCELLED":
            return Decimal("0.00")
        return self.total_amount - self.calculate_paid_amount()

    def __repr__(self) -> str:
        return f"<CustomerInvoice {self.invoice_code} Rp {self.total_amount} ({self.status})>"


class CustomerPaymentAllocation(Base):
    """
    Allocation of a payment transaction against a specific customer invoice.
    Supports partial payments and 1-to-many / many-to-1 allocations.
    """
    __tablename__ = "customer_payment_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="ck_cpa_amount_positive"),
        Index("ix_cpa_invoice_id", "invoice_id"),
        Index("ix_cpa_payment_trx_id", "payment_transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    payment_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    invoice: Mapped["CustomerInvoice"] = relationship(
        "CustomerInvoice",
        back_populates="allocations"
    )
    payment_transaction: Mapped["Transaction"] = relationship("Transaction")
