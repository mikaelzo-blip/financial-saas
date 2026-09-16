import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import DocumentType, DocumentProcessingStatus


class SafeJobFailure(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_type: str
    failure_message: Optional[str] = None
    attempt_count: int = 0
    failed_at: Optional[datetime] = None


class QueueHealth(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pending_count: int = 0
    running_count: int = 0
    failed_count: int = 0
    completed_count: int = 0
    retrying_count: int = 0
    oldest_pending_seconds: Optional[int] = None
    oldest_running_seconds: Optional[int] = None
    near_max_attempts_count: int = 0
    latest_failure: Optional[SafeJobFailure] = None


class DocumentOperationsSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status_counts: Dict[str, int] = Field(default_factory=dict)
    flag_counts: Dict[str, int] = Field(default_factory=dict)
    integrity_flags: Dict[str, int] = Field(default_factory=dict)
    queue_health: QueueHealth
    actionable_counts: Dict[str, int] = Field(default_factory=dict)


class DocumentOperationalItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    document_code: str
    file_name: str
    file_hash: Optional[str] = None
    file_size_bytes: int
    source_channel: str
    document_type: DocumentType
    received_at: datetime
    updated_at: datetime
    processing_status: DocumentProcessingStatus
    review_flags: List[str] = Field(default_factory=list)
    counterparty_name: Optional[str] = None
    counterparty_id: Optional[uuid.UUID] = None
    project_name: Optional[str] = None
    project_code: Optional[str] = None
    project_id: Optional[uuid.UUID] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = "IDR"
    processing_attempts: int = 0
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    age_seconds: int = 0
    age_display: str = "0m"
    is_stuck: bool = False
    converted_transaction_id: Optional[uuid.UUID] = None
    converted_transaction_code: Optional[str] = None
    posting_job_status: Optional[str] = None
    can_review: bool = False
    can_retry: bool = False
    can_post: bool = False


class DocumentOperationalListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[DocumentOperationalItem]
    total: int
    page: int
    limit: int
    pages: int
    total_pages: int = 1
