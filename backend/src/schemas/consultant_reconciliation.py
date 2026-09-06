from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DifferenceClassification(str, Enum):
    MATCH = "MATCH"
    MAPPING_DIFFERENCE = "MAPPING_DIFFERENCE"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    FISCAL_DIFFERENCE = "FISCAL_DIFFERENCE"
    MISSING_DATA = "MISSING_DATA"
    SYSTEM_DEFECT = "SYSTEM_DEFECT"
    CONSULTANT_REPORT_DIFFERENCE = "CONSULTANT_REPORT_DIFFERENCE"


class LineItemComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_key: str
    label_id: str
    label_en: str
    consultant_amount: Decimal
    saas_amount: Decimal
    variance: Decimal
    classification: DifferenceClassification
    notes: Optional[str] = None


class ConsultantIntegrityAudit(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_balanced: bool
    assets_liabilities_equity_discrepancy: Decimal
    pat_vs_current_earnings_discrepancy: Decimal
    findings: List[str] = Field(default_factory=list)


class ConsultantFinancialStatementData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    company_name: str = "PT SAMUDERA TERANG JAYA"
    source_document_name: Optional[str] = None

    # Profit & Loss items
    revenue: Decimal = Decimal("0.00")
    cogs: Decimal = Decimal("0.00")
    gross_profit: Decimal = Decimal("0.00")
    operating_expenses: Decimal = Decimal("0.00")
    operating_profit: Decimal = Decimal("0.00")
    other_income: Decimal = Decimal("0.00")
    other_expenses: Decimal = Decimal("0.00")
    profit_before_tax: Decimal = Decimal("0.00")
    income_tax: Decimal = Decimal("0.00")
    profit_after_tax: Decimal = Decimal("0.00")

    # Balance Sheet items
    cash: Decimal = Decimal("0.00")
    bank: Decimal = Decimal("0.00")
    receivables: Decimal = Decimal("0.00")
    other_current_assets: Decimal = Decimal("0.00")
    inventory: Decimal = Decimal("0.00")
    fixed_assets_cost: Decimal = Decimal("0.00")
    accumulated_depreciation: Decimal = Decimal("0.00")
    total_assets: Decimal = Decimal("0.00")

    payables: Decimal = Decimal("0.00")
    tax_liabilities: Decimal = Decimal("0.00")
    long_term_liabilities: Decimal = Decimal("0.00")
    total_liabilities: Decimal = Decimal("0.00")

    capital: Decimal = Decimal("0.00")
    retained_earnings: Decimal = Decimal("0.00")
    current_year_earnings: Decimal = Decimal("0.00")
    total_equity: Decimal = Decimal("0.00")
    total_liabilities_equity: Decimal = Decimal("0.00")

    # Detailed OPEX breakdown (optional)
    expense_breakdown: Dict[str, Decimal] = Field(default_factory=dict)


class ConsultantReconciliationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_items_compared: int
    match_count: int
    difference_count: int
    missing_data_count: int
    consultant_defect_count: int
    net_pl_variance: Decimal
    net_bs_variance: Decimal


class ConsultantReconciliationReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID
    year: int
    as_of_date: date
    consultant_data: ConsultantFinancialStatementData
    statement_integrity: ConsultantIntegrityAudit
    pl_comparisons: List[LineItemComparison]
    bs_comparisons: List[LineItemComparison]
    summary: ConsultantReconciliationSummary
