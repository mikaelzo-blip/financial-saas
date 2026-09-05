import uuid
from typing import Optional
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
    Enum as SAEnum,
    func
)
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from src.models.enums import DepreciationMethod, AssetStatus


class FixedAsset(Base):
    """
    Fixed Asset register for tracking capital assets, useful life, and depreciation.
    Does not assume depreciation policy; reflects consultant or explicit policy.
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
        nullable=False,
        index=True
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
        SAEnum(DepreciationMethod, name="depreciation_method", create_type=False),
        nullable=False,
        default=DepreciationMethod.STRAIGHT_LINE
    )
    accumulated_depreciation: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus, name="asset_status", create_type=False),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
