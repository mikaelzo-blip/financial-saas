import uuid
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    DateTime,
    Numeric,
    Integer,
    ForeignKey,
    Index,
    UniqueConstraint,
    Enum as SAEnum,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.database import Base
from src.models.enums import DepreciationMethod, AssetStatus


class FixedAsset(Base):
    """
    Fixed Asset register for tracking capital assets, useful life, and depreciation.
    Enforces SAK EP-oriented straight-line book depreciation with start date at available-for-use.
    """
    __tablename__ = "fixed_assets"
    __table_args__ = (
        Index("ix_fixed_assets_org", "organization_id"),
        Index("ix_fixed_assets_category", "organization_id", "asset_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    asset_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True
    )
    asset_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    asset_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    purchase_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    available_for_use_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    purchase_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    salvage_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    useful_life_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    depreciation_method: Mapped[DepreciationMethod] = mapped_column(
        SAEnum(DepreciationMethod, native_enum=False, length=50),
        nullable=False,
        default=DepreciationMethod.STRAIGHT_LINE
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus, native_enum=False, length=50),
        nullable=False,
        default=AssetStatus.ACTIVE
    )
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("counterparties.id", ondelete="SET NULL"),
        nullable=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True
    )
    asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="SET NULL"),
        nullable=True
    )
    depreciation_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="SET NULL"),
        nullable=True
    )

    # Optional / Future-safe Fiscal Depreciation fields
    fiscal_asset_group: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    fiscal_depreciation_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    fiscal_useful_life_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    depreciations: Mapped[List["FixedAssetDepreciation"]] = relationship(
        "FixedAssetDepreciation",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="FixedAssetDepreciation.period_date.desc()"
    )

    @property
    def effective_available_date(self) -> date:
        return self.available_for_use_date or self.purchase_date

    @property
    def net_book_value(self) -> Decimal:
        return self.purchase_cost - self.accumulated_depreciation

    @property
    def depreciable_amount(self) -> Decimal:
        diff = self.purchase_cost - (self.salvage_value or Decimal("0.00"))
        return max(Decimal("0.00"), diff)

    @property
    def remaining_depreciable_amount(self) -> Decimal:
        return max(Decimal("0.00"), self.depreciable_amount - self.accumulated_depreciation)

    @property
    def monthly_depreciation_rate(self) -> Decimal:
        if self.useful_life_months <= 0:
            return Decimal("0.00")
        return (self.depreciable_amount / Decimal(self.useful_life_months)).quantize(Decimal("0.01"))


class FixedAssetDepreciation(Base):
    """
    Immutable audit record for periodic straight-line depreciation runs.
    Linked to double-entry journal entry and transaction.
    """
    __tablename__ = "fixed_asset_depreciations"
    __table_args__ = (
        Index("ix_asset_depr_org", "organization_id"),
        Index("ix_asset_depr_asset", "asset_id"),
        UniqueConstraint("asset_id", "period_date", name="uq_asset_depr_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixed_assets.id", ondelete="CASCADE"),
        nullable=False
    )
    period_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    depreciation_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    accumulated_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    book_value_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True
    )
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    asset: Mapped["FixedAsset"] = relationship(
        "FixedAsset",
        back_populates="depreciations"
    )
