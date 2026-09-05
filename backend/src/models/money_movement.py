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
    Enum as SAEnum,
    Text,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.models.enums import (

    MovementDirection,
    MovementSourceType,
    SettlementType,
    CostCategory
)


class MoneyMovement(Base):
    __tablename__ = "money_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    movement_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True
    )
    payment_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    direction: Mapped[MovementDirection] = mapped_column(
        SAEnum(MovementDirection, name="movement_direction", create_type=False),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    movement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    source_type: Mapped[MovementSourceType] = mapped_column(
        SAEnum(MovementSourceType, name="movement_source_type", create_type=False),
        nullable=False
    )
    reference_no: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    settlements: Mapped[List["Settlement"]] = relationship(
        "Settlement",
        back_populates="money_movement",
        cascade="all, delete-orphan"
    )


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    settlement_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True
    )
    money_movement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("money_movements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    settlement_type: Mapped[SettlementType] = mapped_column(
        SAEnum(SettlementType, name="settlement_type", create_type=False),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    money_movement: Mapped["MoneyMovement"] = relationship(
        "MoneyMovement",
        back_populates="settlements"
    )
    allocations: Mapped[List["SettlementAllocation"]] = relationship(
        "SettlementAllocation",
        back_populates="settlement",
        cascade="all, delete-orphan"
    )


class SettlementAllocation(Base):
    __tablename__ = "settlement_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    settlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("settlements.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    cost_category: Mapped[Optional[CostCategory]] = mapped_column(
        SAEnum(CostCategory, name="cost_category", create_type=False),
        nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    settlement: Mapped["Settlement"] = relationship(
        "Settlement",
        back_populates="allocations"
    )
