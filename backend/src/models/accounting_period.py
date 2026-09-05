import uuid
from typing import Optional
from datetime import date, datetime
from sqlalchemy import (
    String,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SAEnum,
    func
)
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from src.models.enums import AccountingPeriodStatus


class AccountingPeriod(Base):
    """
    Accounting period boundary management (e.g. Monthly / Yearly fiscal cutoffs).
    Controls whether transactions can be posted.
    """
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_name", name="uq_period_org_name"),
        Index("ix_period_org_dates", "organization_id", "start_date", "end_date"),
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
    period_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    status: Mapped[AccountingPeriodStatus] = mapped_column(
        SAEnum(AccountingPeriodStatus, name="accounting_period_status", create_type=False),
        nullable=False,
        default=AccountingPeriodStatus.OPEN
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
