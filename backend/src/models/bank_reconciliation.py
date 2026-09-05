import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.enums import ReconciliationStatus, StatementImportStatus


class BankStatementImport(Base):
    __tablename__ = "bank_statement_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    payment_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    status: Mapped[StatementImportStatus] = mapped_column(
        String(50),
        default=StatementImportStatus.COMPLETED,
        nullable=False
    )

    lines: Mapped[List["BankStatementLine"]] = relationship(
        "BankStatementLine",
        back_populates="statement_import",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


    __table_args__ = (
        UniqueConstraint("organization_id", "file_hash", name="uq_bank_statement_import_file_hash"),
    )


class BankStatementLine(Base):
    __tablename__ = "bank_statement_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_statement_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reconciliation_status: Mapped[ReconciliationStatus] = mapped_column(
        String(50),
        default=ReconciliationStatus.UNMATCHED_BANK,
        nullable=False,
        index=True
    )

    statement_import: Mapped["BankStatementImport"] = relationship(
        "BankStatementImport",
        back_populates="lines"
    )
    reconciliations: Mapped[List["BankReconciliation"]] = relationship(
        "BankReconciliation",
        back_populates="statement_line",
        cascade="all, delete-orphan"
    )


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    statement_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_statement_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    journal_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("journal_lines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    money_movement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("money_movements.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    status: Mapped[ReconciliationStatus] = mapped_column(
        String(50),
        default=ReconciliationStatus.MATCHED,
        nullable=False
    )
    matched_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    match_rule: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    matched_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    statement_line: Mapped["BankStatementLine"] = relationship(
        "BankStatementLine",
        back_populates="reconciliations"
    )
