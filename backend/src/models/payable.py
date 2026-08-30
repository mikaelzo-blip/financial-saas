import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
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


class VendorBill(Base, TimestampMixin):
    """
    Vendor invoice/bill tracking Accounts Payable sub-ledger.
    Outstanding balance is derived: total_amount - sum(allocations).
    """
    __tablename__ = "vendor_bills"
    __table_args__ = (
        UniqueConstraint("organization_id", "bill_code", name="uq_vendor_bills_org_code"),
        CheckConstraint("total_amount > 0", name="ck_vendor_bills_amount_positive"),
        Index("ix_vendor_bills_org_vendor", "organization_id", "vendor_id"),
        Index("ix_vendor_bills_due_date", "organization_id", "due_date"),
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
    bill_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    bill_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
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
    vendor: Mapped["Counterparty"] = relationship("Counterparty")
    project: Mapped[Optional["Project"]] = relationship("Project")
    allocations: Mapped[List["VendorPaymentAllocation"]] = relationship(
        "VendorPaymentAllocation",
        back_populates="bill",
        cascade="all, delete-orphan"
    )

    def calculate_paid_amount(self) -> Decimal:
        if "allocations" in self.__dict__ and self.allocations:
            return sum(a.allocated_amount for a in self.allocations)
        return Decimal("0.00")

    def calculate_outstanding_amount(self) -> Decimal:
        return self.total_amount - self.calculate_paid_amount()

    def __repr__(self) -> str:
        return f"<VendorBill {self.bill_code} Rp {self.total_amount} ({self.status})>"


class VendorPaymentAllocation(Base):
    """
    Allocation of a payment transaction against a specific vendor bill.
    Supports partial payments and 1-to-many / many-to-1 allocations.
    """
    __tablename__ = "vendor_payment_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="ck_vpa_amount_positive"),
        Index("ix_vpa_bill_id", "bill_id"),
        Index("ix_vpa_payment_trx_id", "payment_transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendor_bills.id", ondelete="CASCADE"),
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
    bill: Mapped["VendorBill"] = relationship(
        "VendorBill",
        back_populates="allocations"
    )
    payment_transaction: Mapped["Transaction"] = relationship("Transaction")


class VendorAdvance(Base, TimestampMixin):
    """
    Vendor Advance sub-ledger record.
    Tracks advance issuance, settlement consumption, and remaining balance.
    """
    __tablename__ = "vendor_advances"
    __table_args__ = (
        UniqueConstraint("organization_id", "advance_code", name="uq_vendor_advances_org_code"),
        CheckConstraint("original_amount > 0", name="ck_vendor_advances_orig_positive"),
        CheckConstraint("settled_amount >= 0", name="ck_vendor_advances_settled_non_negative"),
        CheckConstraint("remaining_balance >= 0", name="ck_vendor_advances_rem_non_negative"),
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
    advance_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    advance_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    settled_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    remaining_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    vendor: Mapped["Counterparty"] = relationship("Counterparty")
    project: Mapped[Optional["Project"]] = relationship("Project")
    transaction: Mapped["Transaction"] = relationship("Transaction")

    def __repr__(self) -> str:
        return f"<VendorAdvance {self.advance_code} Orig: Rp {self.original_amount} Remaining: Rp {self.remaining_balance}>"
