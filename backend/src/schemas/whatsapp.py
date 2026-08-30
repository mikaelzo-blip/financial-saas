"""Validated channel DTOs; no accounting instructions accepted."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Phone = str
Role = Literal["OPERATOR", "PROJECT_MANAGER", "FINANCE_MANAGER"]


class SenderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    phone_number: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    display_name: str = Field(min_length=1, max_length=128)
    role_in_org: Role


class SenderResponse(SenderCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime


class InboundMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wamid: str = Field(min_length=1, max_length=128)
    sender_phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    timestamp: datetime
    message_type: Literal["TEXT", "IMAGE", "DOCUMENT", "INTERACTIVE_REPLY"]
    text: str = Field(default="", max_length=4096)
    media_id: str | None = Field(default=None, max_length=128)
    mime_type: str | None = None
    file_name: str = Field(default="document", max_length=255)
    reply_to: str | None = None


class OutboundMessage(BaseModel):
    recipient_phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    body_text: str = Field(min_length=1, max_length=4096)
    buttons: list[dict[str, str]] = Field(default_factory=list, max_length=3)
