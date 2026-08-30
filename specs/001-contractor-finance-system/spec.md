# Feature Specification: Contractor Financial Automation System

**Feature Branch**: `001-contractor-finance-system`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Sistem Keuangan Otomatis Perusahaan Kontraktor — single input, project-based accounting, WhatsApp + Hermes AI agent, Excel financial database"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a Transaction from Document (Priority: P1)

A company user (non-accountant) receives a vendor invoice or transfer receipt and needs to record it in the financial system. The user submits the document (photo, screenshot, or PDF) through WhatsApp or the system interface. Hermes — the AI agent — reads the document, extracts key data (date, amount, vendor/customer, reference numbers), identifies the transaction type, matches it to a project and any existing invoices, and presents a candidate transaction for review. The user reviews the summary and approves it with one tap. The system then automatically generates the correct double-entry journal, updates project costs, updates outstanding receivables/payables, and refreshes dashboards — all from that single input.

**Why this priority**: This is the core value proposition of the entire system. Without the ability to turn a document into a posted financial transaction, nothing else functions. It validates the single-input principle, the Hermes extraction pipeline, and the accounting rule engine.

**Independent Test**: Can be fully tested by submitting a sample vendor invoice image, verifying Hermes extracts the correct data, presents the right transaction type, and upon approval generates a balanced journal entry with the correct COA accounts.

**Acceptance Scenarios**:

1. **Given** a vendor invoice image for Rp25.000.000 linked to Project PRJ-2026-014, **When** the user submits it via the input channel, **Then** Hermes extracts the amount, vendor, project, and invoice number, classifies it as VENDOR_BILL, and presents a candidate transaction with confidence scores.
2. **Given** a candidate transaction in READY_FOR_APPROVAL status, **When** the user approves it, **Then** the system generates a journal entry (Dr Harga Pokok Proyek / Cr Utang Usaha), updates project cost for PRJ-2026-014, and the transaction status becomes POSTED.
3. **Given** a transfer screenshot with insufficient information (no matching project or vendor), **When** Hermes cannot confidently classify the transaction, **Then** the status is set to REVIEW_REQUIRED with appropriate review flags (e.g., PROJECT_UNKNOWN, MISSING_DOCUMENT) and the user is prompted to provide missing details.
4. **Given** a document that is an exact duplicate of a previously submitted file (same SHA256 hash), **When** the user submits it, **Then** the system detects the duplicate, flags it as EXACT_DUPLICATE, and does not create a new transaction.

---

### User Story 2 - Project Financial Tracking (Priority: P1)

A company manager wants to see the financial health of each active project — how much has been spent vs. budgeted, what the current margin is, outstanding invoices, and cash position. The system automatically aggregates all posted transactions by Project_ID and presents a project-level profit & loss statement, budget vs. actual comparison, and cash flow summary.

**Why this priority**: Project-based analysis is the central organizing principle. Contractors make decisions at the project level — whether a project is profitable, whether spending is on track, and whether cash is flowing properly. Without project tracking, the system is just generic bookkeeping.

**Independent Test**: Can be tested by posting several transactions against a project and verifying the project P&L, budget vs. actual, and cash position reports are accurate.

**Acceptance Scenarios**:

1. **Given** a project PRJ-2026-014 with posted transactions totaling Rp150.000.000 in costs and Rp200.000.000 in recognized revenue, **When** the user views the project report, **Then** the system displays Project Profit of Rp50.000.000 and margin of 25%.
2. **Given** a project with a material budget of Rp50.000.000 and actual material costs of Rp60.000.000, **When** the budget vs. actual report is viewed, **Then** it shows a variance of Rp10.000.000 unfavorable and Hermes provides a warning.
3. **Given** a project with invoices issued for Rp800.000.000 and payments received of Rp500.000.000, **When** the project cash information is viewed, **Then** the outstanding receivable is shown as Rp300.000.000.

---

### User Story 3 - Customer Invoicing and Payment Tracking (Priority: P2)

The company issues invoices to customers for project work and needs to track which invoices have been paid, which are partially paid, and which are overdue. When the user records a customer invoice, the system automatically creates the AR entry. When a payment is received and submitted, Hermes matches the payment to the outstanding invoice and updates the receivable balance.

**Why this priority**: Revenue collection is critical to contractor cash flow. Tracking invoices and payments prevents revenue leakage and enables the company to follow up on overdue accounts.

**Independent Test**: Can be tested by creating a customer invoice, then submitting a payment document and verifying the receivable balance decreases correctly.

**Acceptance Scenarios**:

1. **Given** a new customer invoice for Rp100.000.000 on project PRJ-2026-014, **When** the invoice is recorded, **Then** the system creates a journal entry (Dr Piutang Usaha Rp100.000.000 / Cr Pendapatan Proyek dan Jasa Rp100.000.000), sets Billing Status to PARTIALLY_INVOICED, and the invoice appears in the AR ledger.
2. **Given** an outstanding invoice INV-032/2026 for Rp100.000.000, **When** a customer payment of Rp60.000.000 is recorded and matched, **Then** the system generates a journal (Dr Kas dan Bank / Cr Piutang Usaha), the outstanding balance becomes Rp40.000.000, and Collection Status updates to PARTIALLY_PAID.
3. **Given** an invoice that is past its due date with no payment recorded, **When** the aging report is viewed, **Then** the invoice appears in the overdue category.

---

### User Story 4 - Vendor Bill and Payment Management (Priority: P2)

The company receives bills from vendors and subcontractors and needs to track outstanding payables. When a vendor bill is recorded, the system creates the AP entry. When payment is made and the transfer proof is submitted, Hermes matches the payment to the bill and updates the payable balance, ensuring costs are not double-counted.

**Why this priority**: Managing payables prevents double payments, tracks outstanding obligations, and ensures project costs are accurately recorded when the bill is received (accrual basis), not when payment is made.

**Independent Test**: Can be tested by recording a vendor bill, then submitting a payment proof and verifying the payable balance decreases and no duplicate expense is recorded.

**Acceptance Scenarios**:

1. **Given** a vendor bill for Rp25.000.000 on project PRJ-2026-015, **When** the bill is recorded, **Then** the system creates a journal (Dr Harga Pokok Proyek / Cr Utang Usaha), the bill appears in AP, and project cost for the project is updated.
2. **Given** an outstanding vendor bill for Rp25.000.000, **When** a payment of Rp25.000.000 is submitted with matching vendor and invoice reference, **Then** the system generates a journal (Dr Utang Usaha / Cr Kas dan Bank), the AP balance for this bill becomes zero, and no additional expense is recorded.

---

### User Story 5 - Financial Statements Generation (Priority: P2)

The company owner or manager wants to see the overall financial position — Balance Sheet (Neraca), Income Statement (Laba Rugi), and Cash Flow — generated automatically from posted journal entries. No manual data entry into report templates. The reports must satisfy the accounting equation (Assets = Liabilities + Equity).

**Why this priority**: Financial statements are the ultimate output of the system and the basis for business decisions, tax compliance, and stakeholder reporting. However, they depend on the transaction processing and journal engine being functional first.

**Independent Test**: Can be tested by posting a set of representative transactions and verifying the generated financial statements balance correctly and match expected totals.

**Acceptance Scenarios**:

1. **Given** a set of posted journal entries across multiple projects, **When** the Income Statement is generated, **Then** it shows correct totals for Revenue, Cost of Project (Harga Pokok Proyek), Gross Profit, Operating Expenses, and Net Profit, matching the structure defined in the concept document.
2. **Given** the same posted journal entries, **When** the Balance Sheet is generated, **Then** Assets = Liabilities + Equity holds true. If it does not balance, report finalization is blocked.
3. **Given** posted transactions over a date range, **When** the Cash Flow report is generated, **Then** it accurately reflects cash inflows and outflows by category.

---

### User Story 6 - Dashboard and AI Management Insights (Priority: P3)

The dashboard provides a real-time overview of key financial metrics: cash position, revenue, project costs, gross and net profit, receivables, payables, active projects, and outstanding invoices. Hermes proactively surfaces management insights such as low-margin projects, budget overruns, overdue invoices, unusual transactions, and missing documents.

**Why this priority**: While valuable, the dashboard and insights are a presentation layer on top of the core data. They enhance decision-making but require the underlying transaction, journal, and project data to be in place first.

**Independent Test**: Can be tested by populating sample data and verifying dashboard metrics match computed values, and that Hermes generates appropriate alerts for predefined conditions (e.g., margin below threshold).

**Acceptance Scenarios**:

1. **Given** active projects with posted transactions, **When** the dashboard is loaded, **Then** it displays current Cash & Bank balance, Total Revenue, Total Project Cost, Gross Profit, Operating Expenses, Net Profit, Total Receivables, Total Payables, count of Active Projects, and Outstanding Invoices.
2. **Given** a project with a margin of 8.4% (below the company average), **When** Hermes runs analysis, **Then** it generates an alert identifying the project, the low margin, and the top cost driver causing it.
3. **Given** an invoice that has been overdue for more than 30 days, **When** the system checks collection status, **Then** Hermes generates an overdue invoice alert with the customer, amount, and days overdue.

---

### User Story 7 - WhatsApp Document Submission (Priority: P3)

A field user submits a document (photo of receipt, screenshot of transfer, invoice PDF) via WhatsApp. The system receives the document, downloads and stores it with a generated Document ID, preserves the original file with hash verification, and initiates the Hermes extraction pipeline. The user receives a confirmation via WhatsApp with the candidate transaction summary and can approve or flag for review.

**Why this priority**: WhatsApp is the intended primary input channel for daily operations, but the core financial engine must work first. WhatsApp integration is an input convenience layer that can be added once the processing pipeline is proven reliable.

**Independent Test**: Can be tested by sending a document via WhatsApp to the system, verifying it is stored with correct metadata (hash, source channel, timestamp), and that Hermes initiates extraction.

**Acceptance Scenarios**:

1. **Given** a user in a WhatsApp group sends a photo of a vendor receipt with caption "Material proyek Docking Kapal A", **When** the system receives the message, **Then** it downloads the file, stores it in raw_documents/{year}/{month}/ with a generated DOC ID, computes a SHA256 hash, and begins extraction.
2. **Given** Hermes completes extraction with high confidence, **When** the candidate transaction is ready, **Then** the user receives a WhatsApp message showing the candidate summary (amount, vendor, project, transaction type, confidence) with options to approve or request review.

---

### Edge Cases

- What happens when a single payment covers multiple invoices from different projects?
- How does the system handle a partial payment that does not exactly match any single invoice amount?
- What happens when a vendor is not yet registered in the system (new vendor)?
- How does the system behave when OCR confidence is below acceptable threshold for a critical field (e.g., amount)?
- What happens when a transaction could reasonably be classified as either an asset purchase or a project expense?
- How does the system handle a transfer between two company bank accounts (interbank transfer that is not an expense)?
- What happens when a posted transaction is found to be incorrect and needs correction?
- How does the system handle documents submitted in non-standard formats or low-quality images?
- What happens when the accounting equation does not balance during report generation?
- How does the system handle year-end closing and opening balance setup?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support single-input principle — each business event is entered exactly once; all downstream records (journal, AR/AP, project cost, reports) are derived automatically.
- **FR-002**: System MUST use accrual-basis accounting — transactions are recorded when economic rights/obligations arise, not only when cash moves.
- **FR-003**: System MUST enforce double-entry bookkeeping — every posted journal entry must satisfy Total Debit = Total Credit; posting is blocked if unbalanced.
- **FR-004**: System MUST classify each transaction by Transaction Type (from the defined list of 30+ types) which deterministically maps to the correct journal entry via the Accounting Rule Engine.
- **FR-005**: System MUST associate transactions with a Project_ID when applicable, enabling project-based cost tracking and profit analysis.
- **FR-006**: System MUST maintain separate tracking for Contract Value, Revenue Recognized, Invoice Issued, and Cash Received per project — these four values can differ and must not be conflated.
- **FR-007**: System MUST automatically generate journal entries from approved transactions — users do not manually enter debit/credit entries.
- **FR-008**: System MUST manage Accounts Receivable automatically — creating AR entries when customer invoices are recorded and reducing them when payments are matched.
- **FR-009**: System MUST manage Accounts Payable automatically — creating AP entries when vendor bills are recorded and reducing them when payments are made.
- **FR-010**: System MUST detect duplicate documents using SHA256 file hashing and flag suspected transaction duplicates based on date, amount, bank, recipient, and reference.
- **FR-011**: System MUST route ambiguous or low-confidence transactions to a Review Queue with appropriate review flags rather than auto-posting them.
- **FR-012**: System MUST maintain a complete audit trail for all important records, including creation, modification, and approval metadata with timestamps and user identity.
- **FR-013**: System MUST correct posted transactions via reversal entries — posted transactions cannot be deleted or overwritten.
- **FR-014**: System MUST generate financial statements (Income Statement, Balance Sheet, Cash Flow) from journal/database data — no manually entered report figures.
- **FR-015**: System MUST validate the accounting equation (Assets = Liabilities + Equity) before finalizing any financial report; if unbalanced, finalization is blocked.
- **FR-016**: System MUST store original documents in a raw_documents archive without modification, with hash/checksum for integrity verification.
- **FR-017**: System MUST use the simplified Chart of Accounts (COA) structure defined in the concept, with detail handled through Transaction Type, Project, Cost Category, Expense Category, Vendor, Customer, Payment Account, and Tax Type dimensions.
- **FR-018**: System MUST extract data from submitted documents (OCR for images, parsing for PDFs) and produce multi-dimensional confidence scores (OCR, Identity, Document Match, Project, Classification).
- **FR-019**: System MUST support a defined workflow status lifecycle for transactions: CAPTURED → EXTRACTED → STAGED → REVIEW_REQUIRED → APPROVED → POSTED → RECONCILED (with REVERSED as a correction state).
- **FR-020**: System MUST never auto-post sensitive transaction types in MVP: owner transactions, related-party transactions, tax adjustments, opening balance adjustments, asset capitalization when ambiguous, revenue recognition when ambiguous, write-offs, manual journal adjustments, reversals, and year-end adjustments.
- **FR-021**: System MUST provide project-level reporting including Project P&L, Budget vs. Actual comparison, and Project Cash Position.
- **FR-022**: System MUST categorize project costs using the defined Cost Category taxonomy (MAT, SUB, LAB, TRN, TRV, LOG, EQP, SIT, OTH).
- **FR-023**: System MUST separate accounting treatment from tax treatment — tax fields (Tax_Relevance, Tax_Type, Tax_Document_Required, etc.) exist alongside but independent from accounting entries.
- **FR-024**: System MUST distinguish between cash movement and expense recognition — a bank transfer is not automatically an expense; the system must determine the economic substance (bill payment, advance, direct purchase, asset purchase, etc.).
- **FR-025**: System MUST provide a dashboard showing key financial metrics: Cash & Bank balance, Revenue, Project Cost, Gross Profit, Operating Expenses, Net Profit, Receivables, Payables, Active Projects, Outstanding Invoices, and Cash Flow.

### Key Entities

- **Project**: A contractor engagement with a customer, carrying contract value, dates, status (PLANNED/ACTIVE/ON_HOLD/COMPLETED/CLOSED/CANCELLED), billing status, and collection status. Central organizing unit for all financial analysis.
- **Transaction**: A single business event captured once, containing type, amount, project association, counterparty, cost/expense category, payment account, linked documents, confidence scores, workflow status, and review flags.
- **Journal Entry**: An automatically generated double-entry record derived from an approved transaction, containing account code, debit/credit amounts, project reference, and description. Users do not create these directly.
- **Document**: A raw file (image, PDF, etc.) submitted as evidence of a business event, stored with integrity hash, source metadata (WhatsApp channel, sender, timestamp), and linked to transactions and projects.
- **Vendor**: A supplier or subcontractor the company pays for goods and services, linked to bills and payments.
- **Customer**: A party the company invoices for project work, linked to invoices and payments received.
- **Chart of Accounts (COA)**: A simplified account structure (Assets 1xxx, Liabilities 2xxx, Equity 3xxx, Revenue 4xxx, COGS 5xxx, OpEx 6xxx, Other 7xxx-8xxx) that does not store balances — balances are computed from journals.
- **Invoice (AR)**: A customer invoice tracking billed amount, payments received, and outstanding balance per project.
- **Bill (AP)**: A vendor bill tracking owed amount, payments made, and outstanding balance per project.
- **Payment Account**: A specific bank account or cash account (Kas, Mandiri, BCA, BRI, Petty Cash, etc.) used for transactions, aggregated under a single "Kas dan Bank" line in reports.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can record a financial transaction from a document in under 2 minutes — submit document, review Hermes' candidate, approve — without entering debit/credit or manual journal entries.
- **SC-002**: 95% of transactions submitted with supporting documents are correctly classified by Hermes on the first attempt (correct Transaction Type, Project, and Cost Category), requiring no manual correction.
- **SC-003**: All generated financial reports (Balance Sheet, Income Statement) satisfy the accounting equation (Assets = Liabilities + Equity) with zero tolerance — any imbalance blocks finalization.
- **SC-004**: Project profit/loss reports are available in real-time and reflect all posted transactions within 5 seconds of the most recent posting.
- **SC-005**: Zero double-counted expenses — when a vendor bill is recorded and later paid, the cost appears exactly once in project cost and income statement.
- **SC-006**: Outstanding receivables and payables are accurate to within Rp0 variance — the sum of all AR entries matches the Piutang Usaha balance, and the sum of all AP entries matches the Utang Usaha balance.
- **SC-007**: Users with no accounting background can complete all standard daily operations (submit documents, review transactions, approve postings, view project reports) without training beyond an initial 30-minute orientation.
- **SC-008**: Every posted transaction can be traced back to its source document, with a complete audit trail showing who created, modified, and approved each record and when.
- **SC-009**: Duplicate documents are detected with 100% accuracy (via file hash), and suspected duplicate transactions are flagged with zero false negatives (all true duplicates caught), accepting up to 5% false positives.
- **SC-010**: Dashboard key financial metrics (cash balance, revenue, receivables, payables) update within 10 seconds of a transaction being posted.

## Assumptions

- The company is a small-to-medium Indonesian contractor/project-based company using Indonesian language for day-to-day operations and Indonesian Rupiah (IDR/Rp) as the primary currency.
- The initial MVP will use Excel as the financial database, with the workbook structure defined in the concept document. Migration to a proper database can happen in later phases.
- Users have access to WhatsApp on their mobile devices and will use it as the primary document submission channel. A web/desktop interface will also be available as an alternative input method.
- Hermes (the AI agent) has access to OCR capabilities and can process common image formats (JPEG, PNG) and PDF documents.
- The company operates a single legal entity — multi-entity consolidation is out of scope for MVP.
- Tax rates and tax policies are not hard-coded; they will be configurable and require manual verification against current regulations before use.
- Revenue recognition policy, asset capitalization thresholds, depreciation methods, and inventory policies will be defined by the company and configured in the system — Hermes does not make these policy decisions autonomously.
- The system will follow Indonesian accounting standards (SAK) as general guidance, but formal compliance certification is out of scope for MVP.
- Internet connectivity is available for WhatsApp integration and cloud-based OCR processing.
- The MVP focuses on the core financial cycle (document → transaction → journal → report); bank reconciliation, advanced tax management, and AI analytics are planned for subsequent phases as outlined in the implementation roadmap (Phases 5-11).
