"""Transport-safe contracts shared by the Hermes API client and adapter."""
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import DocumentProcessingStatus


class HermesDocumentOutcome(BaseModel):
    """Minimal authoritative outcome retained by orchestration, never source bytes."""

    model_config = ConfigDict(extra="forbid")

    document_id: uuid.UUID
    document_code: str
    processing_status: DocumentProcessingStatus
    correlation_id: Optional[uuid.UUID] = None
    review_required: bool = False


class HermesSubmissionRequest(BaseModel):
    """Metadata for a logical submission; file bytes are passed only to the transport call."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=16, max_length=200)
