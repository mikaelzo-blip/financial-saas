export interface ReportLineItem {
  account_code?: string;
  line_name: string;
  amount: number | string;
  comparative_amount?: number | string | null;
  variance_amount?: number | string | null;
  variance_percentage?: number | string | null;
  drill_down_supported: boolean;
}

export interface ReportSection {
  section_code: string;
  section_name: string;
  lines: ReportLineItem[];
  subtotal: number | string;
  comparative_subtotal?: number | string | null;
}

export interface ProfitLossReportResponse {
  organization_name: string;
  period_label: string;
  start_date: string;
  end_date: string;
  generated_at: string;
  revenue_section: ReportSection;
  cogs_section: ReportSection;
  gross_profit: number | string;
  gross_margin_percentage: number | string;
  operating_expenses_section: ReportSection;
  operating_profit: number | string;
  other_income_expense_section: ReportSection;
  earnings_before_tax: number | string;
  tax_expense: number | string;
  net_profit: number | string;
}

export interface BalanceSheetReportResponse {
  organization_name: string;
  as_of_date: string;
  generated_at: string;
  current_assets: ReportSection;
  fixed_assets: ReportSection;
  total_assets: number | string;
  current_liabilities: ReportSection;
  long_term_liabilities: ReportSection;
  total_liabilities: number | string;
  equity: ReportSection;
  total_equity: number | string;
  total_liabilities_and_equity: number | string;
  is_balanced: boolean;
  balancing_difference: number | string;
  integrity_status: 'VALID' | 'INTEGRITY_ERROR';
}

export interface TrialBalanceLine {
  account_code: string;
  account_name: string;
  account_type: string;
  normal_balance: string;
  opening_debit: number | string;
  opening_credit: number | string;
  period_debit: number | string;
  period_credit: number | string;
  ending_debit: number | string;
  ending_credit: number | string;
}

export interface TrialBalanceResponse {
  organization_name: string;
  as_of_date: string;
  start_date: string;
  end_date: string;
  lines: TrialBalanceLine[];
  total_opening_debit: number | string;
  total_opening_credit: number | string;
  total_period_debit: number | string;
  total_period_credit: number | string;
  total_ending_debit: number | string;
  total_ending_credit: number | string;
  is_balanced: boolean;
  difference: number | string;
}

export interface GeneralLedgerEntry {
  date: string;
  journal_entry_id: string;
  journal_entry_number: string;
  transaction_id?: string | null;
  description: string;
  project_code?: string | null;
  project_name?: string | null;
  debit: number | string;
  credit: number | string;
  running_balance: number | string;
  document_ids: string[];
}

export interface GeneralLedgerResponse {
  organization_name: string;
  account_code: string;
  account_name: string;
  account_type: string;
  normal_balance: string;
  start_date: string;
  end_date: string;
  opening_balance: number | string;
  total_debit: number | string;
  total_credit: number | string;
  closing_balance: number | string;
  entries: GeneralLedgerEntry[];
  total_records: number;
  page: number;
  page_size: number;
}

export interface IntegrityCheckItem {
  check_name: string;
  status: 'PASS' | 'FAIL';
  left_value: number | string;
  right_value: number | string;
  discrepancy: number | string;
  message: string;
}

export interface IntegrityReportResponse {
  organization_name: string;
  as_of_date: string;
  overall_status: 'VALID' | 'INTEGRITY_ERROR';
  checks: IntegrityCheckItem[];
}

export interface CashFlowReportResponse {
  organization_name: string;
  period_label: string;
  start_date: string;
  end_date: string;
  opening_cash_balance: number | string;
  operating_activities: ReportSection;
  net_operating_cash: number | string;
  investing_activities: ReportSection;
  net_investing_cash: number | string;
  financing_activities: ReportSection;
  net_financing_cash: number | string;
  net_cash_change: number | string;
  closing_cash_balance: number | string;
  unclassified_cash_activities?: ReportSection | null;
}

export interface AgingBucketSummary {
  current: number | string;
  days_1_30: number | string;
  days_31_60: number | string;
  days_61_90: number | string;
  days_over_90: number | string;
  total: number | string;
}

export interface ARAgingInvoiceLine {
  customer_id: string;
  customer_name: string;
  project_code?: string | null;
  project_name?: string | null;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  days_overdue: number;
  total_amount: number | string;
  paid_amount: number | string;
  outstanding_amount: number | string;
  bucket: string;
}

export interface ARAgingReportResponse {
  organization_name: string;
  as_of_date: string;
  summary: AgingBucketSummary;
  invoices: ARAgingInvoiceLine[];
}

export interface APAgingBillLine {
  vendor_id: string;
  vendor_name: string;
  project_code?: string | null;
  project_name?: string | null;
  bill_number: string;
  bill_date: string;
  due_date: string;
  days_overdue: number;
  total_amount: number | string;
  paid_amount: number | string;
  outstanding_amount: number | string;
  bucket: string;
}

export interface APAgingReportResponse {
  organization_name: string;
  as_of_date: string;
  summary: AgingBucketSummary;
  bills: APAgingBillLine[];
  unsettled_advances_total: number | string;
}

export interface ProjectCostCategoryLine {
  cost_category: string;
  category_name: string;
  amount: number | string;
}

export interface ProjectProfitabilityReportResponse {
  organization_name: string;
  project_id: string;
  project_code: string;
  project_name: string;
  client_name?: string | null;
  status: string;
  original_contract_value: number | string;
  variation_orders_value: number | string;
  revised_contract_value: number | string;
  revenue_recognized: number | string;
  cost_breakdown: ProjectCostCategoryLine[];
  total_project_cost: number | string;
  gross_profit: number | string;
  gross_margin_percentage: number | string;
}

export interface ProjectCashPositionReportResponse {
  organization_name: string;
  project_id: string;
  project_code: string;
  project_name: string;
  invoiced_amount: number | string;
  cash_received: number | string;
  receivable_outstanding: number | string;
  cash_spent: number | string;
  net_cash_position: number | string;
  is_surplus: boolean;
  notice_message: string;
}

export interface BudgetVsActualLine {
  cost_category: string;
  category_name: string;
  budget_amount: number | string;
  actual_amount: number | string;
  variance_amount: number | string;
  variance_percentage: number | string;
  status: string;
}

export interface BudgetVsActualReportResponse {
  organization_name: string;
  project_id: string;
  project_code: string;
  project_name: string;
  has_budget: boolean;
  budget_status_label: string;
  total_budget: number | string;
  total_actual: number | string;
  total_variance: number | string;
  consumption_percentage: number | string;
  lines: BudgetVsActualLine[];
}

export interface DashboardSummaryResponse {
  organization_name: string;
  as_of_date: string;
  cash_and_bank_balance: number | string;
  cash_in_period: number | string;
  cash_out_period: number | string;
  net_cash_flow: number | string;
  unallocated_cash: number | string;
  project_spending: number | string;
  accounts_receivable_outstanding: number | string;
  accounts_payable_outstanding: number | string;
  revenue_ytd: number | string;
  net_profit_ytd: number | string;
  estimated_monthly_burn_rate: number | string;
  cash_runway_months?: number | string | null;
  active_projects_count: number;
  review_queue_pending_count: number;
  integrity_status: 'VALID' | 'INTEGRITY_ERROR';
}


