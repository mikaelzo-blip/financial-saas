import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

from src.models.enums import ReconciliationStatus, StatementImportStatus


class BankStatementLineCreate(BaseModel):
    line_number: int
    transaction_date: date
    description: str
    debit: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0)
    balance: Optional[Decimal] = None
    reference: Optional[str] = None
    counterparty_name: Optional[str] = None


class BankStatementLineResponse(BaseModel):
    id: uuid.UUID
    import_id: uuid.UUID
    organization_id: uuid.UUID
    line_number: int
    transaction_date: date
    description: str
    debit: Decimal
    credit: Decimal
    balance: Optional[Decimal] = None
    reference: Optional[str] = None
    counterparty_name: Optional[str] = None
    reconciliation_status: ReconciliationStatus

    model_config = ConfigDict(from_attributes=True)


class BankStatementImportCreate(BaseModel):
    payment_account_id: uuid.UUID
    source_file: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    lines: List[BankStatementLineCreate] = []


class BankStatementImportResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    payment_account_id: uuid.UUID
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    file_hash: str
    source_file: str
    imported_at: datetime
    status: StatementImportStatus
    line_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class BankReconciliationMatchRequest(BaseModel):
    statement_line_id: uuid.UUID
    journal_line_id: Optional[uuid.UUID] = None
    money_movement_id: Optional[uuid.UUID] = None
    transaction_id: Optional[uuid.UUID] = None
    matched_amount: Decimal = Field(gt=0)
    notes: Optional[str] = None


class CashCompletenessDashboardResponse(BaseModel):
    payment_account_id: Optional[uuid.UUID] = None
    total_bank_inflow: Decimal
    total_bank_outflow: Decimal
    matched_amount: Decimal
    unmatched_bank_amount: Decimal
    unmatched_book_amount: Decimal
    unallocated_cash_total: Decimal
    completeness_percentage: Decimal
