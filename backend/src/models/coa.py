import uuid
from typing import List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.core.database import Base
from src.models.enums import AccountType, NormalBalance

if TYPE_CHECKING:
    from src.models.organization import Organization


class ChartOfAccount(Base):
    """
    Chart of Accounts (COA) master entity.
    CRITICAL: Does NOT store running balances. All balances are derived from journal lines.
    """
    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_code", name="uq_coa_org_account_code"),
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
    account_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, name="account_type"),
        nullable=False
    )
    normal_balance: Mapped[NormalBalance] = mapped_column(
        SAEnum(NormalBalance, name="normal_balance"),
        nullable=False
    )
    report_group: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="chart_of_accounts"
    )
    payment_accounts: Mapped[List["PaymentAccount"]] = relationship(
        "PaymentAccount",
        back_populates="coa_account",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<COA {self.account_code} - {self.account_name} ({self.account_type.value})>"


class PaymentAccount(Base):
    """
    Operational cash / bank account (e.g. Mandiri, BCA, Petty Cash, Cash).
    Maps to parent COA account (typically 1101 Kas dan Bank).
    """
    __tablename__ = "payment_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    coa_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    account_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="payment_accounts"
    )
    coa_account: Mapped["ChartOfAccount"] = relationship(
        "ChartOfAccount",
        back_populates="payment_accounts"
    )

    def __repr__(self) -> str:
        return f"<PaymentAccount {self.name} -> COA {self.coa_account_id}>"

    @property
    def coa_account_code(self) -> str:
        return self.coa_account.account_code

    @property
    def coa_account_name(self) -> str:
        return self.coa_account.account_name

    @property
    def account_type(self) -> AccountType:
        return self.coa_account.account_type
