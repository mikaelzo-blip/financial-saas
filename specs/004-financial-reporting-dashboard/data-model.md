# Reporting Data Model & View Models: Financial Reporting & Management Dashboard

**Feature Branch**: `004-financial-reporting-dashboard`  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)

---

## 1. Request Query Models

```python
from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ReportPeriodType(str, Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"

class FinancialReportQuery(BaseModel):
    period_type: ReportPeriodType = ReportPeriodType.MONTHLY
    start_date: date
    end_date: date
    compare_with: Optional[str] = None # "PREVIOUS_PERIOD" | "PREVIOUS_YEAR" | "BUDGET"
    project_id: Optional[str] = None

class GeneralLedgerQuery(BaseModel):
    account_code: str
    start_date: date
    end_date: date
    project_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
```

---

## 2. Financial Statement View Models (DTOs)

### A. Laporan Laba Rugi (Profit & Loss DTO)
```python
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel

class ReportLineItem(BaseModel):
    account_code: Optional[str] = None
    line_name: str
    amount: Decimal
    comparative_amount: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    variance_percentage: Optional[Decimal] = None
    drill_down_supported: bool = True

class ReportSection(BaseModel):
    section_code: str
    section_name: str
    lines: List[ReportLineItem]
    subtotal: Decimal
    comparative_subtotal: Optional[Decimal] = None

class ProfitLossReportResponse(BaseModel):
    organization_name: str
    period_label: str
    start_date: date
    end_date: date
    generated_at: str
    revenue_section: ReportSection
    cogs_section: ReportSection
    gross_profit: Decimal
    gross_margin_percentage: Decimal
    operating_expenses_section: ReportSection
    operating_profit: Decimal
    other_income_expense_section: ReportSection
    earnings_before_tax: Decimal
    tax_expense: Decimal
    net_profit: Decimal
```

---

### B. Laporan Neraca (Balance Sheet DTO)
```python
class BalanceSheetReportResponse(BaseModel):
    organization_name: str
    as_of_date: date
    generated_at: str
    current_assets: ReportSection
    fixed_assets: ReportSection
    total_assets: Decimal
    current_liabilities: ReportSection
    long_term_liabilities: ReportSection
    total_liabilities: Decimal
    equity: ReportSection
    total_equity: Decimal
    total_liabilities_and_equity: Decimal
    is_balanced: bool
    balancing_difference: Decimal
    integrity_status: str # "VALID" | "INTEGRITY_ERROR"
```

---

### C. Laporan Arus Kas (Cash Flow DTO - Direct Method)
```python
class CashFlowReportResponse(BaseModel):
    organization_name: str
    period_label: str
    start_date: date
    end_date: date
    opening_cash_balance: Decimal
    operating_activities: ReportSection
    net_operating_cash: Decimal
    investing_activities: ReportSection
    net_investing_cash: Decimal
    financing_activities: ReportSection
    net_financing_cash: Decimal
    net_cash_change: Decimal
    closing_cash_balance: Decimal
    unclassified_cash_activities: Optional[ReportSection] = None
```

---

### D. Neraca Saldo (Trial Balance DTO)
```python
class TrialBalanceLine(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    ending_debit: Decimal
    ending_credit: Decimal

class TrialBalanceResponse(BaseModel):
    as_of_date: date
    lines: List[TrialBalanceLine]
    total_opening_debit: Decimal
    total_opening_credit: Decimal
    total_period_debit: Decimal
    total_period_credit: Decimal
    total_ending_debit: Decimal
    total_ending_credit: Decimal
    is_balanced: bool
```

---

### E. Buku Besar (General Ledger DTO)
```python
class GeneralLedgerEntry(BaseModel):
    date: date
    journal_entry_id: str
    journal_entry_number: str
    transaction_id: Optional[str] = None
    transaction_code: Optional[str] = None
    description: str
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    document_ids: List[str] = []

class GeneralLedgerResponse(BaseModel):
    account_code: str
    account_name: str
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    entries: List[GeneralLedgerEntry]
    total_records: int
    page: int
    page_size: int
```

---

### F. Laporan Umur Piutang & Utang (AR/AP Aging DTO)
```python
class AgingBucketSummary(BaseModel):
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_over_90: Decimal
    total: Decimal

class ARAgingInvoiceLine(BaseModel):
    customer_id: str
    customer_name: str
    project_name: Optional[str] = None
    invoice_number: str
    invoice_date: date
    due_date: date
    days_overdue: int
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    bucket: str # "CURRENT", "1_30", "31_60", "61_90", "OVER_90"

class ARAgingReportResponse(BaseModel):
    as_of_date: date
    summary: AgingBucketSummary
    invoices: List[ARAgingInvoiceLine]

class APAgingBillLine(BaseModel):
    vendor_id: str
    vendor_name: str
    project_name: Optional[str] = None
    bill_number: str
    bill_date: date
    due_date: date
    days_overdue: int
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    bucket: str

class APAgingReportResponse(BaseModel):
    as_of_date: date
    summary: AgingBucketSummary
    bills: List[APAgingBillLine]
    unsettled_advances_total: Decimal
```
