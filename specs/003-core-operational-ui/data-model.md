# Frontend Data Model & View Schemas: Web SaaS Application — Core Operational UI

**Feature**: `003-core-operational-ui`  
**Date**: 2026-08-30  
**Status**: Approved

---

## 1. Overview & Principle of Frontend Non-Authority

The frontend data models represent view-state DTOs and form inputs. **No database tables or running balances exist in the frontend**. All financial numbers, statuses, and calculations originate from the authoritative backend API.

---

## 2. Core View Models & TypeScript Interfaces

### A. Authentication & Session State
```typescript
export interface UserSession {
  userId: string;
  email: string;
  fullName: string;
  role: 'OPERATOR' | 'MANAGER' | 'ADMIN' | 'VIEWER';
  organizationId: string;
  organizationName: string;
  accessToken: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: UserSession | null;
  isLoading: boolean;
}
```

---

### B. Dashboard Operational Metrics
```typescript
export interface DashboardSummary {
  cashAndBankBalance: string; // Decimal string from backend
  totalReceivables: string;    // Outstanding AR
  totalPayables: string;       // Outstanding AP
  activeProjectsCount: number;
  reviewQueueCount: number;
}
```

---

### C. Project View Models
```typescript
export type ProjectStatus = 'PLANNED' | 'ACTIVE' | 'ON_HOLD' | 'COMPLETED' | 'CLOSED' | 'CANCELLED';

export interface ProjectListItem {
  id: string;
  projectCode: string;
  projectName: string;
  customerName: string;
  originalContractValue: string;
  variationOrderValue: string;
  revisedContractValue: string;
  projectStatus: ProjectStatus;
  startDate: string;
  targetEndDate?: string;
  actualEndDate?: string;
  billingStatus: 'NOT_INVOICED' | 'PARTIALLY_INVOICED' | 'FULLY_INVOICED';
  collectionStatus: 'NOT_DUE' | 'DUE' | 'OVERDUE' | 'COLLECTED';
}

export interface ProjectCostCategoryBreakdown {
  costCategory: string; // 'MAT', 'SUB', 'LAB', 'EQP', 'TRN', 'UTL', 'PRM', 'OHD', 'OTH'
  budgetAmount: string;
  actualCost: string;
  varianceAmount: string;
  variancePercentage: string;
}

export interface ProjectFinancialDetail {
  id: string;
  projectCode: string;
  projectName: string;
  contract: {
    originalContractValue: string;
    variationOrderValue: string;
    revisedContractValue: string;
  };
  pnl: {
    recognizedRevenue: string;
    totalActualCost: string;
    grossProfit: string;
    grossMarginPercentage: string;
  };
  cash: {
    totalInvoiced: string;
    totalReceived: string;
    outstandingReceivables: string;
    netCashPosition: string;
  };
  costBreakdown: ProjectCostCategoryBreakdown[];
}
```

---

### D. Transaction View & Form Models
```typescript
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

export type WorkflowStatus = 'STAGED' | 'REVIEW_REQUIRED' | 'POSTED' | 'REVERSED' | 'REJECTED';

export interface TransactionAllocationItem {
  projectId?: string;
  costCategory?: string;
  expenseCategory?: string;
  amount: string; // Decimal string
  notes?: string;
}

export interface TransactionFormData {
  transactionType: TransactionType;
  transactionDate: string;
  amount: string;
  currency: string;
  counterpartyId?: string;
  paymentAccountId?: string;
  referenceNo?: string;
  description: string;
  documentIds: string[];
  
  // Single-project mode (default)
  projectId?: string;
  costCategory?: string;
  expenseCategory?: string;
  
  // Multi-project split toggle
  isSplitAllocation: boolean;
  allocations: TransactionAllocationItem[];
}

export interface TransactionListItem {
  id: string;
  transactionCode: string;
  transactionType: TransactionType;
  transactionDate: string;
  amount: string;
  currency: string;
  workflowStatus: WorkflowStatus;
  description: string;
  counterpartyName?: string;
  paymentAccountName?: string;
  hasDocuments: boolean;
  reviewFlagsCount: number;
  createdAt: string;
}
```

---

### E. Review Queue View Models
```typescript
export type ReviewFlag =
  | 'AMOUNT_MISMATCH'
  | 'DUPLICATE_SUSPECTED'
  | 'PROJECT_UNKNOWN'
  | 'VENDOR_UNKNOWN'
  | 'CUSTOMER_UNKNOWN'
  | 'ACCOUNT_REVIEW'
  | 'TAX_REVIEW'
  | 'MISSING_DOCUMENT';

export interface ReviewFlagItem {
  id: string;
  flag: ReviewFlag;
  severity: 'WARNING' | 'CRITICAL';
  message: string;
  resolvedBy?: string;
  resolvedAt?: string;
  resolutionNotes?: string;
  createdAt: string;
}

export interface ReviewQueueItem {
  transaction: TransactionListItem;
  reviewFlags: ReviewFlagItem[];
  documentPreviews: DocumentItem[];
}
```

---

### F. Accounts Receivable (AR) & Accounts Payable (AP)
```typescript
export interface CustomerInvoiceItem {
  id: string;
  invoiceNumber: string;
  customerId: string;
  customerName: string;
  projectId: string;
  projectName: string;
  invoiceDate: string;
  dueDate: string;
  totalAmount: string;
  paidAmount: string;
  outstandingAmount: string;
  status: 'ISSUED' | 'PARTIALLY_PAID' | 'PAID' | 'CANCELLED';
  collectionStatus: 'NOT_DUE' | 'DUE' | 'OVERDUE';
}

export interface VendorBillItem {
  id: string;
  billNumber: string;
  vendorId: string;
  vendorName: string;
  projectId?: string;
  projectName?: string;
  billDate: string;
  dueDate: string;
  totalAmount: string;
  paidAmount: string;
  outstandingAmount: string;
  status: 'RECEIVED' | 'PARTIALLY_PAID' | 'PAID' | 'CANCELLED';
}
```

---

### G. Document Metadata
```typescript
export interface DocumentItem {
  id: string;
  documentCode: string;
  documentType: string;
  fileName: string;
  fileHash: string;
  sourceChannel: string;
  fileUrl: string;
  createdAt: string;
}
```
