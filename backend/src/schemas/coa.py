import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import AccountType, NormalBalance, CostCategory, ExpenseCategory


class ChartOfAccountCreate(BaseModel):
    account_code: str = Field(min_length=1, max_length=20, description="Account numeric code, e.g. 1101")
    account_name: str = Field(min_length=1, max_length=255, description="Account display name")
    account_type: AccountType
    normal_balance: NormalBalance
    report_group: str = Field(min_length=1, max_length=100, description="Financial reporting category")


class ChartOfAccountUpdate(BaseModel):
    account_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    report_group: Optional[str] = Field(default=None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class ChartOfAccountResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: AccountType
    normal_balance: NormalBalance
    report_group: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentAccountCreate(BaseModel):
    coa_account_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100, description="Display name e.g. Bank Mandiri Operasional")
    bank_name: Optional[str] = Field(default=None, max_length=100)
    account_number: Optional[str] = Field(default=None, max_length=100)


class PaymentAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    is_active: Optional[bool] = None


class PaymentAccountResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    coa_account_id: uuid.UUID
    coa_account_code: str
    coa_account_name: str
    account_type: AccountType
    name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryMetadataResponse(BaseModel):
    cost_categories: List[str]
    expense_categories: List[str]
