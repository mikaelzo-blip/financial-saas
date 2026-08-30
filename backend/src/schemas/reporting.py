from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
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
    compare_with: Optional[str] = None
    project_id: Optional[str] = None


class GeneralLedgerQuery(BaseModel):
    account_code: str
    start_date: date
    end_date: date
    project_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


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
    lines: List[ReportLineItem] = []
    subtotal: Decimal = Decimal("0.00")
    comparative_subtotal: Optional[Decimal] = None


# Profit & Loss
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


# Balance Sheet
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
    integrity_status: str  # "VALID" | "INTEGRITY_ERROR"


# Trial Balance
class TrialBalanceLine(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    ending_debit: Decimal
    ending_credit: Decimal


class TrialBalanceResponse(BaseModel):
    organization_name: str
    as_of_date: date
    start_date: date
    end_date: date
    lines: List[TrialBalanceLine] = []
    total_opening_debit: Decimal = Decimal("0.00")
    total_opening_credit: Decimal = Decimal("0.00")
    total_period_debit: Decimal = Decimal("0.00")
    total_period_credit: Decimal = Decimal("0.00")
    total_ending_debit: Decimal = Decimal("0.00")
    total_ending_credit: Decimal = Decimal("0.00")
    is_balanced: bool = True
    difference: Decimal = Decimal("0.00")


# General Ledger
class GeneralLedgerEntry(BaseModel):
    date: date
    journal_entry_id: str
    journal_entry_number: str
    transaction_id: Optional[str] = None
    description: str
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    document_ids: List[str] = []


class GeneralLedgerResponse(BaseModel):
    organization_name: str
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    start_date: date
    end_date: date
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    entries: List[GeneralLedgerEntry] = []
    total_records: int
    page: int
    page_size: int


# Integrity Diagnostics
class IntegrityCheckItem(BaseModel):
    check_name: str
    status: str  # "PASS" | "FAIL"
    left_value: Decimal
    right_value: Decimal
    discrepancy: Decimal
    message: str


class IntegrityReportResponse(BaseModel):
    organization_name: str
    as_of_date: date
    overall_status: str  # "VALID" | "INTEGRITY_ERROR"
    checks: List[IntegrityCheckItem] = []


# Cash Flow (Direct Method)
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


# AR Aging
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
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    invoice_number: str
    invoice_date: date
    due_date: date
    days_overdue: int
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    bucket: str  # "CURRENT", "1_30", "31_60", "61_90", "OVER_90"


class ARAgingReportResponse(BaseModel):
    organization_name: str
    as_of_date: date
    summary: AgingBucketSummary
    invoices: List[ARAgingInvoiceLine] = []


# AP Aging
class APAgingBillLine(BaseModel):
    vendor_id: str
    vendor_name: str
    project_code: Optional[str] = None
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
    organization_name: str
    as_of_date: date
    summary: AgingBucketSummary
    bills: List[APAgingBillLine] = []
    unsettled_advances_total: Decimal = Decimal("0.00")


# Project Profitability
class ProjectCostCategoryLine(BaseModel):
    cost_category: str  # "MAT", "SUB", etc.
    category_name: str
    amount: Decimal


class ProjectProfitabilityReportResponse(BaseModel):
    organization_name: str
    project_id: str
    project_code: str
    project_name: str
    client_name: Optional[str] = None
    status: str
    original_contract_value: Decimal
    variation_orders_value: Decimal
    revised_contract_value: Decimal
    revenue_recognized: Decimal
    cost_breakdown: List[ProjectCostCategoryLine] = []
    total_project_cost: Decimal
    gross_profit: Decimal
    gross_margin_percentage: Decimal


# Project Cash Position
class ProjectCashPositionReportResponse(BaseModel):
    organization_name: str
    project_id: str
    project_code: str
    project_name: str
    invoiced_amount: Decimal
    cash_received: Decimal
    receivable_outstanding: Decimal
    cash_spent: Decimal
    net_cash_position: Decimal
    is_surplus: bool
    notice_message: str = "Laba Proyek (Akrual) Berbeda dengan Posisi Kas Proyek (Likuiditas)."


# Budget vs Actual
class BudgetVsActualLine(BaseModel):
    cost_category: str
    category_name: str
    budget_amount: Decimal
    actual_amount: Decimal
    variance_amount: Decimal
    variance_percentage: Decimal
    status: str  # "NORMAL", "WARNING", "OVERBUDGET"


class BudgetVsActualReportResponse(BaseModel):
    organization_name: str
    project_id: str
    project_code: str
    project_name: str
    has_budget: bool
    budget_status_label: str
    total_budget: Decimal
    total_actual: Decimal
    total_variance: Decimal
    consumption_percentage: Decimal
    lines: List[BudgetVsActualLine] = []


# Executive Management Dashboard
class DashboardSummaryResponse(BaseModel):
    organization_name: str
    as_of_date: date
    cash_and_bank_balance: Decimal
    accounts_receivable_outstanding: Decimal
    accounts_payable_outstanding: Decimal
    revenue_ytd: Decimal
    net_profit_ytd: Decimal
    estimated_monthly_burn_rate: Decimal
    cash_runway_months: Optional[Decimal] = None
    active_projects_count: int
    review_queue_pending_count: int
    integrity_status: str  # "VALID" | "INTEGRITY_ERROR"


