import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.models.enums import DocumentType


class DocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    document_code: str
    document_type: DocumentType
    file_name: str
    mime_type: str
    file_size_bytes: int
    file_hash: str
    source_channel: str
    source_metadata: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
