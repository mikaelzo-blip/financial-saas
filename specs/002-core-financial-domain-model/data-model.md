# Phase 1 Data Model: Relational Domain Specification

**Feature**: `002-core-financial-domain-model`  
**Database Engine**: PostgreSQL 16+  
**Currency Standard**: Indonesian Rupiah (IDR), stored as `NUMERIC(18, 2)` (with standard 0 decimal display)

---

## 1. Domain Enums

### 1.1 `user_role`
- `ADMIN`: Full configuration and management capabilities.
- `MANAGER`: Project insights viewer; required approver for sensitive transactions.
- `OPERATOR`: Daily document intake, transaction capture, routine approvals.
- `VIEWER`: Read-only reporting access.

### 1.2 `project_status`
- `PLANNED`: Contract signed or intent confirmed; work not yet commenced.
- `ACTIVE`: Construction/service execution currently underway.
- `ON_HOLD`: Work temporarily suspended.
- `COMPLETED`: Physical and operational site work finished.
- `CLOSED`: Final retention settled, accounting fully closed (terminal).
- `CANCELLED`: Engagement cancelled before/during execution (terminal).

### 1.3 `billing_status` (Derived)
- `NOT_INVOICED`: No customer invoices issued against contract.
- `PARTIALLY_INVOICED`: Total invoiced < revised contract value.
- `FULLY_INVOICED`: Total invoiced >= revised contract value.

### 1.4 `collection_status` (Derived)
- `NOT_DUE`: No issued invoices are currently due.
- `PARTIALLY_PAID`: Some payments received, but outstanding balance exists on due invoices.
- `PAID`: All issued invoices are fully paid.
- `OVERDUE`: At least one issued invoice is past its due date with an outstanding balance.

### 1.5 `workflow_status`
- `CAPTURED`: Source document received via ingest API.
- `EXTRACTED`: Document data parsed/extracted into structured staging.
- `STAGED`: Validated candidate transaction ready for operational review/approval.
- `REVIEW_REQUIRED`: Discrepancy, ambiguity, or sensitive flag requires resolution.
- `APPROVED`: Validations passed and approved by authorized operator/manager.
- `POSTED`: Double-entry journal generated, balanced, and ledger updated (immutable).
- `RECONCILED`: Bank statement reconciliation confirmed.
- `REVERSED`: Transaction negated by a subsequent reversing transaction (terminal).

### 1.6 `review_flag`
- `OCR_LOW_CONFIDENCE`
- `MISSING_DOCUMENT`
- `DUPLICATE_SUSPECTED`
- `PROJECT_UNKNOWN`
- `VENDOR_UNKNOWN`
- `CUSTOMER_UNKNOWN`
- `AMOUNT_MISMATCH`
- `DATE_MISMATCH`
- `TAX_REVIEW`
- `ACCOUNT_REVIEW`
- `RELATED_PARTY_REVIEW`

### 1.7 `transaction_type` (Approved 35 Types)
- **Direct & Bills**: `DIRECT_PURCHASE`, `VENDOR_BILL`, `PAY_VENDOR_BILL`, `SUBCONTRACTOR_BILL`, `PAY_SUBCONTRACTOR`
- **Advances & Settlements**: `VENDOR_ADVANCE`, `SETTLE_VENDOR_ADVANCE`, `EMPLOYEE_ADVANCE`, `EMPLOYEE_SETTLEMENT`, `CUSTOMER_ADVANCE`
- **Reimbursements & Petty Cash**: `REIMBURSEMENT`, `PAY_REIMBURSEMENT`, `PETTY_CASH_EXPENSE`, `TOPUP_PETTY_CASH`, `RETURN_PETTY_CASH`
- **Transfers**: `BANK_TO_CASH`, `CASH_TO_BANK`, `INTERBANK_TRANSFER`
- **Assets & Inventory**: `ASSET_PURCHASE`, `INVENTORY_PURCHASE`, `INVENTORY_USAGE`
- **Customer Billing & Revenue**: `CUSTOMER_INVOICE`, `CUSTOMER_PAYMENT`, `REVENUE_RECOGNITION`
- **Refunds**: `CUSTOMER_REFUND`, `VENDOR_REFUND`
- **Equity & Financing**: `OWNER_CONTRIBUTION`, `OWNER_WITHDRAWAL`, `LOAN_RECEIVED`, `LOAN_PAYMENT`
- **Overhead & Adjustments**: `BANK_CHARGE`, `OTHER_INCOME`, `OTHER_EXPENSE`, `JOURNAL_ADJUSTMENT`, `REVERSAL`

### 1.8 `cost_category`
- `MAT`: Material & Goods
- `SUB`: Subcontractor & Specialist Services
- `LAB`: Direct Labor, Technicians & Freelancers
- `TRN`: Local Transportation, Fuel (BBM), Toll & Parking
- `TRV`: Travel, Lodging, Airfare & Site Accommodation
- `LOG`: Freight, Trucking, Shipping & Handling
- `EQP`: Equipment Rental & Tool Usage
- `SIT`: Site Safety (PPE), Site Administration & Permits
- `OTH`: Other Direct Project Costs

### 1.9 `expense_category`
- `SALARY`: Employee Payroll & THR
- `FEE`: Honorarium, Non-project Consulting, Referral Fee
- `OFFICE_ADMIN`: Office Utilities, Rent, Office Supplies
- `TRAVEL_OFFICE`: Office Transport & Executive Travel
- `PERMITS`: Corporate Licenses & Legal Registrations
- `PROFESSIONAL_SERVICE`: Legal, Tax Consultant, Audit Services
- `BANK_CHARGES`: Bank Administration & Transfer Fees
- `DEPRECIATION`: Asset Depreciation Expense
- `OTHER_OPERATIONAL`: Miscellaneous Operational Overhead

### 1.10 `account_type` & `normal_balance`
- `account_type`: `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`
- `normal_balance`: `DEBIT`, `CREDIT`

### 1.11 `document_type`
- `PO_CUSTOMER`, `SPK`, `CONTRACT`, `VARIATION_ORDER`
- `PURCHASE_ORDER`, `QUOTATION`, `VENDOR_INVOICE`, `SUBCONTRACT_AGREEMENT`
- `TRANSFER_PROOF`, `RECEIPT`, `BANK_STATEMENT`, `PETTY_CASH_PROOF`
- `SURAT_JALAN`, `BAST`, `PROGRESS_REPORT`, `TIMESHEET`
- `CUSTOMER_INVOICE`, `CUSTOMER_RECEIPT`
- `TAX_INVOICE`, `WITHHOLDING_DOCUMENT`, `OTHER_TAX_DOCUMENT`

---

## 2. Relational Schema & Tables

### 2.1 Core Organization & Users

#### `organizations`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal UUID |
| `slug` | VARCHAR(50) | UNIQUE, NOT NULL | URL-safe identifier |
| `legal_name` | VARCHAR(255) | NOT NULL | Registered company name |
| `tax_id` | VARCHAR(50) | NULL | NPWP |
| `default_payment_term_days` | INT | NOT NULL DEFAULT 30 | Default invoice payment terms |
| `fiscal_year_start_month` | INT | NOT NULL DEFAULT 1 | 1 for January |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Audit creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Audit update timestamp |

#### `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal user ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `email` | VARCHAR(255) | NOT NULL | User login email |
| `full_name` | VARCHAR(255) | NOT NULL | Display name |
| `role` | user_role | NOT NULL DEFAULT 'OPERATOR' | Authorization role |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Updated at |
| **Indexes/Unique** | | `UNIQUE(organization_id, email)` | |

---

### 2.2 Master Data: Counterparties, COA & Accounts

#### `counterparties`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `name` | VARCHAR(255) | NOT NULL | Company / Individual name |
| `is_customer` | BOOLEAN | NOT NULL DEFAULT FALSE | Can be invoiced |
| `is_vendor` | BOOLEAN | NOT NULL DEFAULT FALSE | Can issue bills |
| `tax_id` | VARCHAR(50) | NULL | NPWP |
| `contact_info` | JSONB | NOT NULL DEFAULT '{}'::jsonb | Phone, email, address |
| `bank_accounts` | JSONB | NOT NULL DEFAULT '[]'::jsonb | Counterparty bank accounts |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active status |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Updated at |

#### `chart_of_accounts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `account_code` | VARCHAR(20) | NOT NULL | E.g. '1101', '5101' |
| `account_name` | VARCHAR(255) | NOT NULL | E.g. 'Kas dan Bank' |
| `account_type` | account_type | NOT NULL | ASSET, LIABILITY, etc. |
| `normal_balance` | normal_balance | NOT NULL | DEBIT or CREDIT |
| `report_group` | VARCHAR(100) | NOT NULL | Grouping for balance sheet / P&L |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |
| **Indexes/Unique** | | `UNIQUE(organization_id, account_code)` | |
*Note*: No balance column. Balances are derived dynamically from `journal_lines`.

#### `payment_accounts`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `coa_account_id` | UUID | FK -> chart_of_accounts(id), NOT NULL | Typically maps to 1101 |
| `name` | VARCHAR(100) | NOT NULL | E.g. 'Bank Mandiri Operasional' |
| `bank_name` | VARCHAR(100) | NULL | Mandiri, BCA, BRI, Cash |
| `account_number` | VARCHAR(100) | NULL | Bank account number |
| `is_active` | BOOLEAN | NOT NULL DEFAULT TRUE | Active flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |

---

### 2.3 Projects & Budgeting

#### `projects`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `project_code` | VARCHAR(50) | NOT NULL | E.g. 'PRJ-2026-001' |
| `project_name` | VARCHAR(255) | NOT NULL | Project description/title |
| `customer_id` | UUID | FK -> counterparties(id), NOT NULL | Customer reference |
| `po_spk_no` | VARCHAR(100) | NULL | Customer PO / SPK Number |
| `po_spk_date` | DATE | NULL | Date of contract / SPK |
| `original_contract_value` | NUMERIC(18,2)| NOT NULL DEFAULT 0, CHECK (>= 0) | Initial value |
| `variation_order_value` | NUMERIC(18,2)| NOT NULL DEFAULT 0 | Addendum value |
| `revised_contract_value` | NUMERIC(18,2)| GENERATED ALWAYS AS (original_contract_value + variation_order_value) STORED | Total contract value |
| `start_date` | DATE | NOT NULL | Start date |
| `target_end_date` | DATE | NULL | Target completion date |
| `actual_end_date` | DATE | NULL | Real completion date |
| `pic_user_id` | UUID | FK -> users(id), NULL | Responsible Person in Charge |
| `project_status` | project_status | NOT NULL DEFAULT 'PLANNED' | Lifecycle status |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |
| `updated_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Updated at |
| **Indexes/Unique** | | `UNIQUE(organization_id, project_code)` | |

#### `project_budgets`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `project_id` | UUID | FK -> projects(id), NOT NULL | Project reference |
| `cost_category` | cost_category | NOT NULL | MAT, SUB, LAB, etc. |
| `budget_amount` | NUMERIC(18,2)| NOT NULL DEFAULT 0, CHECK (>= 0) | Budget allocated |
| `notes` | TEXT | NULL | Budget notes |
| **Indexes/Unique** | | `UNIQUE(project_id, cost_category)` | One budget per category |

---

### 2.4 Documents & File Traceability

#### `documents`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `document_code` | VARCHAR(50) | NOT NULL | E.g. 'DOC-2026-000001' |
| `document_type` | document_type | NOT NULL | VENDOR_INVOICE, etc. |
| `file_name` | VARCHAR(255) | NOT NULL | Original uploaded filename |
| `mime_type` | VARCHAR(100) | NOT NULL | E.g. 'image/jpeg', 'application/pdf' |
| `file_size_bytes` | BIGINT | NOT NULL | File size |
| `file_hash` | VARCHAR(64) | NOT NULL | SHA-256 hash |
| `storage_path` | VARCHAR(500) | NOT NULL | S3 or local storage key |
| `source_channel` | VARCHAR(50) | NOT NULL DEFAULT 'WEB_UPLOAD' | 'WHATSAPP', 'WEB_UPLOAD', etc. |
| `source_metadata` | JSONB | NOT NULL DEFAULT '{}'::jsonb | Sender phone, message ID, chat ID |
| `raw_extraction` | JSONB | NOT NULL DEFAULT '{}'::jsonb | OCR / Hermes parsed payload |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Upload timestamp |
| `created_by` | UUID | FK -> users(id), NULL | Uploader |
| **Indexes/Unique** | | `UNIQUE(organization_id, file_hash)` | Duplicate detection |
| | | `UNIQUE(organization_id, document_code)` | |

#### `project_document_links`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `project_id` | UUID | FK -> projects(id) ON DELETE CASCADE | Project |
| `document_id` | UUID | FK -> documents(id) ON DELETE RESTRICT | Document |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Linked timestamp |
| **Primary Key** | | `PRIMARY KEY(project_id, document_id)` | |

---

### 2.5 Transactions & Allocations (Single Input Core)

#### `transactions`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `transaction_code` | VARCHAR(50) | NOT NULL | E.g. 'TRX-2026-000001' |
| `transaction_date` | DATE | NOT NULL | Business event date |
| `transaction_type` | transaction_type | NOT NULL | One of 35 types |
| `description` | TEXT | NOT NULL | Transaction memo/summary |
| `total_amount` | NUMERIC(18,2)| NOT NULL, CHECK (total_amount > 0) | Gross transaction amount |
| `workflow_status` | workflow_status | NOT NULL DEFAULT 'STAGED' | State machine status |
| `counterparty_id` | UUID | FK -> counterparties(id), NULL | Vendor or Customer |
| `payment_account_id`| UUID | FK -> payment_accounts(id), NULL | Cash / Bank account |
| `project_id` | UUID | FK -> projects(id), NULL | Single-project link (if not split) |
| `cost_category` | cost_category | NULL | Cost category (single-project) |
| `expense_category` | expense_category| NULL | Operational expense category |
| `reference_number` | VARCHAR(100) | NULL | Invoice #, Check #, Ref # |
| `tax_relevance` | BOOLEAN | NOT NULL DEFAULT FALSE | Has tax implications |
| `tax_type_id` | UUID | NULL | Reference to tax table |
| `tax_base` | NUMERIC(18,2)| NULL | DPP (Dasar Pengenaan Pajak) |
| `tax_amount` | NUMERIC(18,2)| NULL | Tax amount |
| `confidence_score` | NUMERIC(5,4) | NULL | AI / OCR confidence (0.0000-1.0000)|
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created timestamp |
| `created_by` | UUID | FK -> users(id), NOT NULL | Submitter |
| `modified_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last modified timestamp |
| `modified_by` | UUID | FK -> users(id), NOT NULL | Last modifier |
| `approved_at` | TIMESTAMPTZ | NULL | Approval timestamp |
| `approved_by` | UUID | FK -> users(id), NULL | Approving user |
| `reversal_of_id` | UUID | FK -> transactions(id), NULL | If this is a REVERSAL, target TRX |
| **Indexes/Unique** | | `UNIQUE(organization_id, transaction_code)` | |
| | | `INDEX(organization_id, workflow_status)` | Review queue querying |
| | | `INDEX(organization_id, transaction_date, total_amount, counterparty_id)` | Duplicate transaction check |

#### `transaction_allocations`
*Used when a transaction is split across multiple projects (Clarification Q1).*
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `transaction_id` | UUID | FK -> transactions(id) ON DELETE CASCADE, NOT NULL | Parent transaction |
| `project_id` | UUID | FK -> projects(id), NOT NULL | Target project |
| `cost_category` | cost_category | NOT NULL | Cost category for this split |
| `allocated_amount` | NUMERIC(18,2)| NOT NULL, CHECK (allocated_amount > 0) | Split amount |
| `notes` | VARCHAR(255) | NULL | Line description |
| **Constraint** | | `CHECK (allocated_amount > 0)` | |

#### `transaction_review_flags`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `transaction_id` | UUID | FK -> transactions(id) ON DELETE CASCADE, NOT NULL | Target transaction |
| `flag` | review_flag | NOT NULL | E.g. 'AMOUNT_MISMATCH' |
| `details` | TEXT | NULL | Context message / reason |
| `is_resolved` | BOOLEAN | NOT NULL DEFAULT FALSE | Resolved flag |
| `resolved_at` | TIMESTAMPTZ | NULL | Resolution timestamp |
| `resolved_by` | UUID | FK -> users(id), NULL | Resolving user |
| `resolution_notes`| TEXT | NULL | Explanation of override/fix |
| **Indexes/Unique** | | `UNIQUE(transaction_id, flag)` | |

#### `transaction_document_links`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `transaction_id` | UUID | FK -> transactions(id) ON DELETE CASCADE | Transaction |
| `document_id` | UUID | FK -> documents(id) ON DELETE RESTRICT | Document |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Linked timestamp |
| **Primary Key** | | `PRIMARY KEY(transaction_id, document_id)` | |

---

### 2.6 Double-Entry Journal Engine (Immutable Ledger)

#### `journal_entries`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `transaction_id` | UUID | FK -> transactions(id), UNIQUE, NOT NULL | Exactly 1 journal per posted TRX |
| `entry_date` | DATE | NOT NULL | Posting date |
| `total_debit` | NUMERIC(18,2)| NOT NULL, CHECK (total_debit > 0) | Sum of line debits |
| `total_credit` | NUMERIC(18,2)| NOT NULL, CHECK (total_credit > 0) | Sum of line credits |
| `posted_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Immutability lock time |
| `posted_by` | UUID | FK -> users(id), NOT NULL | Posting user |
| **Constraint** | | `CHECK (total_debit = total_credit)` | Constitution Principle IV |

#### `journal_lines`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Line ID |
| `journal_entry_id` | UUID | FK -> journal_entries(id) ON DELETE CASCADE, NOT NULL | Header |
| `account_id` | UUID | FK -> chart_of_accounts(id), NOT NULL | COA account |
| `project_id` | UUID | FK -> projects(id), NULL | Project dimension |
| `cost_category` | cost_category | NULL | Cost category (if 5101) |
| `expense_category` | expense_category| NULL | Expense category (if 6xxx) |
| `payment_account_id`| UUID | FK -> payment_accounts(id), NULL | Sub-account (if 1101) |
| `debit` | NUMERIC(18,2)| NOT NULL DEFAULT 0, CHECK (debit >= 0) | Debit amount |
| `credit` | NUMERIC(18,2)| NOT NULL DEFAULT 0, CHECK (credit >= 0) | Credit amount |
| `description` | VARCHAR(255) | NULL | Line description |
| **Constraint** | | `CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))` | Exactly one side non-zero |

---

### 2.7 Sub-Ledgers: Receivables, Payables & Advances

#### `customer_invoices` (Accounts Receivable Tracker)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `transaction_id` | UUID | FK -> transactions(id), UNIQUE, NOT NULL | Source CUSTOMER_INVOICE TRX |
| `invoice_number` | VARCHAR(100) | NOT NULL | Invoice number |
| `customer_id` | UUID | FK -> counterparties(id), NOT NULL | Customer |
| `project_id` | UUID | FK -> projects(id), NOT NULL | Project |
| `invoice_date` | DATE | NOT NULL | Billing date |
| `due_date` | DATE | NOT NULL | Due date (Net 30 default / override) |
| `amount` | NUMERIC(18,2)| NOT NULL, CHECK (amount > 0) | Billed gross amount |
| `is_cancelled` | BOOLEAN | NOT NULL DEFAULT FALSE | Reversal flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |

#### `vendor_bills` (Accounts Payable Tracker)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `transaction_id` | UUID | FK -> transactions(id), UNIQUE, NOT NULL | Source VENDOR_BILL TRX |
| `bill_number` | VARCHAR(100) | NOT NULL | Vendor invoice # |
| `vendor_id` | UUID | FK -> counterparties(id), NOT NULL | Vendor |
| `project_id` | UUID | FK -> projects(id), NULL | Associated project |
| `bill_date` | DATE | NOT NULL | Bill date |
| `due_date` | DATE | NULL | Due date |
| `amount` | NUMERIC(18,2)| NOT NULL, CHECK (amount > 0) | Bill amount |
| `is_cancelled` | BOOLEAN | NOT NULL DEFAULT FALSE | Reversal flag |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |

#### `payment_allocations` (Settles Invoices and Bills)
*Supports N payments -> M invoices with partial settlement tracking.*
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `payment_transaction_id` | UUID | FK -> transactions(id), NOT NULL | Payment TRX |
| `customer_invoice_id` | UUID | FK -> customer_invoices(id), NULL | Target AR Invoice |
| `vendor_bill_id` | UUID | FK -> vendor_bills(id), NULL | Target AP Bill |
| `allocated_amount` | NUMERIC(18,2)| NOT NULL, CHECK (allocated_amount > 0) | Settled amount |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Allocation time |
| **Constraint** | | `CHECK ((customer_invoice_id IS NOT NULL AND vendor_bill_id IS NULL) OR (vendor_bill_id IS NOT NULL AND customer_invoice_id IS NULL))` | Mutual exclusivity |

#### `advances` (Prepayments Tracker)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `transaction_id` | UUID | FK -> transactions(id), UNIQUE, NOT NULL | Source Advance TRX |
| `counterparty_id` | UUID | FK -> counterparties(id), NULL | Vendor or Customer |
| `employee_user_id` | UUID | FK -> users(id), NULL | For EMPLOYEE_ADVANCE |
| `advance_type` | VARCHAR(50) | NOT NULL | 'VENDOR', 'CUSTOMER', 'EMPLOYEE' |
| `original_amount` | NUMERIC(18,2)| NOT NULL, CHECK (original_amount > 0) | Original advance value |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Created at |

#### `advance_settlement_allocations`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `advance_id` | UUID | FK -> advances(id), NOT NULL | Target advance |
| `settlement_transaction_id` | UUID | FK -> transactions(id), NOT NULL | Settlement TRX |
| `allocated_amount` | NUMERIC(18,2)| NOT NULL, CHECK (allocated_amount > 0) | Settled amount |
| `created_at` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Settlement time |

---

### 2.8 Audit & Traceability

#### `audit_logs` (Immutable Append-Only Log)
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Internal ID |
| `organization_id` | UUID | FK -> organizations(id), NOT NULL | Tenant boundary |
| `entity_name` | VARCHAR(100) | NOT NULL | E.g. 'transactions', 'projects' |
| `entity_id` | UUID | NOT NULL | Target row UUID |
| `action` | VARCHAR(50) | NOT NULL | 'INSERT', 'UPDATE', 'STATE_CHANGE', 'REVERSAL' |
| `actor_id` | UUID | FK -> users(id), NULL | Operator who performed action |
| `old_values` | JSONB | NULL | Snapshot before modification |
| `new_values` | JSONB | NULL | Snapshot after modification |
| `reason` | TEXT | NULL | Reason for reversal / adjustment |
| `timestamp` | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Immutable timestamp |
| **Indexes** | | `INDEX(organization_id, entity_name, entity_id)` | Fast audit trail history |
