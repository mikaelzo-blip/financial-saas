import uuid
from decimal import Decimal
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from src.models.enums import (
    MovementDirection,
    MovementSourceType,
    SettlementType,
    CostCategory
)


class SettlementAllocationCreate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(gt=0)
    cost_category: Optional[CostCategory] = None
    notes: Optional[str] = None


class SettlementAllocationResponse(BaseModel):
    id: uuid.UUID
    settlement_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    amount: Decimal
    cost_category: Optional[CostCategory] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SettlementCreate(BaseModel):
    transaction_id: Optional[uuid.UUID] = None
    settlement_type: SettlementType
    amount: Decimal = Field(gt=0)
    notes: Optional[str] = None
    allocations: List[SettlementAllocationCreate] = Field(default_factory=list)


class SettlementResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    settlement_code: str
    money_movement_id: uuid.UUID
    transaction_id: Optional[uuid.UUID] = None
    settlement_type: SettlementType
    amount: Decimal
    notes: Optional[str] = None
    allocations: List[SettlementAllocationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MoneyMovementCreate(BaseModel):
    payment_account_id: uuid.UUID
    direction: MovementDirection
    amount: Decimal = Field(gt=0)
    movement_date: date
    source_type: MovementSourceType
    reference_no: Optional[str] = None
    description: Optional[str] = None
    settlements: List[SettlementCreate] = Field(default_factory=list)


class MoneyMovementResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    movement_code: str
    payment_account_id: uuid.UUID
    direction: MovementDirection
    amount: Decimal
    movement_date: date
    source_type: MovementSourceType
    reference_no: Optional[str] = None
    description: Optional[str] = None
    settlements: List[SettlementResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
