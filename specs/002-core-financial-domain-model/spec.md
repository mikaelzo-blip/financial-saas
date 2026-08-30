# Feature Specification: Core Financial Domain Model

**Feature Branch**: `002-core-financial-domain-model`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Phase 2 — Core Financial Domain and Data Model. Design the functional specification for the core data model of a project-based financial management SaaS for an Indonesian contractor company. Transform the approved business concept into a precise domain specification before database schema or application implementation."

**Authoritative Source**: [Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)

## Clarifications

### Session 2026-08-29

- Q: When a single vendor bill covers materials used across two or more projects, should the system allow that one transaction to be split across multiple projects with separate journal lines per project, or should the user always create one transaction per project? → A: Support both — default to single-project transactions, but offer an optional split allocation mode when the user explicitly needs it.
- Q: When a customer pays more than the outstanding receivable on an invoice, should the system automatically create a credit balance on the customer's account, or should it always route the overpayment to the review queue for manual handling? → A: Route to review queue with AMOUNT_MISMATCH. User explicitly classifies the excess after review (Customer Advance, payment for another invoice, unapplied payment, refund required, or correction). No automatic excess allocation in MVP.
- Q: Should certain transaction types or amounts require Manager approval rather than Operator approval, and what distinguishes them? → A: Type-based escalation for MVP. Sensitive types (OWNER_WITHDRAWAL, REVERSAL, JOURNAL_ADJUSTMENT, etc.) require Manager approval. Routine operational types may be Operator-approved. Amount-based thresholds deferred (OPEN POLICY: materiality threshold). Approval model must be extensible to support type + amount + flags + role + policy rules in future.
- Q: When a SETTLE_VENDOR_ADVANCE amount exceeds the original advance's outstanding balance, should the system auto-split it or route to review? → A: Route to review with AMOUNT_MISMATCH. Do not automatically assume the excess is a new cash expense. User confirms the treatment of the excess (additional project cost as AP, additional cost paid immediately, allocation to another advance, correction, or other valid type). After confirmation, the Accounting Engine may generate multiple journal lines from the single transaction.
- Q: Where does the due date for a customer invoice come from? → A: Default with override. The system calculates a default due date from invoice date + a configurable organization-level payment term (e.g., Net 30). The user may override the due date per individual invoice.

---

## 1. Scope

This specification defines the domain entities, their relationships, lifecycle rules, business invariants, and data integrity requirements for the core financial data model of a project-based contractor financial management SaaS.

**In scope:**

- Domain entity definitions with attribute requirements (required vs. optional)
- Entity relationships and cardinality
- Lifecycle and status state machines
- Accounting engine rules and posting invariants
- Document management domain rules
- Duplicate detection domain rules
- Audit trail requirements
- Data integrity constraints
- Business rules that the data model must enforce

**Out of scope:**

- Database schema, migrations, or technology choice (PostgreSQL, etc.)
- API design, endpoints, or protocols
- Frontend, dashboard, or UI
- WhatsApp integration or Hermes agent implementation
- OCR, AI extraction, or document processing pipeline
- Tax calculation or tax rate configuration
- Financial statement rendering or report UI
- Deployment, infrastructure, or DevOps
- Excel import/export (Excel is not the system of record)

---

## 2. Actors

| Actor | Description |
| ----- | ----------- |
| **Operator** | Day-to-day user who submits documents and reviews transactions. Not necessarily an accountant. May approve routine operational transactions (non-sensitive types) after all validations pass. |
| **Manager** | Views project financial reports, budget vs. actual, and management insights. Required approver for sensitive transaction types (OWNER_WITHDRAWAL, REVERSAL, JOURNAL_ADJUSTMENT, related-party, etc.). May also approve any routine transaction. |
| **Admin** | Manages system configuration: users, COA, payment accounts, vendor/customer master data, cost categories, expense categories, and organization settings. |
| **Hermes** (future) | Automation agent that submits documents and candidate transactions via the SaaS API. Hermes does NOT write directly to the production database; it interacts exclusively through authenticated API endpoints. All posting controls remain in the SaaS backend. |
| **System** | The SaaS backend accounting engine that applies accounting rules, generates journal entries, enforces balance checks, manages workflow transitions, and enforces approval tier requirements. |

---

## 3. User Scenarios & Testing *(mandatory)*

### User Story 1 — Define and Manage Project Master Data (Priority: P1)

An Admin creates a new project when the company wins a contract. The project record stores the customer, contract value, PO/SPK reference, dates, and responsible person. As the project progresses, the Operator or Manager updates its status. The system automatically derives billing status and collection status from related invoices and payments rather than requiring manual updates.

**Why this priority**: Project is the central organizing dimension. Every transaction, cost, invoice, and report depends on a valid project record. Without it, no project-based financial analysis is possible.

**Independent Test**: Create a project record with all required fields, verify it persists with correct defaults, transition its status through the lifecycle, and confirm billing/collection statuses update when related invoices and payments are created.

**Acceptance Scenarios**:

1. **Given** a new contract with Customer "PT Pelabuhan" for Rp1.000.000.000, **When** the Admin creates a project, **Then** the project is stored with status PLANNED, billing status NOT_INVOICED, collection status NOT_DUE, and a unique Project_ID following the format PRJ-{YYYY}-{NNN}.
2. **Given** a project in PLANNED status, **When** work begins and the Admin changes the status to ACTIVE, **Then** the transition is recorded with timestamp and user identity in the audit trail.
3. **Given** a project with one customer invoice issued out of a total contract, **When** the billing status is queried, **Then** it reflects PARTIALLY_INVOICED (derived from invoice data, not manually set).
4. **Given** a project in ACTIVE status, **When** the Admin attempts to set status to CLOSED without first being in COMPLETED, **Then** the system rejects the invalid transition.

---

### User Story 2 — Record a Transaction from a Business Event (Priority: P1)

An Operator records a business event (e.g., a vendor purchase, a customer payment, a bank transfer) by entering minimal required information: transaction type, amount, counterparty, project (if applicable), payment account, and attaching a document. The system validates the input, assigns a unique Transaction_ID, sets the workflow status to STAGED (or REVIEW_REQUIRED if issues are detected), and persists the transaction without requiring the user to specify debit/credit accounts.

**Why this priority**: The Transaction entity is the single point of truth for every business event. The entire downstream flow — journals, AR/AP, project cost, reports — depends on correct transaction capture.

**Independent Test**: Create a transaction with type DIRECT_PURCHASE, verify the record is persisted with all fields, confirm the user is never asked to enter debit/credit, and confirm the workflow status is set correctly.

**Acceptance Scenarios**:

1. **Given** a DIRECT_PURCHASE for Rp8.500.000 against project PRJ-2026-014 paid from Bank Mandiri, **When** the Operator submits the transaction, **Then** it is stored with a unique Transaction_ID, workflow status STAGED, and all required fields populated.
2. **Given** a transaction submission where the project is unknown, **When** the system evaluates the input, **Then** the workflow status is set to REVIEW_REQUIRED and the review flag PROJECT_UNKNOWN is attached.
3. **Given** a transaction submission where date, amount, payment account, and recipient match an existing posted transaction, **When** duplicate detection runs, **Then** the review flag DUPLICATE_SUSPECTED is attached and the transaction is NOT automatically posted.

---

### User Story 3 — Approve and Post a Transaction with Automatic Journal Generation (Priority: P1)

An Operator reviews a transaction in STAGED or REVIEW_REQUIRED status, confirms or corrects the details, and approves it. Upon approval, the Accounting Engine looks up the Accounting Rule for the transaction type, generates the journal entry lines (debit and credit), validates that Total Debit = Total Credit, and transitions the workflow status to POSTED. The journal entry, project cost update, and AR/AP effects are all derived from this single approval action.

**Why this priority**: The Accounting Engine is what transforms a human-readable business event into proper double-entry accounting. Without automatic journal generation, users would need accounting expertise and the single-input principle is violated.

**Independent Test**: Approve a VENDOR_BILL transaction, verify the system generates journal lines (Dr Harga Pokok Proyek / Cr Utang Usaha) with balanced debits and credits, verify a new AP entry is created, and verify the project cost is updated.

**Acceptance Scenarios**:

1. **Given** a VENDOR_BILL transaction for Rp25.000.000 against Project A in STAGED status, **When** the Operator approves it, **Then** the Accounting Engine generates journal lines (Dr 5101 Harga Pokok Proyek Rp25.000.000 / Cr 2101 Utang Usaha Rp25.000.000), the workflow status becomes POSTED, a payable record is created for the vendor, and the project cost for Project A increases by Rp25.000.000 under the appropriate cost category.
2. **Given** a transaction whose accounting rule produces lines where Total Debit ≠ Total Credit, **When** posting is attempted, **Then** the posting is BLOCKED, the transaction remains in its current status, and an error is recorded.
3. **Given** a CUSTOMER_INVOICE transaction for Rp100.000.000 on Project B, **When** approved and posted, **Then** journal lines are generated (Dr 1201 Piutang Usaha / Cr 4101 Pendapatan Proyek dan Jasa), a receivable record is created, and the project's billing status is updated.
4. **Given** a transaction type in the never-auto-post list (e.g., OWNER_WITHDRAWAL), **When** the system processes it, **Then** Hermes or the system may provide a recommendation but the transaction MUST require explicit human approval before posting.

---

### User Story 4 — Manage Documents and Link Them to Business Records (Priority: P2)

An Operator uploads or attaches a source document (invoice PDF, transfer screenshot, receipt photo) to a transaction. The system stores the original file immutably, generates a Document_ID, computes a file hash, and records source metadata. The document can be linked to one or more transactions, projects, invoices, or bills. If a file with the same hash already exists, the system flags it as an exact duplicate.

**Why this priority**: Documents are the evidential basis for every transaction. Without document management, the system cannot provide auditability or support the future Hermes extraction pipeline.

**Independent Test**: Upload a document, verify it receives a unique Document_ID and file hash, link it to a transaction and a project, then upload the same file again and verify duplicate detection triggers.

**Acceptance Scenarios**:

1. **Given** a vendor invoice PDF, **When** uploaded, **Then** the system stores the original file without modification, generates DOC-{YYYY}-{NNNNNN}, computes SHA-256 hash, and records the original filename, MIME type, and upload timestamp.
2. **Given** a document already stored with hash ABC123, **When** the same file is uploaded again, **Then** the system detects EXACT_DUPLICATE via hash comparison and alerts the user rather than creating a second document silently.
3. **Given** a document linked to transaction TRX-2026-000151, **When** the same document is also relevant to project PRJ-2026-014, **Then** both relationships can coexist — a document may be linked to multiple entities simultaneously.

---

### User Story 5 — Track Customer Invoices and Payments (Receivables) (Priority: P2)

The Operator records a CUSTOMER_INVOICE transaction. The system automatically creates a receivable entry tracking the billed amount. Later, when a CUSTOMER_PAYMENT transaction is posted and matched to the invoice, the system reduces the outstanding receivable. Partial payments are supported. The project's collection status is derived from the sum of payments against issued invoices.

**Why this priority**: Revenue collection is critical to contractor cash flow. AR must be automated from invoice and payment transactions to avoid duplicate manual entry.

**Independent Test**: Post a customer invoice, verify a receivable is created. Post a partial payment matched to that invoice, verify the outstanding balance decreases correctly.

**Acceptance Scenarios**:

1. **Given** a CUSTOMER_INVOICE for Rp100.000.000 is posted, **When** the receivable ledger is queried, **Then** an AR entry exists with outstanding amount Rp100.000.000.
2. **Given** an outstanding AR of Rp100.000.000, **When** a CUSTOMER_PAYMENT of Rp60.000.000 is posted and matched to the invoice, **Then** the outstanding AR becomes Rp40.000.000 and collection status is PARTIALLY_PAID.
3. **Given** a second CUSTOMER_PAYMENT of Rp40.000.000 matched to the same invoice, **When** posted, **Then** the outstanding AR becomes Rp0, and collection status is PAID.

---

### User Story 6 — Track Vendor Bills and Payments (Payables) (Priority: P2)

The Operator records a VENDOR_BILL transaction. The system automatically creates a payable entry. When a PAY_VENDOR_BILL transaction is posted and matched, the payable is reduced. The cost is recognized at bill time (accrual), not at payment time — payment only settles the liability. No double-counted expense.

**Why this priority**: AP management prevents duplicate expense recognition and tracks outstanding obligations to vendors.

**Independent Test**: Post a vendor bill, verify a payable is created and project cost is recorded. Post a payment matched to that bill, verify the payable decreases but no additional expense is recorded.

**Acceptance Scenarios**:

1. **Given** a VENDOR_BILL for Rp25.000.000 is posted, **When** the payable ledger is queried, **Then** an AP entry exists with outstanding Rp25.000.000 and project cost includes this amount.
2. **Given** a PAY_VENDOR_BILL for Rp25.000.000 matched to the bill above, **When** posted, **Then** the AP entry outstanding becomes Rp0, journal entry is Dr Utang Usaha / Cr Kas dan Bank, and project cost does NOT increase again.

---

### User Story 7 — Correct a Posted Transaction via Reversal (Priority: P2)

A Manager discovers that a posted transaction was recorded incorrectly. They cannot delete or edit the posted transaction. Instead, they create a REVERSAL transaction that generates an equal-and-opposite journal entry, then create a new correct transaction. Both the original and reversal remain in the audit trail.

**Why this priority**: Data integrity requires that posted financial records are never destroyed. Reversal is the only approved correction mechanism.

**Independent Test**: Post a transaction, then create a reversal, verify the original journal remains, the reversal journal cancels it out, and a corrected transaction can be posted independently.

**Acceptance Scenarios**:

1. **Given** a posted transaction TRX-001 with journal (Dr 5101 Rp10.000.000 / Cr 1101 Rp10.000.000), **When** a REVERSAL is created referencing TRX-001, **Then** a new transaction TRX-002 is created with workflow status POSTED and journal (Dr 1101 Rp10.000.000 / Cr 5101 Rp10.000.000), and TRX-001's workflow status becomes REVERSED.
2. **Given** a posted transaction, **When** a user attempts to edit its amount or account codes directly, **Then** the system rejects the modification.

---

### User Story 8 — Manage Chart of Accounts, Payment Accounts, and Reference Data (Priority: P3)

An Admin configures the Chart of Accounts, payment accounts (specific bank accounts and cash accounts), cost categories, expense categories, and transaction types. The COA does not store balances — balances are always computed from journal lines. Payment accounts are operational detail behind the single "Kas dan Bank" reporting line.

**Why this priority**: Reference data is foundational but relatively static. It must be in place before transactions can be processed, but it changes infrequently after initial setup.

**Independent Test**: Create COA entries, payment accounts, and categories. Verify COA does not have balance fields. Verify payment accounts roll up under "Kas dan Bank" in reports.

**Acceptance Scenarios**:

1. **Given** the Admin creates COA account 1101 "Kas dan Bank" with type ASSET and normal balance DEBIT, **When** the COA is queried, **Then** the account exists without any stored balance — balance is derived from journal lines referencing account 1101.
2. **Given** payment accounts "Kas", "Bank Mandiri", "BCA" all mapped to COA 1101, **When** an account summary is generated, **Then** each payment account shows its individual balance and they aggregate to the total "Kas dan Bank" balance.

---

### Edge Cases

- What happens when a CUSTOMER_PAYMENT amount exceeds the outstanding receivable for the matched invoice? The system routes overpayments to review with AMOUNT_MISMATCH flag. After review, the user classifies the excess as: Customer Advance, payment for another invoice, unapplied payment, refund required, or correction. No automatic allocation of excess.
- How does the system handle a single payment from a customer that covers multiple invoices across different projects?
- What happens when an INTERBANK_TRANSFER is mistakenly classified as an expense?
- How does the system handle a VENDOR_ADVANCE followed by a SETTLE_VENDOR_ADVANCE that partially offsets the advance and partially becomes a new expense? The system routes to review with AMOUNT_MISMATCH when the settlement exceeds the advance balance. The user explicitly confirms the excess treatment (additional AP, immediate cost, reallocation, correction, or other). No automatic assumption about the excess.
- What happens when a transaction references a project that has been CANCELLED or CLOSED?
- How does the system handle a CUSTOMER_ADVANCE (payment received before invoice is issued)?
- What happens when a reversal is attempted on a transaction that has already been reversed?
- How does the system handle a transaction that must be split across multiple projects (e.g., shared material purchase)?
- What happens when a vendor bill arrives denominated in a currency other than IDR?
- How does the system handle the year-end closing process — does it create an opening balance journal entry?
- What happens when two documents with different content produce the same SHA-256 hash? (hash collision — astronomically unlikely but the domain should acknowledge it)
- What happens when a REIMBURSEMENT is approved but the payment is not yet made?

---

## 4. Requirements *(mandatory)*

### Functional Requirements

#### Organization & User

- **FR-001**: The system MUST support an Organization entity representing the contractor company, storing company name, legal name, tax ID (NPWP), address, and fiscal year start.
- **FR-002**: The system MUST support a User entity with unique identity, display name, email, role, and active status, capable of supporting future multi-user operation.
- **FR-003**: Every record-modifying action MUST be attributable to an authenticated user (via Created_By, Modified_By, Approved_By fields).

#### Project

- **FR-010**: The system MUST support a Project entity with all fields specified in the master concept: Project_ID, Project_Name, Customer reference, PO/SPK number, PO/SPK date, Original_Contract_Value, Variation_Order, Revised_Contract_Value, Start_Date, Target_End_Date, Actual_End_Date, PIC, Project_Status, Billing_Status, Collection_Status.
- **FR-011**: Project_ID MUST follow the format `PRJ-{YYYY}-{NNN}` and be unique within the organization.
- **FR-012**: Project_Status MUST be constrained to the approved states: PLANNED, ACTIVE, ON_HOLD, COMPLETED, CLOSED, CANCELLED.
- **FR-013**: Billing_Status MUST be derived from the sum of customer invoices relative to the revised contract value: NOT_INVOICED (no invoices), PARTIALLY_INVOICED (invoices exist but total < revised contract value), FULLY_INVOICED (total invoices ≥ revised contract value).
- **FR-014**: Collection_Status MUST be derived from payments received relative to invoices issued: NOT_DUE (no invoices yet due per their due date), PARTIALLY_PAID (some payments received but outstanding remains on due invoices), PAID (all invoices fully paid), OVERDUE (at least one invoice past its due date with outstanding balance). Due date is determined per invoice (see FR-100a).
- **FR-015**: Revised_Contract_Value MUST equal Original_Contract_Value + Variation_Order and be enforced by the system, not manually entered.

#### Transaction

- **FR-020**: The system MUST support a Transaction entity as the primary representation of a business event, containing all fields specified in the master concept section 59.
- **FR-021**: Transaction_ID MUST follow the format `TRX-{YYYY}-{NNNNNN}` and be unique within the organization.
- **FR-022**: Each transaction MUST reference exactly one Transaction_Type from the approved list.
- **FR-023**: A transaction MAY reference a Project_ID. Whether the project reference is required or optional depends on the Transaction_Type (e.g., DIRECT_PURCHASE requires a project; INTERBANK_TRANSFER does not). By default, a transaction references a single project. Optionally, a transaction may use split allocation mode to distribute its amount across multiple projects.
- **FR-023a**: When split allocation mode is used, the transaction MUST have one or more Transaction Allocation records specifying: Project_ID, allocated amount, and cost category per allocation. The sum of all allocation amounts MUST equal the transaction's total amount. The Accounting Engine MUST generate separate journal lines per project based on the allocations.
- **FR-023b**: When a transaction uses single-project mode (the default), no allocation records are needed — the full amount applies to the single referenced project.
- **FR-024**: A transaction MUST store its primary amount. For transactions involving tax, the system MUST separately store gross amount, tax base, tax amount, and net amount.
- **FR-025**: A transaction MAY reference a counterparty, which resolves to either a Vendor_ID or a Customer_ID depending on the Transaction_Type direction.
- **FR-026**: Workflow_Status is a single-value field on the transaction, tracking position in the processing pipeline.
- **FR-027**: Review flags are a multi-value association — one transaction MAY have zero or more review flags simultaneously.
- **FR-028**: A transaction in POSTED status MUST NOT be destructively modified. Fields that may be updated after posting are limited to: administrative notes, review flags (for audit annotations), and reconciliation status.

#### Transaction Type & Accounting Rule

- **FR-030**: The system MUST support all 35 approved Transaction Types as enumerated in the master concept section 29.
- **FR-031**: Each Transaction_Type MUST map to exactly one Accounting Rule that deterministically specifies: debit account(s), credit account(s), and derivation logic for amounts.
- **FR-032**: Accounting Rules MUST support rules where the specific account depends on context (e.g., DIRECT_PURCHASE debits 5101 if project-related but may debit 6xxx if not project-related; PAY_VENDOR_BILL always debits 2101 and credits 1101 regardless of project).
- **FR-033**: Accounting Rules MUST support multi-line journals where required (e.g., a transaction with tax may produce three journal lines: expense, tax payable, and cash/payable).
- **FR-034**: The Accounting Rule lookup MUST be deterministic — given a Transaction_Type and its context attributes, the same journal entry MUST always be produced.

#### Journal Entry

- **FR-040**: The system MUST represent journal entries as a header (Journal Entry) with one or more lines (Journal Lines).
- **FR-041**: Each Journal Entry MUST reference exactly one source Transaction.
- **FR-042**: Each Journal Line MUST specify: Account_Code, Debit amount, Credit amount, and optionally Project_ID and Description. Exactly one of Debit or Credit must be non-zero on each line.
- **FR-043**: Before a Journal Entry is finalized, the system MUST validate that the sum of all Debit amounts equals the sum of all Credit amounts across all lines. If not equal, posting MUST be blocked.
- **FR-044**: Journal entries MUST NOT be manually created for normal operational transactions. They are exclusively generated by the Accounting Engine upon transaction approval.
- **FR-045**: A JOURNAL_ADJUSTMENT transaction type exists for cases where a manual journal is genuinely required (e.g., year-end adjustments). Even these go through the transaction workflow and require approval. They are in the never-auto-post list.
- **FR-046**: Journal Line IDs MUST be globally unique to support ledger queries and audit trail references.

#### Chart of Accounts

- **FR-050**: The system MUST support a Chart of Accounts entity with: Account_Code, Account_Name, Account_Type (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE), Normal_Balance (DEBIT or CREDIT), Report_Group, and Active flag.
- **FR-051**: The COA MUST NOT store balance values. All account balances MUST be computed from journal lines at query time or via materialized aggregation.
- **FR-052**: The COA MUST be seeded with the approved accounts from the master concept (sections 16–28): 1101 through 8101.
- **FR-053**: Account_Code MUST be unique within the organization.
- **FR-054**: An inactive COA account MUST NOT be used in new journal entries but MUST remain queryable for historical data.

#### Payment Account

- **FR-060**: The system MUST support a Payment Account entity representing specific bank accounts and cash accounts (e.g., Kas, Petty Cash, Bank Mandiri, BCA, BRI).
- **FR-061**: Each Payment Account MUST map to a parent COA account (typically 1101 Kas dan Bank).
- **FR-062**: Financial statements MUST aggregate all payment accounts under their parent COA account line (e.g., "Kas dan Bank"), while operational records and bank reconciliation MUST distinguish individual payment accounts.
- **FR-063**: Each Payment Account MUST have a unique identifier, display name, account number (optional), bank name (optional), and active flag.

#### Document

- **FR-070**: The system MUST support a Document entity with: Document_ID, original filename, MIME type, file hash (SHA-256), file storage reference, source channel, source message ID, source chat ID, source sender, source timestamp, caption, document type, upload timestamp.
- **FR-071**: Document_ID MUST follow the format `DOC-{YYYY}-{NNNNNN}` and be unique within the organization.
- **FR-072**: The original raw document file MUST be stored immutably — it cannot be modified, overwritten, or deleted through normal operations.
- **FR-073**: Document type MUST be one of the approved types from the master concept section 34: PO_CUSTOMER, SPK, CONTRACT, VARIATION_ORDER, PURCHASE_ORDER, QUOTATION, VENDOR_INVOICE, SUBCONTRACT_AGREEMENT, TRANSFER_PROOF, RECEIPT, BANK_STATEMENT, PETTY_CASH_PROOF, SURAT_JALAN, BAST, PROGRESS_REPORT, TIMESHEET, CUSTOMER_INVOICE, CUSTOMER_RECEIPT, TAX_INVOICE, WITHHOLDING_DOCUMENT, OTHER_TAX_DOCUMENT.
- **FR-074**: The system MUST support a many-to-many relationship between Documents and Transactions (Transaction_Document_Link). One transaction may have multiple supporting documents; one document may be linked to multiple transactions.
- **FR-075**: The system MUST support linking documents to Projects independently of transactions (Project_Document_Link), for contract documents (PO, SPK, BAST) that exist at the project level.

#### Duplicate Detection

- **FR-080**: The system MUST detect exact file duplicates by comparing SHA-256 hashes at upload time. If a matching hash exists, the document is flagged as EXACT_DUPLICATE.
- **FR-081**: The system MUST detect suspected transaction duplicates by evaluating combinations of: date (same day or within configurable window), amount (exact match), payment account, recipient/counterparty, and reference number.
- **FR-082**: A suspected duplicate MUST NOT silently generate a new posted transaction. It MUST be flagged with DUPLICATE_SUSPECTED and routed to review.
- **FR-083**: The system MUST allow a user to explicitly confirm that a suspected duplicate is in fact a legitimate separate transaction, clearing the flag after review.

#### Workflow & Review

- **FR-090**: Transaction workflow status MUST be constrained to the approved states: CAPTURED, EXTRACTED, STAGED, REVIEW_REQUIRED, APPROVED, POSTED, RECONCILED, REVERSED.
- **FR-091**: Workflow transitions MUST follow the defined state machine (see section 10 — Lifecycle Rules). Invalid transitions MUST be rejected.
- **FR-092**: Review flags MUST be a separate multi-value concept from workflow status. A transaction MAY have zero or more flags simultaneously from the approved list: OCR_LOW_CONFIDENCE, MISSING_DOCUMENT, DUPLICATE_SUSPECTED, PROJECT_UNKNOWN, VENDOR_UNKNOWN, CUSTOMER_UNKNOWN, AMOUNT_MISMATCH, DATE_MISMATCH, TAX_REVIEW, ACCOUNT_REVIEW, RELATED_PARTY_REVIEW.
- **FR-093**: Any unresolved review flag MUST prevent a transaction from transitioning to APPROVED status. All flags must be resolved (cleared or overridden with justification) before approval.
- **FR-094**: The system MUST maintain a Review Queue — a filtered view of transactions in REVIEW_REQUIRED status or with unresolved review flags.
- **FR-095**: The system MUST enforce approval tiers based on transaction type for MVP. Sensitive transaction types MUST require Manager-level approval. Routine operational transaction types MAY be approved by an Operator with approval rights.
- **FR-095a**: Sensitive transaction types requiring Manager approval MUST include at minimum: OWNER_WITHDRAWAL, OWNER_CONTRIBUTION (when flagged for review), REVERSAL, JOURNAL_ADJUSTMENT, and any transaction flagged with RELATED_PARTY_REVIEW, TAX_REVIEW, or ACCOUNT_REVIEW. This list also covers tax adjustments, opening balance adjustments, year-end adjustments, write-offs, ambiguous asset capitalization, and ambiguous revenue recognition scenarios.
- **FR-095b**: The approval model MUST be designed to support future extension to additional escalation dimensions without changing the core transaction schema. Future dimensions include: amount-based thresholds, review flag combinations, user role hierarchy, and organization-level policy configuration.
- **FR-095c**: For MVP, transaction type is the sole active escalation rule. Amount-based approval thresholds are deferred pending resolution of the materiality threshold OPEN POLICY.
- **FR-095d**: A Manager MAY approve any transaction regardless of type (Manager authority is a superset of Operator authority for approval purposes).

#### Receivables (AR)

- **FR-100**: When a CUSTOMER_INVOICE transaction is posted, the system MUST automatically create or update a receivable record linking the invoice to the customer and project, with the billed amount as the outstanding balance.
- **FR-100a**: Each customer invoice MUST have a due date. The system MUST calculate a default due date from the invoice date plus a configurable organization-level payment term (e.g., Net 30 days). The user MAY override the due date per individual invoice at creation time. The payment term default MUST be stored as an organization setting. Collection_Status derivation (FR-014) uses this due date to determine OVERDUE status.
- **FR-101**: When a CUSTOMER_PAYMENT transaction is posted and matched to one or more invoices, the system MUST reduce the outstanding balance of each matched invoice accordingly.
- **FR-102**: Partial payments MUST be supported — an invoice may be paid in multiple installments.
- **FR-103**: When a CUSTOMER_PAYMENT amount exceeds the outstanding balance of the matched invoice(s), the system MUST: (a) identify the invoice outstanding amount, (b) identify the payment amount, (c) calculate the excess, (d) flag the transaction with AMOUNT_MISMATCH and route to REVIEW_REQUIRED, (e) preserve the full payment evidence without splitting or partial-posting. The system MUST NOT automatically classify or allocate the excess.
- **FR-103a**: After review, the user MUST be able to explicitly classify the excess as one of: Customer Advance (Uang Muka Customer), payment for another invoice, unapplied customer payment, refund required, or correction of an incorrect invoice/payment match. The system MUST NOT require the user to re-enter the entire payment — only the resolution of the excess.
- **FR-103b**: Until the excess is explicitly resolved, only the portion matching the outstanding invoice balance MAY be allocated. The remainder MUST remain unallocated and visible in the review queue.
- **FR-104**: When a CUSTOMER_ADVANCE is posted, the system MUST record the advance as a liability (Uang Muka Customer) until it is applied against a future invoice.

#### Payables (AP)

- **FR-110**: When a VENDOR_BILL or SUBCONTRACTOR_BILL transaction is posted, the system MUST automatically create or update a payable record linking the bill to the vendor and project, with the billed amount as the outstanding balance.
- **FR-111**: When a PAY_VENDOR_BILL or PAY_SUBCONTRACTOR transaction is posted and matched to one or more bills, the system MUST reduce the outstanding balance of each matched bill accordingly.
- **FR-112**: Partial payments MUST be supported.
- **FR-113**: When a VENDOR_ADVANCE is posted, the system MUST record the advance as an asset (Uang Muka) until it is settled against a future vendor bill via SETTLE_VENDOR_ADVANCE.

#### Advance Management

- **FR-120**: The system MUST support advances for: vendors (VENDOR_ADVANCE), employees (EMPLOYEE_ADVANCE), and customers (CUSTOMER_ADVANCE).
- **FR-121**: Each advance MUST track: original amount, settled amount, and outstanding amount.
- **FR-122**: Settlement transactions (SETTLE_VENDOR_ADVANCE, EMPLOYEE_SETTLEMENT) MUST reference the original advance and reduce the outstanding amount.
- **FR-123**: If a SETTLE_VENDOR_ADVANCE or EMPLOYEE_SETTLEMENT amount exceeds the original advance's outstanding balance, the system MUST: (a) calculate the remaining advance balance, (b) calculate the excess settlement amount, (c) flag the transaction with AMOUNT_MISMATCH and route to REVIEW_REQUIRED, (d) preserve the settlement as a single business event without splitting or partial-posting. The system MUST NOT automatically assume the excess is a new cash expense or DIRECT_PURCHASE.
- **FR-123a**: After review, the user MUST be able to explicitly confirm the treatment of the excess as one of: additional project cost creating Accounts Payable, additional project cost paid immediately, allocation to another vendor advance, correction of the settlement amount, or another valid transaction type. The system MUST NOT require the user to re-enter the entire settlement.
- **FR-123b**: After the user confirms the excess treatment, the Accounting Engine MAY generate multiple journal lines from the single transaction to reflect both the advance reduction and the user-confirmed excess treatment.

#### Project Cost

- **FR-130**: Project cost analysis MUST use Cost Category as the primary detail dimension, not separate COA accounts.
- **FR-131**: The system MUST support the approved cost categories: MAT (Material & Goods), SUB (Subcontractor), LAB (Labor), TRN (Transportation), TRV (Travel), LOG (Logistics), EQP (Equipment), SIT (Site), OTH (Other Direct Cost).
- **FR-132**: Project cost MUST be derived from posted journal entries where the debit account is 5101 (Harga Pokok Proyek) and a Project_ID is specified. Cost is not stored as a separate running total but computed from journal data, optionally with materialized aggregation.
- **FR-133**: Expense Category MUST be a separate dimension for operational expenses (COA 6xxx) not directly attributed to a project, supporting values aligned with the COA: SALARY, FEE, OFFICE_ADMIN, TRAVEL_OFFICE, PERMITS, PROFESSIONAL_SERVICE, BANK_CHARGES, DEPRECIATION, OTHER_OPERATIONAL.
- **FR-134**: The system MUST support budget tracking per project per cost category. Budget data MUST be stored as a separate concern (budget line items) that can be compared against actual cost derived from journals.
- **FR-135**: Project profit MUST be computed as: Revenue Recognized − Total Project Cost. Project margin MUST be computed as: Project Profit / Revenue Recognized × 100%.

#### Revenue Tracking

- **FR-140**: The following four values MUST be tracked independently per project and MUST NOT be conflated: Contract Value, Revenue Recognized, Invoice Issued (total of customer invoices), Cash Received (total of customer payments).
- **FR-141**: Contract Value = Original_Contract_Value + Variation_Order = Revised_Contract_Value (stored on the Project entity).
- **FR-142**: Revenue Recognized is determined by the revenue recognition policy. **[OPEN POLICY: Revenue recognition policy is not yet defined. The data model must support recording revenue recognition events as separate REVENUE_RECOGNITION transactions, independent of invoicing and cash receipt.]**
- **FR-143**: Invoice Issued MUST be the sum of all posted CUSTOMER_INVOICE transactions for the project.
- **FR-144**: Cash Received MUST be the sum of all posted CUSTOMER_PAYMENT transactions for the project.

#### Audit Trail

- **FR-150**: Every entity that represents a business record (Transaction, Journal Entry, Project, Document, Invoice/Bill, Advance, etc.) MUST store: Created_At, Created_By, Modified_At, Modified_By.
- **FR-151**: Transactions that have been approved MUST additionally store: Approved_At, Approved_By.
- **FR-152**: For meaningful changes to critical business data (amount, account, project, status, counterparty), the system MUST record change history as immutable audit log entries containing: entity type, entity ID, field changed, old value, new value, changed by, changed at, and reason (optional, required for reversals and adjustments).
- **FR-153**: The audit log MUST be append-only. Audit records MUST NOT be editable or deletable.
- **FR-154**: The specification determines that **immutable event/history records (audit log table) are preferable** to storing audit values directly on business tables. Business tables store current-state audit fields (Created_At/By, Modified_At/By, Approved_At/By). The separate audit log stores the full change history. This provides both quick access to current-state metadata and complete historical traceability.

#### Tax

- **FR-160**: The system MUST separate accounting treatment from tax treatment. Tax fields on a transaction are informational and do NOT drive the primary accounting journal.
- **FR-161**: The system MUST support tax-related fields on transactions: Tax_Relevance (boolean or enum indicating whether this transaction has tax implications), Tax_Type (e.g., PPN, PPh 21, PPh 23, PPh 4(2), PPh Final — stored as a reference, not hard-coded rates), Tax_Document_Required (boolean), Tax_Document_Available (boolean), Tax_Base, Tax_Amount, Tax_Status (PENDING, FILED, PAID, EXEMPT).
- **FR-162**: Tax rates MUST NOT be hard-coded. The system MUST support a configurable tax type reference table that can be updated when regulations change. **[OPEN POLICY: Specific tax rates, tax codes, and filing requirements are not defined in this specification per the master concept.]**

#### Cash & Bank

- **FR-170**: Cash movements (bank transfers, cash withdrawals) MUST NOT be automatically classified as expenses. The Accounting Rule Engine determines the economic substance based on Transaction_Type.
- **FR-171**: An INTERBANK_TRANSFER MUST produce journal lines that debit the destination payment account's COA and credit the source payment account's COA — both mapping to 1101, resulting in no income statement impact.
- **FR-172**: BANK_TO_CASH and CASH_TO_BANK MUST similarly produce COA-neutral journal entries that only affect the breakdown within payment accounts.

#### SaaS Architecture

- **FR-180**: All entities MUST include an organization_id foreign key to support future multi-organization operation. Single-organization operation is the initial target but the schema must not prevent multi-organization queries.
- **FR-181**: The transactional database is the system of record. Excel is NOT the primary database.
- **FR-182**: Hermes MUST NOT write directly to the production database. All data changes from external agents MUST go through the authenticated SaaS API and the normal transaction workflow (CAPTURED → EXTRACTED → STAGED → …).

### Key Entities

| Entity | Responsibility |
| ------ | -------------- |
| **Organization** | Represents the contractor company. Stores company identity, tax ID, fiscal year. Serves as the tenant boundary for all records. |
| **User** | Authenticated system user with role and permissions. Source of all Created_By / Modified_By / Approved_By references. |
| **Project** | Central organizing unit for financial analysis. Stores contract details, dates, status lifecycle, and links to customer. All cost and revenue analysis is per-project. |
| **Customer** | A party the company invoices. Stores name, contact, tax ID. Linked to projects, customer invoices, and customer payments. |
| **Vendor** | A party the company pays. Stores name, contact, tax ID, bank details. Linked to vendor bills and vendor payments. |
| **Payment Account** | Specific bank account or cash register. Maps to parent COA account. Provides operational detail behind aggregated report lines. |
| **Chart of Accounts (COA)** | Account classification. Stores code, name, type, normal balance, report group. Does NOT store balances. |
| **Transaction** | Primary business event record. Single point of capture for all financial events. Drives journal generation, AR/AP, project cost. |
| **Transaction Type** | Enumeration of approved business event categories. Each type maps to an accounting rule. |
| **Accounting Rule** | Deterministic mapping from Transaction Type (+ context) to journal entry template. Specifies debit/credit accounts and amount derivation. |
| **Journal Entry** | Double-entry accounting record header. One per posted transaction. Links to journal lines. |
| **Journal Line** | Individual debit or credit line within a journal entry. References COA account and optionally a project. |
| **Document** | Immutable record of a source file (image, PDF). Stores file reference, hash, metadata, and document type. |
| **Document Type** | Enumeration of document classifications (PO_CUSTOMER, SPK, VENDOR_INVOICE, TRANSFER_PROOF, etc.). |
| **Transaction Document Link** | Many-to-many relationship between transactions and documents. |
| **Project Document Link** | Many-to-many relationship between projects and documents (for contract-level documents). |
| **Customer Invoice** | Receivable record created when a CUSTOMER_INVOICE transaction is posted. Tracks billed amount, payments received, outstanding balance, and due date (defaulted from organization payment term, overridable per invoice). |
| **Customer Payment Allocation** | Records how a customer payment is allocated across one or more invoices. |
| **Vendor Bill** | Payable record created when a VENDOR_BILL or SUBCONTRACTOR_BILL transaction is posted. Tracks owed amount, payments made, and outstanding balance. |
| **Vendor Payment Allocation** | Records how a vendor payment is allocated across one or more bills. |
| **Advance** | Tracks prepayments to vendors, from customers, or to employees. Stores original, settled, and outstanding amounts. |
| **Cost Category** | Enumeration of project cost categories (MAT, SUB, LAB, etc.) used for project cost analysis. |
| **Expense Category** | Enumeration of operational expense categories (SALARY, FEE, OFFICE_ADMIN, etc.) for non-project overhead. |
| **Review Flag** | Multi-value flags attachable to a transaction indicating issues that require human review before approval. |
| **Audit Log** | Immutable, append-only history of changes to business records. Stores entity, field, old/new values, user, timestamp, and reason. |
| **Budget Line** | Per-project, per-cost-category budget amounts for budget vs. actual comparison. |
| **Tax Type** | Reference table of tax classifications (PPN, PPh types) without hard-coded rates. |

---

## 5. Business Rules

### BR-001: Single Input Principle
A business event MUST be captured exactly once. All downstream records (journal entries, AR/AP entries, project cost, financial report data) MUST be derived automatically from the single transaction record and its approved posting. The user MUST NOT be required to re-enter the same information into multiple records.

### BR-002: Accrual Accounting
Transactions MUST be recorded when economic rights or obligations arise, not only when cash moves. A vendor bill creates an expense and payable at bill date, regardless of when payment is made.

### BR-003: Cash Movement ≠ Expense
A bank transfer or cash movement is NOT automatically an expense. The accounting treatment depends on the Transaction Type's economic substance. An INTERBANK_TRANSFER is balance-sheet only. A PAY_VENDOR_BILL reduces a liability. Only DIRECT_PURCHASE, PETTY_CASH_EXPENSE, and similar types create expense recognition.

### BR-004: Revenue vs. Invoice vs. Cash Separation
Contract Value, Revenue Recognized, Invoice Issued, and Cash Received are four independent measures per project. They commonly differ and MUST NOT be conflated or derived from each other except as explicitly defined.

### BR-005: No Manual Debit/Credit for Normal Transactions
Users MUST NOT be presented with debit/credit account selection during normal transaction entry. The Accounting Rule Engine derives the correct journal entries from the Transaction Type and context.

### BR-006: Balance Check Before Posting
Every journal entry MUST satisfy Total Debit = Total Credit before it can transition to POSTED. The system MUST block posting of unbalanced entries.

### BR-007: Posted Transactions Are Immutable
A posted transaction's financial data (amount, accounts, project, date, type) MUST NOT be modified. Corrections MUST use the reversal pattern: original + reversal + corrected transaction.

### BR-008: Never Auto-Post Sensitive Transactions
The following transaction types MUST always require explicit Manager-level human approval and MUST NOT be auto-posted even if all confidence scores are high: OWNER_CONTRIBUTION (when review-flagged), OWNER_WITHDRAWAL, JOURNAL_ADJUSTMENT, REVERSAL, and any transaction flagged with RELATED_PARTY_REVIEW, TAX_REVIEW, or ACCOUNT_REVIEW. This includes tax adjustments, opening balance adjustments, year-end adjustments, write-offs, ambiguous asset capitalization, and ambiguous revenue recognition scenarios. Routine operational transactions (e.g., DIRECT_PURCHASE, VENDOR_BILL, CUSTOMER_PAYMENT) may be approved by an Operator with approval rights. **[OPEN POLICY: Owner transaction treatment details and amount-based escalation thresholds are not yet defined. The approval model is designed for future extension to amount + flags + role + policy-based rules.]**

### BR-009: Duplicate Prevention
File duplicates (exact hash match) MUST be detected at upload and flagged. Transaction duplicates (matching date + amount + counterparty + payment account) MUST be flagged for review. Neither type of duplicate may silently create a new posted accounting entry.

### BR-010: Document Immutability
Raw source documents MUST be stored without modification. The original file, its hash, and source metadata MUST be preserved indefinitely. Documents MUST NOT be deleted through normal operations.

### BR-011: Audit Trail Completeness
All business-critical state changes (status transitions, amount modifications, approvals, reversals) MUST be recorded in the audit log with sufficient detail to reconstruct the full history of any record.

### BR-012: Accounting Equation Integrity
At any point in time, the aggregate of all posted journal entries MUST satisfy: Total Assets = Total Liabilities + Total Equity. If this equation does not hold, financial report finalization MUST be blocked. The system MUST NOT silently adjust numbers to force balance.

### BR-013: Project Cost via Category, Not COA
Project cost detail MUST be analyzed using Cost Category (MAT, SUB, LAB, etc.) rather than creating separate COA accounts for each cost type. The COA remains small; dimensionality is provided by the cost category attribute on transactions.

### BR-014: Derived Statuses
Billing Status and Collection Status on a project MUST be computed from the actual state of related invoices and payments, not manually set by users. The system MUST update these statuses whenever the underlying invoice or payment data changes.

---

## 6. Entity Relationships & Cardinality

```
Organization (1) ──────< (many) User
Organization (1) ──────< (many) Project
Organization (1) ──────< (many) Customer
Organization (1) ──────< (many) Vendor
Organization (1) ──────< (many) Payment Account
Organization (1) ──────< (many) COA Account
Organization (1) ──────< (many) Transaction
Organization (1) ──────< (many) Document

Customer (1) ──────< (many) Project
Project (1) ──────< (many) Transaction  [via project_id; optional on transaction]
Project (1) ──────< (many) Customer Invoice
Project (1) ──────< (many) Vendor Bill
Project (1) ──────< (many) Budget Line
Project (many) >────────< (many) Document  [via Project_Document_Link]

Transaction (1) ──────< (1) Journal Entry  [1:1, one journal per posted transaction]
Journal Entry (1) ──────< (many) Journal Line  [1:N, at least 2 lines]
Journal Line (many) >──────(1) COA Account

Transaction (many) >────────< (many) Document  [via Transaction_Document_Link]
Transaction (many) >──────(1) Transaction Type
Transaction (many) >──────(0..1) Vendor  [if vendor-side transaction]
Transaction (many) >──────(0..1) Customer  [if customer-side transaction]
Transaction (many) >──────(0..1) Payment Account  [if cash involved]
Transaction (many) >──────(0..1) Project  [single-project default]
Transaction (1) ──────< (0..many) Transaction Allocation  [optional split mode]
Transaction Allocation (many) >──────(1) Project
Transaction Allocation (many) >──────(0..1) Cost Category
Transaction (many) >──────(0..1) Cost Category  [if project cost, single-project mode]
Transaction (many) >──────(0..1) Expense Category  [if operational expense]
Transaction (1) ──────< (many) Review Flag  [zero or more]

Transaction Type (1) ──────(1) Accounting Rule

Customer Invoice (many) >──────(1) Customer
Customer Invoice (many) >──────(1) Project
Customer Invoice (1) ──────(1) Transaction  [source transaction]
Customer Invoice (1) ──────< (many) Customer Payment Allocation

Customer Payment Allocation (many) >──────(1) Customer Invoice
Customer Payment Allocation (many) >──────(1) Transaction  [the payment transaction]

Vendor Bill (many) >──────(1) Vendor
Vendor Bill (many) >──────(1) Project
Vendor Bill (1) ──────(1) Transaction  [source transaction]
Vendor Bill (1) ──────< (many) Vendor Payment Allocation

Vendor Payment Allocation (many) >──────(1) Vendor Bill
Vendor Payment Allocation (many) >──────(1) Transaction  [the payment transaction]

Advance (many) >──────(0..1) Vendor
Advance (many) >──────(0..1) Customer
Advance (many) >──────(0..1) User  [employee advance]
Advance (1) ──────(1) Transaction  [source transaction]

Payment Account (many) >──────(1) COA Account  [parent account]

Budget Line (many) >──────(1) Project
Budget Line (many) >──────(1) Cost Category

Audit Log Entry ──────> references any entity by type + ID
```

---

## 7. Lifecycle & Status Rules

### 7.1 Transaction Workflow Status State Machine

```
CAPTURED ──→ EXTRACTED ──→ STAGED ──→ APPROVED ──→ POSTED ──→ RECONCILED
                              │                       │
                              ├──→ REVIEW_REQUIRED ───┘ (after flags resolved → APPROVED)
                              │         ↑
                              │         │ (new flags detected)
                              └─────────┘
                                                  POSTED ──→ REVERSED
```

**Allowed transitions:**

| From | To | Condition |
| ---- | -- | --------- |
| CAPTURED | EXTRACTED | Document extraction (OCR/parse) completed |
| EXTRACTED | STAGED | Data validated, candidate transaction created |
| STAGED | REVIEW_REQUIRED | One or more review flags detected |
| STAGED | APPROVED | No review flags; user approves |
| REVIEW_REQUIRED | STAGED | All review flags resolved/cleared |
| REVIEW_REQUIRED | APPROVED | All review flags resolved with override justification; user approves |
| APPROVED | POSTED | Accounting Engine generates balanced journal; posting succeeds |
| POSTED | RECONCILED | Bank reconciliation confirms match |
| POSTED | REVERSED | Reversal transaction posted against this transaction |

**Forbidden transitions:**

- POSTED → any state except RECONCILED or REVERSED
- REVERSED → any state (terminal)
- RECONCILED → REVERSED is allowed (discovered error after reconciliation)
- Skipping states (e.g., CAPTURED → POSTED) is forbidden

**Notes:**

- CAPTURED and EXTRACTED states are primarily for the future Hermes/document pipeline. For manually entered transactions, the initial status may be STAGED.
- A transaction may move between STAGED and REVIEW_REQUIRED multiple times as flags are raised and resolved.

### 7.2 Project Status State Machine

```
PLANNED ──→ ACTIVE ──→ ON_HOLD ──→ ACTIVE (can return)
                   ──→ COMPLETED ──→ CLOSED
                                        ↓
                                    (terminal)
PLANNED ──→ CANCELLED (terminal)
ACTIVE  ──→ CANCELLED (terminal)
ON_HOLD ──→ CANCELLED (terminal)
```

**Rules:**

- CLOSED and CANCELLED are terminal states.
- A project may toggle between ACTIVE and ON_HOLD.
- COMPLETED requires that all billable work is finished (business judgment, not a system-enforced calculation).
- CLOSED requires COMPLETED status first.
- New transactions SHOULD NOT be posted against CANCELLED or CLOSED projects. The system MUST warn but MAY allow with override justification (e.g., late-arriving vendor bill).

### 7.3 Document Lifecycle

Documents have a simpler lifecycle:

| Status | Meaning |
| ------ | ------- |
| UPLOADED | File received and stored |
| PROCESSED | Extraction/OCR completed (future) |
| LINKED | Associated with at least one transaction or project |
| ARCHIVED | Retained for audit but no longer in active use |

Documents are never deleted.

### 7.4 Invoice/Bill Status

| Status | Meaning |
| ------ | ------- |
| OPEN | Issued, payment outstanding |
| PARTIALLY_PAID | Some payment received/made |
| PAID | Fully settled |
| OVERDUE | Past due date with outstanding balance |
| CANCELLED | Invoice/bill voided (via reversal of source transaction) |

---

## 8. Required vs. Optional Data

### Transaction — Required Fields

| Field | Required | Condition |
| ----- | -------- | --------- |
| Transaction_ID | Always | System-generated |
| Date | Always | |
| Transaction_Type | Always | |
| Amount | Always | > 0 |
| Workflow_Status | Always | System-managed |
| Created_At | Always | System-generated |
| Created_By | Always | System-generated |
| Description | Always | May be auto-generated from context |
| Organization_ID | Always | System-derived |

### Transaction — Conditionally Required Fields

| Field | Condition |
| ----- | --------- |
| Project_ID | Required for project-related types (DIRECT_PURCHASE, VENDOR_BILL, SUBCONTRACTOR_BILL, CUSTOMER_INVOICE, etc.). Optional for non-project types (INTERBANK_TRANSFER, BANK_CHARGE, OWNER_CONTRIBUTION, etc.) |
| Vendor_ID | Required for vendor-side types (VENDOR_BILL, PAY_VENDOR_BILL, VENDOR_ADVANCE, SUBCONTRACTOR_BILL, etc.) |
| Customer_ID | Required for customer-side types (CUSTOMER_INVOICE, CUSTOMER_PAYMENT, CUSTOMER_ADVANCE) |
| Payment_Account_ID | Required when cash movement is involved (payments, transfers, direct purchases). Not required for accrual-only entries (VENDOR_BILL, CUSTOMER_INVOICE) |
| Cost_Category | Required when Transaction_Type involves project cost (DIRECT_PURCHASE with project, VENDOR_BILL, SUBCONTRACTOR_BILL, etc.) |
| Expense_Category | Required when Transaction_Type involves operational expense (types debiting 6xxx accounts) |
| Invoice_Reference | Required for payment-matching types (PAY_VENDOR_BILL, CUSTOMER_PAYMENT) |

### Transaction — Optional Fields

| Field | Notes |
| ----- | ----- |
| PO_SPK_Reference | Link to purchase order or contract |
| Tax_Relevance | Defaults to false |
| Tax_Type | Required if Tax_Relevance is true |
| Tax_Base | Required if Tax_Relevance is true |
| Tax_Amount | Required if Tax_Relevance is true |
| Confidence scores | Populated by automation/Hermes, null for manual entry |
| Counterparty_Name | Free-text fallback when Vendor/Customer not yet registered |

### Project — Required Fields

| Field | Required |
| ----- | -------- |
| Project_ID | Always (system-generated) |
| Project_Name | Always |
| Customer_ID | Always |
| Original_Contract_Value | Always |
| Start_Date | Always |
| Project_Status | Always (default: PLANNED) |
| Organization_ID | Always |

### Project — Optional Fields

| Field | Notes |
| ----- | ----- |
| PO_SPK_No | May not be available at project creation |
| PO_SPK_Date | May not be available at project creation |
| Variation_Order | Defaults to 0 |
| Target_End_Date | Recommended but not always known |
| Actual_End_Date | Set when project completes |
| PIC | Recommended |

---

## 9. Posting Invariants

These invariants MUST hold at all times and MUST be enforced by the system:

1. **Journal Balance**: For every posted journal entry, `SUM(debit) = SUM(credit)` across all lines.
2. **Accounting Equation**: Across all posted journal entries, `Total Assets = Total Liabilities + Total Equity`. This is verified at report generation time.
3. **AR Consistency**: For every customer invoice, `Outstanding = Billed Amount − SUM(allocated payments)`. Outstanding MUST NOT be negative under normal operation.
4. **AP Consistency**: For every vendor bill, `Outstanding = Bill Amount − SUM(allocated payments)`. Outstanding MUST NOT be negative under normal operation.
5. **Advance Consistency**: For every advance, `Outstanding = Original Amount − SUM(settlement allocations)`. Outstanding MUST NOT be negative.
6. **Contract Value**: `Revised_Contract_Value = Original_Contract_Value + Variation_Order` MUST hold.
7. **No Orphan Journals**: Every journal entry MUST reference exactly one source transaction. No journal entry may exist without a parent transaction.
8. **Single Journal Per Transaction**: A posted transaction produces exactly one journal entry. A reversal is a new transaction with its own journal entry.
9. **Immutable Posted Data**: No posted transaction's financial fields (date, amount, type, accounts) may be modified after posting.

---

## 10. Data Integrity Requirements

- **DI-001**: All ID fields (Transaction_ID, Document_ID, Project_ID, etc.) MUST be unique within the organization scope.
- **DI-002**: Foreign key references (Project_ID on Transaction, Account_Code on Journal Line, etc.) MUST reference valid, existing records.
- **DI-003**: Enum fields (Transaction_Type, Workflow_Status, Project_Status, etc.) MUST be constrained to their defined value sets. Invalid values MUST be rejected.
- **DI-004**: Amount fields MUST be stored with sufficient precision for Indonesian Rupiah (IDR). Since IDR has no decimal subdivision in practice, integer storage (in Rupiah) is acceptable. However, the system SHOULD support at least 2 decimal places to handle any future requirement for sub-Rupiah precision (e.g., unit price calculations, tax rounding).
- **DI-005**: Date fields MUST store timezone-aware timestamps. The system operates in WIB (UTC+7) as the default business timezone.
- **DI-006**: The audit log MUST be append-only. No DELETE or UPDATE operations are permitted on audit log records.
- **DI-007**: Document file hash MUST be computed upon upload and stored. If the stored hash does not match the file content at any point, a data integrity alert MUST be raised.
- **DI-008**: A transaction MUST NOT reference an inactive COA account, an inactive vendor, an inactive customer, or an inactive payment account in new postings. Historical records referencing subsequently-deactivated entities MUST remain valid.

---

## 11. Duplicate Handling Rules

### File Duplicate Detection

| Check | Method | Action |
| ----- | ------ | ------ |
| Exact file duplicate | SHA-256 hash comparison | Flag as EXACT_DUPLICATE. Existing document is referenced; no new document record is created. User is informed and may link the existing document to a new transaction if appropriate. |

### Transaction Duplicate Detection

| Check | Fields Compared | Action |
| ----- | --------------- | ------ |
| Strong match | Date (same day) + Amount (exact) + Payment Account + Counterparty | Flag as DUPLICATE_SUSPECTED. Transaction is created but moved to REVIEW_REQUIRED. |
| Moderate match | Date (±3 days) + Amount (exact) + Counterparty | Flag as DUPLICATE_SUSPECTED with lower confidence. Route to review. |
| Reference match | Invoice_Reference or PO_SPK_Reference matches an already-posted transaction | Flag for review. May be a legitimate follow-up (e.g., second payment on same invoice) or a duplicate. |

### Resolution

- A human reviewer MUST explicitly confirm or reject the duplicate suspicion.
- If confirmed as NOT a duplicate: the DUPLICATE_SUSPECTED flag is cleared with justification, and the transaction proceeds.
- If confirmed as duplicate: the transaction is discarded (not posted) and linked to the original for audit purposes.

---

## 12. Open Policy Items

The master concept explicitly leaves these policies unresolved. The data model MUST accommodate them without hard-coding assumptions:

| Policy | Impact on Model | How Accommodated |
| ------ | --------------- | ---------------- |
| **Revenue recognition policy** | Determines when and how REVENUE_RECOGNITION transactions are created | Model supports REVENUE_RECOGNITION as a distinct transaction type with its own accounting rule. The rule can be configured once the policy is defined. FR-142 marks this as open. |
| **Asset capitalization threshold** | Determines whether a purchase is ASSET_PURCHASE or DIRECT_PURCHASE/expense | Model supports both transaction types. Classification depends on the policy threshold, which can be configured. |
| **Asset useful life & depreciation method** | Affects periodic depreciation journal entries | Model does not include depreciation scheduling in Phase 2. The COA includes 1502 Akumulasi Penyusutan and 6108 Penyusutan to support future depreciation journals. |
| **Inventory policy** | Determines INVENTORY_PURCHASE vs. direct expense treatment | Model supports INVENTORY_PURCHASE and INVENTORY_USAGE transaction types with appropriate accounting rules. Policy determines when each is used. |
| **Owner transaction treatment** | Owner draws and contributions may have special accounting or tax implications | Model supports OWNER_CONTRIBUTION and OWNER_WITHDRAWAL types. These are in the never-auto-post list. Treatment details are deferred. |
| **Formal accounting standard (SAK)** | May impose additional disclosure or classification requirements | Model follows general double-entry principles. Specific SAK requirements can be layered on without schema changes. |
| **Tax rates and codes** | Specific rates for PPN, PPh 21/23/4(2)/Final | Tax_Type is a configurable reference table. No rates are hard-coded. |
| **Cutoff period** | Determines fiscal period boundaries for accrual adjustments | Model stores transaction dates; period assignment can be derived. Year-end adjustment is supported via JOURNAL_ADJUSTMENT. |
| **Materiality threshold** | Affects rounding, write-off, and variance tolerance decisions | Not encoded in Phase 2. Can be added as a configuration parameter. |

---

## 13. Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every domain entity defined in this specification can be instantiated with all required fields and persisted without data loss or constraint violation.
- **SC-002**: The Accounting Rule Engine, given any of the 35 approved Transaction Types with valid context, produces a journal entry where Total Debit = Total Credit — verified for every transaction type.
- **SC-003**: A complete business cycle (Project creation → Vendor Bill → Bill Payment → Customer Invoice → Customer Payment) can be executed through the domain model, with correct AR/AP balances at every step and zero double-counted expenses.
- **SC-004**: The accounting equation (Assets = Liabilities + Equity) holds after posting any valid combination of the 35 transaction types — verified by automated test suite.
- **SC-005**: Duplicate detection identifies 100% of exact file duplicates (same SHA-256 hash) and flags at least 95% of suspected transaction duplicates (same date + amount + counterparty + payment account).
- **SC-006**: A posted transaction cannot be modified through any API or data operation. Only reversal can create a correcting entry — verified by attempting direct modification and confirming rejection.
- **SC-007**: The domain model can represent all data required to generate: General Ledger, Trial Balance, Income Statement, Balance Sheet, Cash Flow, AR Aging, AP Aging, Project P&L, Project Cash Position, and Budget vs. Actual — verified by tracing each report's required data to specific entities and fields.
- **SC-008**: Every state transition in the transaction workflow and project lifecycle follows the defined state machine — invalid transitions are rejected 100% of the time.
- **SC-009**: The audit log captures all business-critical changes with old value, new value, user, and timestamp — verified by modifying a transaction field and confirming the audit record is created.
- **SC-010**: Cost category analysis per project produces the same total as the sum of journal lines debiting account 5101 for that project — verified for data consistency.

---

## 14. Assumptions

- The system operates for a single Indonesian contractor company in the initial deployment. The Organization entity exists to support future multi-organization capability without requiring schema migration, but multi-tenant isolation complexity is deferred.
- Indonesian Rupiah (IDR) is the sole operating currency. Multi-currency support is out of scope. Foreign-currency vendor bills, if encountered, are converted to IDR at the time of entry.
- The COA is seeded with the approved accounts from the master concept and is modifiable by Admin users. New accounts can be added within the established structure (1xxx–8xxx).
- The 35 approved Transaction Types cover the known business scenarios. New types can be added by extending the enumeration and defining a corresponding Accounting Rule.
- Hermes integration is a future concern. The domain model and business rules are designed to work correctly whether transactions are entered manually by an Operator or submitted programmatically by Hermes through the API. The Hermes boundary is enforced at the API layer, not in the domain model.
- Bank reconciliation (matching bank statements to book transactions) is a Phase 6 concern. The RECONCILED workflow status exists in the model but reconciliation logic is not specified here.
- Multi-user permissions and role-based access control are acknowledged by the User entity but detailed permission rules are not specified in Phase 2. The model supports user attribution for all actions.
- Performance targets (e.g., maximum response time for ledger queries, concurrent user count) are not specified in Phase 2. The domain model should be designed to support efficient querying but performance optimization is an implementation concern.
- The document storage mechanism (local filesystem, cloud object storage) is an implementation decision. The domain model specifies the metadata that must be captured, not the storage technology.

---

## 15. Open Questions

1. **Revenue Recognition Timing**: The master concept defines REVENUE_RECOGNITION as a separate transaction type, but does not specify when it should be triggered. Should revenue be recognized at invoice issuance, at BAST acceptance, at percentage-of-completion milestones, or at project completion? This is marked as [OPEN POLICY] and must be decided before implementing the revenue recognition transaction flow.

2. ~~**Multi-Project Transaction Splitting**~~: **RESOLVED** — The system defaults to single-project transactions but offers an optional split allocation mode. When split mode is used, Transaction Allocation records distribute the amount across projects, and the Accounting Engine generates per-project journal lines. See FR-023, FR-023a, FR-023b.

3. ~~**Advance Settlement Excess Handling**~~: **RESOLVED** — When a SETTLE_VENDOR_ADVANCE exceeds the outstanding advance balance, the system routes to review with AMOUNT_MISMATCH. The user confirms the excess treatment before posting. The Accounting Engine may generate multiple journal lines from the single transaction after user confirmation. See FR-123, FR-123a, FR-123b.
