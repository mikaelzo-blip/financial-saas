import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CounterpartyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_customer: bool = False
    is_vendor: bool = False
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=1000)
    npwp: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_role(self):
        if not self.is_customer and not self.is_vendor:
            raise ValueError("Counterparty must be a customer, vendor, or both")
        return self


class CounterpartyResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    is_customer: bool
    is_vendor: bool
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    npwp: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)