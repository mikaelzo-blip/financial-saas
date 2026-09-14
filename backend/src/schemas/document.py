import uuid
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    line_total: Optional[Decimal] = None

    @model_validator(mode="after")
    def sync_amount_and_line_total(self) -> "LineItem":
        if self.line_total is None and self.amount is not None:
            object.__setattr__(self, "line_total", self.amount)
        elif self.amount is None and self.line_total is not None:
            object.__setattr__(self, "amount", self.line_total)
        return self


class ExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any = None
    confidence: Decimal = Field(ge=0, le=1)
    evidence: Optional[str] = None
    validation_status: str = Field(pattern="^(VALID|AMBIGUOUS|INVALID|MISSING)$")


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
    field_evidence: Dict[str, ExtractedField] = Field(default_factory=dict)


class TransactionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    proposed_transaction_type: Optional[TransactionType] = None
    counterparty_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    payment_account_id: Optional[uuid.UUID] = None
    allocation_target_id: Optional[uuid.UUID] = None
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


class DocumentRejectionRequest(BaseModel):
    reason: str = Field(min_length=3)


class DocumentCorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    document_id: uuid.UUID
    field_path: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    reason: str
    corrected_by: uuid.UUID
    corrected_at: datetime


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
    processing_attempts: int = 0
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    matching_results: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, Any] = Field(default_factory=dict)
    candidate_transaction: Dict[str, Any] = Field(default_factory=dict)
    review_flags: List[str] = Field(default_factory=list)
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    corrections: List[DocumentCorrectionResponse] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def prevent_lazy_load_corrections(cls, data: Any) -> Any:
        try:
            from sqlalchemy import inspect as sa_inspect
            insp = sa_inspect(data, raiseerr=False)
            if insp is not None and "corrections" in insp.unloaded:
                data.__dict__["corrections"] = []
        except Exception:
            pass
        return data

    model_config = ConfigDict(from_attributes=True)
