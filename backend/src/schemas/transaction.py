import uuid
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import (
    TransactionType,
    WorkflowStatus,
    CostCategory,
    ExpenseCategory,
    ReviewFlag
)


class TransactionAllocationInput(BaseModel):
    project_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    amount: Decimal = Field(gt=0, description="Allocation amount")
    notes: Optional[str] = None


TransactionAllocationCreate = TransactionAllocationInput


class TransactionAllocationResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    amount: Decimal
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionReviewFlagResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    flag: ReviewFlag
    severity: str
    message: str
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    transaction_type: TransactionType
    transaction_date: date
    amount: Decimal = Field(gt=0, description="Total transaction amount")
    currency: str = Field(default="IDR", max_length=3)
    counterparty_id: Optional[uuid.UUID] = None
    payment_account_id: Optional[uuid.UUID] = None
    reference_no: Optional[str] = None
    description: str = Field(min_length=1)
    source_channel: str = "WEB"
    document_ids: List[uuid.UUID] = Field(default_factory=list)

    # Single-project convenience fields (auto-generates 1 allocation)
    project_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None

    # Multi-project explicit split allocations
    allocations: Optional[List[TransactionAllocationInput]] = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    transaction_code: str
    transaction_type: TransactionType
    transaction_date: date
    amount: Decimal
    currency: str
    workflow_status: WorkflowStatus
    counterparty_id: Optional[uuid.UUID] = None
    payment_account_id: Optional[uuid.UUID] = None
    reference_no: Optional[str] = None
    description: str
    source_channel: str
    created_by: Optional[uuid.UUID] = None
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    reversal_of_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    allocations: List[TransactionAllocationResponse] = []
    review_flags: List[TransactionReviewFlagResponse] = []

    model_config = ConfigDict(from_attributes=True)
