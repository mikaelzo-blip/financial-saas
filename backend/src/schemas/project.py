import uuid
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import ProjectStatus, BillingStatus, CollectionStatus, CostCategory


class ProjectBudgetCreate(BaseModel):
    cost_category: CostCategory
    budget_amount: Decimal = Field(ge=0, description="Budget allocation for this category")
    notes: Optional[str] = None


class ProjectBudgetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    cost_category: CostCategory
    budget_amount: Decimal
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    project_name: str = Field(min_length=1, max_length=255)
    customer_id: uuid.UUID
    po_spk_no: Optional[str] = None
    po_spk_date: Optional[date] = None
    original_contract_value: Decimal = Field(default=Decimal("0.00"), ge=0)
    start_date: date
    target_end_date: Optional[date] = None
    pic_user_id: Optional[uuid.UUID] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    po_spk_no: Optional[str] = None
    po_spk_date: Optional[date] = None
    target_end_date: Optional[date] = None
    pic_user_id: Optional[uuid.UUID] = None


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus
    actual_end_date: Optional[date] = None


class ProjectVariationOrderUpdate(BaseModel):
    variation_order_value: Decimal = Field(description="Addendum / Variation order value")


class ProjectResponse(BaseModel):
    id: uuid.UUID
    project_code: str
    project_name: str
    customer_id: uuid.UUID
    po_spk_no: Optional[str] = None
    po_spk_date: Optional[date] = None
    original_contract_value: Decimal
    variation_order_value: Decimal
    revised_contract_value: Decimal
    start_date: date
    target_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    pic_user_id: Optional[uuid.UUID] = None
    project_status: ProjectStatus
    billing_status: BillingStatus = BillingStatus.NOT_INVOICED
    collection_status: CollectionStatus = CollectionStatus.NOT_DUE
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
