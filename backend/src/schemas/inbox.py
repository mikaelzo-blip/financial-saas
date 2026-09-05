import uuid
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from src.models.enums import InboxMessageStatus, SessionMatchStatus


class InboxAttachmentResponse(BaseModel):
    id: uuid.UUID
    inbox_message_id: uuid.UUID
    file_name: str
    mime_type: str
    size_bytes: int
    file_hash_sha256: str
    document_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InboxMessageResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    external_message_id: str
    sender_phone: str
    sender_name: Optional[str] = None
    caption: Optional[str] = None
    status: InboxMessageStatus
    received_at: datetime
    synced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    attachments: List[InboxAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RemoteInboxPayload(BaseModel):
    external_message_id: str
    sender_phone: str
    sender_name: Optional[str] = None
    caption: Optional[str] = None
    received_at: datetime
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_content_base64: Optional[str] = None
    file_hash_sha256: Optional[str] = None


class MatchEvidenceResponse(BaseModel):
    id: uuid.UUID
    evidence_type: str
    rule_name: str
    score: Decimal
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentSessionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    session_code: str
    status: SessionMatchStatus
    inbox_message_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    transaction_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    evidences: List[MatchEvidenceResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
