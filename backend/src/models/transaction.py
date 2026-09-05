import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING
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
    Index,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base, TimestampMixin
from src.models.enums import (
    TransactionType,
    WorkflowStatus,
    CostCategory,
    ExpenseCategory,
    ReviewFlag
)

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.counterparty import Counterparty
    from src.models.coa import PaymentAccount
    from src.models.user import User
    from src.models.project import Project


class Transaction(Base, TimestampMixin):
    """
    Transaction Candidate / Business Event.
    Represents a single financial event captured once.
    """
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("organization_id", "transaction_code", name="uq_transactions_org_code"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        Index("ix_transactions_org_date", "organization_id", "transaction_date"),
        Index("ix_transactions_org_status", "organization_id", "workflow_status"),
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
    transaction_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, name="transaction_type"),
        nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="IDR"
    )
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        SAEnum(WorkflowStatus, name="workflow_status"),
        nullable=False,
        default=WorkflowStatus.STAGED
    )
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    payment_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    destination_payment_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    reference_no: Mapped[Optional[str]] = mapped_column(

        String(100),
        nullable=True
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    source_channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="WEB"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    reversal_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True
    )
    retention_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.0000")
    )
    retention_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    counterparty: Mapped[Optional["Counterparty"]] = relationship("Counterparty")
    payment_account: Mapped[Optional["PaymentAccount"]] = relationship("PaymentAccount", foreign_keys=[payment_account_id])
    destination_payment_account: Mapped[Optional["PaymentAccount"]] = relationship("PaymentAccount", foreign_keys=[destination_payment_account_id])
    allocations: Mapped[List["TransactionAllocation"]] = relationship(

        "TransactionAllocation",
        back_populates="transaction",
        cascade="all, delete-orphan"
    )
    review_flags: Mapped[List["TransactionReviewFlag"]] = relationship(
        "TransactionReviewFlag",
        back_populates="transaction",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_code} - {self.transaction_type.value} Rp {self.amount} ({self.workflow_status.value})>"


class TransactionAllocation(Base):
    """
    Project / Overhead cost allocation for a single transaction.
    Supports single-project default and multi-project splitting.
    """
    __tablename__ = "transaction_allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_allocations_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    cost_category: Mapped[Optional[CostCategory]] = mapped_column(
        SAEnum(CostCategory, name="cost_category"),
        nullable=True
    )
    expense_category: Mapped[Optional[ExpenseCategory]] = mapped_column(
        SAEnum(ExpenseCategory, name="expense_category"),
        nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="allocations"
    )
    project: Mapped[Optional["Project"]] = relationship("Project")


class TransactionReviewFlag(Base):
    """
    Flags raised by validation, OCR, or duplicate detection routing transaction to review queue.
    """
    __tablename__ = "transaction_review_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    flag: Mapped[ReviewFlag] = mapped_column(
        SAEnum(ReviewFlag, name="review_flag"),
        nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="WARNING"
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="review_flags"
    )
