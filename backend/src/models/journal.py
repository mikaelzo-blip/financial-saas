import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    DateTime,
    Numeric,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.models.enums import CostCategory, ExpenseCategory

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.transaction import Transaction
    from src.models.coa import ChartOfAccount
    from src.models.project import Project
    from src.models.counterparty import Counterparty


class JournalEntry(Base):
    """
    Immutable posted double-entry journal entry header.
    Guarantees Total Debit == Total Credit.
    """
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "entry_number", name="uq_je_org_entry_number"),
        CheckConstraint("total_debit > 0", name="ck_je_total_debit_positive"),
        CheckConstraint("total_credit > 0", name="ck_je_total_credit_positive"),
        CheckConstraint("total_debit = total_credit", name="ck_je_balanced"),
        Index("ix_je_org_posting_date", "organization_id", "posting_date"),
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
    entry_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True
    )
    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    total_debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    total_credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    is_balanced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    is_reversed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    reversal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    transaction: Mapped["Transaction"] = relationship("Transaction")
    lines: Mapped[List["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_number"
    )

    def __repr__(self) -> str:
        return f"<JournalEntry {self.entry_number} Date: {self.posting_date} Rp {self.total_debit} (Balanced={self.is_balanced})>"


class JournalLine(Base):
    """
    Individual debit or credit leg of a posted journal entry.
    Carries dimensional analysis tags (Project_ID, Counterparty, Cost Category).
    """
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="ck_jl_debit_non_negative"),
        CheckConstraint("credit_amount >= 0", name="ck_jl_credit_non_negative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_jl_one_sided_amount"
        ),
        Index("ix_jl_account_id", "account_id"),
        Index("ix_jl_project_id", "project_id"),
        Index("ix_jl_counterparty_id", "counterparty_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"),
        nullable=False
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True
    )
    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=True
    )
    cost_category: Mapped[Optional[CostCategory]] = mapped_column(
        SAEnum(CostCategory, name="cost_category"),
        nullable=True
    )
    expense_category: Mapped[Optional[ExpenseCategory]] = mapped_column(
        SAEnum(ExpenseCategory, name="expense_category"),
        nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry",
        back_populates="lines"
    )
    account: Mapped["ChartOfAccount"] = relationship("ChartOfAccount")
    project: Mapped[Optional["Project"]] = relationship("Project")
    counterparty: Mapped[Optional["Counterparty"]] = relationship("Counterparty")

    def __repr__(self) -> str:
        side = f"Dr {self.debit_amount}" if self.debit_amount > 0 else f"Cr {self.credit_amount}"
        return f"<JournalLine #{self.line_number} Acc: {self.account_id} {side}>"
