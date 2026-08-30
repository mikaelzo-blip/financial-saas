import uuid
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import (DocumentType, DocumentProcessingStatus, TransactionType,
                              CostCategory, ExpenseCategory, CandidateStatus)


class ConfidenceScores(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocr_confidence: Decimal = Field(ge=0, le=1)
    document_type_confidence: Decimal = Field(ge=0, le=1)
    entity_confidence: Decimal = Field(ge=0, le=1)
    project_confidence: Decimal = Field(ge=0, le=1)
    amount_confidence: Decimal = Field(ge=0, le=1)


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    amount: Optional[Decimal] = None


class StructuredExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_number: Optional[str] = None
    invoice_number: Optional[str] = None
    spk_number: Optional[str] = None
    bast_number: Optional[str] = None
    transaction_date: Optional[date] = None
    due_date: Optional[date] = None
    issuer_name: Optional[str] = None
    recipient_name: Optional[str] = None
    description: Optional[str] = None
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    subtotal: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    withholding_amount: Optional[Decimal] = None
    admin_fee: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    origin_bank: Optional[str] = None
    destination_bank: Optional[str] = None
    destination_account_number: Optional[str] = None
    destination_account_name: Optional[str] = None
    transfer_reference: Optional[str] = None
    project_reference: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    raw_text: Optional[str] = None
    field_evidence: Dict[str, Any] = Field(default_factory=dict)


class TransactionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    proposed_transaction_type: Optional[TransactionType] = None
    counterparty_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    payment_account_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    transaction_date: Optional[date] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    description: Optional[str] = None
    external_reference: Optional[str] = None
    status: CandidateStatus = CandidateStatus.PROPOSED
    converted_transaction_id: Optional[uuid.UUID] = None


class DocumentCorrectionRequest(BaseModel):
    changes: Dict[str, Any]
    reason: str = Field(min_length=1)


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
    processing_status: DocumentProcessingStatus = DocumentProcessingStatus.UPLOADED
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    matching_results: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, Any] = Field(default_factory=dict)
    candidate_transaction: Dict[str, Any] = Field(default_factory=dict)
    review_flags: List[str] = Field(default_factory=list)
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
