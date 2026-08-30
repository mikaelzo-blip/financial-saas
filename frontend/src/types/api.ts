/**
 * Core API TypeScript DTOs mirroring Backend OpenAPI contracts
 */

export type UserRole = 'ADMIN' | 'MANAGER' | 'OPERATOR' | 'VIEWER';

export interface UserSession {
  userId: string;
  email: string;
  fullName: string;
  role: UserRole;
  organizationId: string;
  organizationName: string;
  accessToken: string;
}

export type ProjectStatus =
  | 'PLANNED'
  | 'ACTIVE'
  | 'ON_HOLD'
  | 'COMPLETED'
  | 'CLOSED'
  | 'CANCELLED';

export type TransactionType =
  | 'DIRECT_PURCHASE'
  | 'VENDOR_BILL'
  | 'PAY_VENDOR_BILL'
  | 'VENDOR_ADVANCE'
  | 'SETTLE_VENDOR_ADVANCE'
  | 'CUSTOMER_INVOICE'
  | 'CUSTOMER_PAYMENT'
  | 'CUSTOMER_ADVANCE'
  | 'TRANSFER_INTERBANK'
  | 'OWNER_CONTRIBUTION'
  | 'OWNER_WITHDRAWAL'
  | 'REVERSAL'
  | 'JOURNAL_ADJUSTMENT';

export type WorkflowStatus =
  | 'STAGED'
  | 'REVIEW_REQUIRED'
  | 'POSTED'
  | 'REVERSED'
  | 'REJECTED';

export type CostCategory =
  | 'MAT'
  | 'SUB'
  | 'LAB'
  | 'EQP'
  | 'TRN'
  | 'UTL'
  | 'PRM'
  | 'OHD'
  | 'OTH';

export type ReviewFlag =
  | 'AMOUNT_MISMATCH'
  | 'DUPLICATE_SUSPECTED'
  | 'PROJECT_UNKNOWN'
  | 'VENDOR_UNKNOWN'
  | 'CUSTOMER_UNKNOWN'
  | 'ACCOUNT_REVIEW'
  | 'TAX_REVIEW'
  | 'MISSING_DOCUMENT';

export interface ProjectResponse {
  id: string;
  organization_id: string;
  project_code: string;
  project_name: string;
  customer_id: string;
  customer_name?: string;
  po_spk_no?: string;
  po_spk_date?: string;
  original_contract_value: string;
  variation_order_value: string;
  revised_contract_value: string;
  start_date: string;
  target_end_date?: string;
  actual_end_date?: string;
  pic_user_id?: string;
  project_status: ProjectStatus;
  billing_status?: string;
  collection_status?: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCostCategoryBreakdown {
  cost_category: string;
  budget_amount: string;
  actual_cost: string;
  variance_amount: string;
}

export interface ProjectProfitabilityResponse {
  project_id: string;
  project_code: string;
  project_name: string;
  contract: {
    original_contract_value: string;
    variation_order_value: string;
    revised_contract_value: string;
  };
  pnl: {
    recognized_revenue: string;
    total_actual_cost: string;
    gross_profit: string;
    gross_margin_percentage: string;
  };
  cash: {
    total_invoiced: string;
    total_received: string;
    outstanding_receivables: string;
    net_cash_position: string;
  };
  cost_breakdown: ProjectCostCategoryBreakdown[];
}

export interface TransactionAllocationItem {
  id?: string;
  project_id?: string;
  cost_category?: CostCategory;
  amount: string;
  notes?: string;
}

export interface TransactionResponse {
  id: string;
  organization_id: string;
  transaction_code: string;
  transaction_type: TransactionType;
  transaction_date: string;
  amount: string;
  currency: string;
  workflow_status: WorkflowStatus;
  counterparty_id?: string;
  counterparty_name?: string;
  payment_account_id?: string;
  payment_account_name?: string;
  reference_no?: string;
  description: string;
  source_channel: string;
  created_by?: string;
  approved_by?: string;
  approved_at?: string;
  posted_at?: string;
  reversal_of_id?: string;
  created_at: string;
  updated_at: string;
  allocations: TransactionAllocationItem[];
  review_flags: ReviewFlagResponse[];
}

export interface ReviewFlagResponse {
  id: string;
  transaction_id: string;
  flag: ReviewFlag;
  severity: string;
  message: string;
  resolved_by?: string;
  resolved_at?: string;
  resolution_notes?: string;
  created_at: string;
}

export interface DocumentResponse {
  id: string;
  organization_id: string;
  document_code: string;
  document_type: string;
  file_name: string;
  file_hash: string;
  file_size_bytes: number;
  mime_type: string;
  source_channel: string;
  created_at: string;
  processing_status: 'UPLOADED' | 'HASHED' | 'EXTRACTING' | 'EXTRACTED' | 'MATCHING' | 'REVIEW_REQUIRED' | 'READY_FOR_APPROVAL' | 'PROCESSED' | 'FAILED';
  extracted_data: Record<string, unknown>;
  matching_results: Record<string, unknown>;
  confidence_scores: Record<string, string>;
  candidate_transaction: Record<string, unknown>;
  review_flags: string[];
  failure_code?: string;
  failure_message?: string;
}

export interface CounterpartyResponse {
  id: string;
  organization_id: string;
  name: string;
  is_customer: boolean;
  is_vendor: boolean;
  phone?: string;
  email?: string;
  address?: string;
  npwp?: string;
  created_at: string;
}

export interface PaymentAccountResponse {
  id: string;
  organization_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  bank_name?: string;
  account_number?: string;
  is_active: boolean;
}

export interface ChartOfAccountResponse {
  id: string;
  organization_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  parent_id?: string;
  is_active: boolean;
}
