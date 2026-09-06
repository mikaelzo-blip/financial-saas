import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field

from src.models.enums import AccountingPeriodStatus


class AccountingPeriodBase(BaseModel):
    period_name: str = Field(..., max_length=50, description="Format: YYYY-MM e.g. 2026-01")
    start_date: date
    end_date: date


class AccountingPeriodCreate(AccountingPeriodBase):
    pass


class AccountingPeriodUpdate(BaseModel):
    status: AccountingPeriodStatus
    reason: Optional[str] = Field(None, description="Required when reopening a closed or soft-closed period")


class AccountingPeriodResponse(AccountingPeriodBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: AccountingPeriodStatus
    closed_at: Optional[datetime] = None
    closed_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}
