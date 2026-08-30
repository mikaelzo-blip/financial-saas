# Feature Specification: Web SaaS Application — Core Operational UI

**Feature Branch**: `003-core-operational-ui`

**Created**: 2026-08-30

**Status**: Draft (Clarified & Complete)

**Input**: User description: "WEB SAAS APPLICATION — CORE OPERATIONAL UI. Design the web SaaS operational interface for an Indonesian contractor company. The application must be simple enough for non-accountants while using the existing financial backend for all accounting logic. Core principle: Simple for user, structured underneath."

**Authoritative Sources**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)
- [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)
- [specs/002-core-financial-domain-model/contracts/openapi.yaml](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/contracts/openapi.yaml)

---

## Clarifications

### Session 2026-08-30

- **Q1 (Authentication UX)**: What is the minimum login and session behavior required for MVP? → **A**: Standard email/password login screen saving JWT access token in browser session/local storage, automatically attached as `Bearer` header on all API requests. Automatic redirect to `/login` on 401 Unauthorized with token expiration notice.
- **Q2 (User Roles & Permissions)**: What can Operator, Manager, and Admin see and do? → **A**:
  - *Operator*: Day-to-day data entry (Transactions, Projects, Invoices, Bills, Documents) and routine operational approvals.
  - *Manager*: Full visibility on all operational metrics, project profitabilities, cash summaries, and exclusive authority to approve sensitive transaction types (`OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`, `JOURNAL_ADJUSTMENT`) and trigger reversals.
  - *Admin*: Master data management (Users, COA, Payment Accounts, Organization settings).
  - *Backend Authority*: Frontend hides/disables unauthorized action buttons, while the backend remains the strict authoritative enforcement barrier (returning 403 Forbidden).
- **Q3 (Primary Navigation)**: How should primary navigation be structured? → **A**: Flat, single-level sidebar navigation to minimize nesting:
  1. *Dashboard* (`/dashboard`)
  2. *Proyek* (`/projects`)
  3. *Transaksi* (`/transactions`)
  4. *Dokumen* (`/documents`)
  5. *Pelanggan / Customer* (`/customers`)
  6. *Vendor & Subkon* (`/vendors`)
  7. *Piutang Usaha / AR* (`/receivables`)
  8. *Utang Usaha / AP* (`/payables`)
  9. *Antrean Review* (`/review-queue`)
  10. *Akun Kas & Bank* (`/payment-accounts`)
  11. *Bagan Akun / COA* (`/chart-of-accounts`)
  12. *Pengaturan* (`/settings`)
- **Q4 (Dashboard Scope)**: Which exact metrics belong to Feature 003? → **A**: Operational summaries only: Total Kas & Bank, Total Piutang (AR), Total Utang (AP), Total Proyek Aktif, and Count of Transactions Requiring Review. Detailed multi-period P&L and Balance Sheet reports remain deferred to a future reporting feature.
- **Q5 (Transaction Creation UX)**: How should the transaction creation form behave? → **A**: Simple business terms (*Jenis Transaksi*, *Tanggal*, *Proyek*, *Customer/Vendor*, *Nominal*, *Kategori Biaya*, *Bayar Dari/Ke*, *Dokumen Bukti*, *Keterangan*). Zero Debit/Credit exposure. Default to single project. Multi-project split appears only when explicitly toggled ("Bagi Alokasi Proyek"), validating that $\sum \text{Allocations} == \text{Nominal}$.
- **Q6 (Review Queue Workflow)**: How does multi-flag review and escalation work? → **A**: Transactions in `REVIEW_REQUIRED` show individual flag badges (`AMOUNT_MISMATCH`, `DUPLICATE_SUSPECTED`, `PROJECT_UNKNOWN`, `MISSING_DOCUMENT`). Users resolve flags one by one by providing mandatory resolution notes. Transaction remains blocked until all flags are resolved. Sensitive transaction types require a Manager or Admin to approve and post.
- **Q7 (Posted Transaction Immutability)**: How are posted transactions displayed and corrected? → **A**: Posted transactions are strictly read-only (all form fields disabled, Delete button absent). Corrections use an auditable "Batalkan / Koreksi (Reversal)" action prompting for a mandatory reversal reason and executing the backend 3-step correction workflow.
- **Q8 (Document Evidence UX)**: What document capabilities are supported? → **A**: Drag-and-drop upload, thumbnail previews, embedded PDF/image viewer, and SHA-256 duplicate warning dialog linking to existing records. OCR and AI extraction are deferred.
- **Q9 (Customer & Vendor Terminology)**: How should counterparties be presented? → **A**: Use natural business terminology ("Pelanggan / Customer" and "Vendor & Subkon") with dedicated views, rather than generic technical terms like "Counterparty".
- **Q10 (AR & AP Management)**: How are receivables and payables displayed? → **A**: List views with status badges (`NOT_DUE`, `DUE`, `OVERDUE`, `PAID`, `PARTIALLY_PAID`). Users allocate payments against invoices/bills. Outstanding balances are dynamically derived from backend records and are strictly non-editable.
- **Q11 (Error Handling & User Feedback)**: How are errors communicated? → **A**: Non-technical, actionable inline banners and modal notifications for form validation errors, duplicate warnings (409), permission barriers (403), review queue alerts, and network disconnection banners.
- **Q12 (Language & Terminology)**: What is the application language? → **A**: Bahasa Indonesia as primary UI language with standard contractor terminology (*Uang Muka*, *Termin*, *Kasbon*, *SPK*, *Prive*, *Biaya Material/Upah*).
- **Q13 (Responsive Design)**: What devices are supported? → **A**: Desktop-first (optimized for 1280px+), with full tablet and mobile responsiveness via collapsible sidebar and horizontally scrollable / stacked data tables.
- **Q14 (Unsaved Form Protection)**: How are unsaved changes handled? → **A**: Browser confirmation prompt / custom modal warning when navigating away from a dirty form.
- **Q15 (Pagination, Search & Filtering)**: How are large datasets handled? → **A**: Server-side and client-side pagination (default 25 items/page), debounced real-time search, and multi-criteria filters (Status, Date Range, Project, Counterparty).
- **Q16 (Empty & Loading States)**: How are loading and empty states handled? → **A**: Skeleton loader animations during API fetches; descriptive empty state illustrations with quick-action buttons (e.g., "Belum ada transaksi — Catat Transaksi Pertama").
- **Q17 (Accessibility)**: What accessibility standards are met for MVP? → **A**: High contrast color palette, full keyboard tab navigation, visible focus indicators, semantic HTML, and descriptive ARIA labels on all interactive controls.
- **Q18 (Frontend Authority & Strict Backend Delegation)**: Where does accounting computation happen? → **A**: Frontend NEVER computes or invents accounting journals, balance sheet equations, or ledger entries. The backend REST APIs remain the sole authoritative system of record.

---

## 1. Scope & Core Principles

This specification defines the user experience, screens, interaction workflows, and business rules for the **Web SaaS Operational User Interface**.

### Core UX Principle: "Simple for User, Structured Underneath"
1. **No Debit/Credit Selection**: Normal operational users and managers NEVER select debit or credit accounts. They interact exclusively in natural business terms (*Jenis Transaksi*, *Tanggal*, *Proyek*, *Vendor/Customer*, *Nominal*, *Kategori Biaya*, *Akun Kas/Bank*, *Keterangan*, *Bukti Dokumen*).
2. **Authoritative Backend**: The UI never replicates accounting rules, balance equations, or financial computations. All journal creation, AR/AP derivation, project costing, approval checks, duplicate detection, and immutability guards remain authoritative in the backend.
3. **Single Input Interaction**: A business event is recorded once in the UI. The UI automatically displays the derived downstream effects (AR, AP, Project Cost, Ledger) without requiring secondary manual entries.
4. **Primary Language**: Bahasa Indonesia with standard Indonesian contractor financial terminology.

---

## 2. Actors & Roles

| Role | Primary Responsibilities & UI Permissions |
|---|---|
| **Operator** | Records daily transactions, uploads documents, creates projects, issues invoices/bills, registers payments, and resolves operational review flags (e.g. `PROJECT_UNKNOWN`, `MISSING_DOCUMENT`). May approve routine operational transactions. |
| **Manager** | Views operational dashboards, project profitabilities, cash positions, budget variances, and approves sensitive transactions (`OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`, related-party). Can initiate transaction reversals. |
| **Admin** | Manages organization master data, users, roles, payment accounts, and master COA references. |
| **Viewer** | Read-only access to dashboards, project summaries, and transaction records. Cannot create, edit, or approve. |

---

## 3. User Scenarios & Testing *(mandatory)*

### User Story 1 — Intuitive Transaction Intake (Priority: P1)

An Operator records an operational transaction (e.g., direct project purchase, vendor bill, customer payment) using a streamlined form with natural business terms. By default, the form targets a single project, with an optional toggle to split allocations across multiple projects if needed. When submitted, the UI sends the transaction to the backend, receives the generated code (`TRX-YYYY-######`), and indicates whether it is staged or routed to review.

**Why this priority**: Transaction intake is the single point of entry for all financial facts. A clean, non-accountant-friendly UI prevents input errors and maintains operational speed.

**Independent Test**: Complete a direct purchase form with document attachment, submit, verify successful capture message with `TRX` code, and view the recorded transaction in the list.

**Acceptance Scenarios**:
1. **Given** an Operator on the Transaction Entry screen, **When** they select "Pembelian Langsung", choose "Proyek Gedung A", enter Rp 15.000.000, select "Besi & Semen (MAT)", select "Bank Mandiri", attach a PDF receipt, and submit, **Then** the transaction is submitted via API and appears in the transaction list with status `STAGED`.
2. **Given** a purchase covering two projects, **When** the Operator enables "Bagi Alokasi Proyek", specifies Rp 10.000.000 for Proyek A and Rp 5.000.000 for Proyek B, **Then** the UI validates that the allocation sum equals the total nominal (Rp 15.000.000) before allowing submission.
3. **Given** a transaction submission where the receipt is duplicate or missing required data, **When** submitted, **Then** the UI displays an alert indicating the transaction has been sent to the `REVIEW_REQUIRED` queue with specific flag badges.

---

### User Story 2 — Operational Executive Dashboard (Priority: P1)

A Manager or Operator logs into the application and immediately sees real-time operational summary cards:
- **Kas dan Bank**: Total operational cash across all active payment accounts.
- **Piutang Usaha (AR)**: Total outstanding receivables from customers.
- **Utang Usaha (AP)**: Total outstanding payables to vendors.
- **Proyek Aktif**: Count of active contractor projects.
- **Antrean Review**: Count of transactions currently blocked in `REVIEW_REQUIRED`.

**Why this priority**: Gives business owners and project managers instant visibility into the company's operational pulse and pending bottlenecks without opening complex accounting ledgers.

**Independent Test**: Load the dashboard screen, verify all 5 metric cards load from live backend endpoints, and verify clicking the review queue card navigates directly to the review screen.

**Acceptance Scenarios**:
1. **Given** an authenticated user on the Dashboard, **When** the page loads, **Then** the UI displays the 5 key operational metric cards populated directly from backend summary APIs.
2. **Given** 3 transactions with review flags, **When** viewing the Dashboard, **Then** the "Antrean Review" badge displays `3` in warning color, and clicking it navigates to `/review-queue`.

---

### User Story 3 — Project Master & Financial Tracking (Priority: P1)

An Operator creates a new project with contract metadata (Customer, SPK/PO Number, Original Contract Value, Dates). As variations occur, the Manager records variation orders (`VO`), and the UI displays the revised contract value (`Original + VO`). The project detail view shows real-time derived billing status, collection status, actual project cost broken down by category (`MAT`, `SUB`, `LAB`, etc.), budget variance, and gross profit margin.

**Why this priority**: Project is the core organizing unit for construction contractors. Profitability must be visible per project in real-time.

**Independent Test**: Create a project, view the project detail tab, verify contract values, budget vs actual cards, and profitability percentages render without client-side manual calculations.

**Acceptance Scenarios**:
1. **Given** an active project with Original Contract Rp 1.000.000.000 and Variation Rp 100.000.000, **When** viewing the Project Detail, **Then** the UI displays Revised Contract Value Rp 1.100.000.000.
2. **Given** posted transactions with cost categories `MAT` (Rp 200M) and `SUB` (Rp 100M), **When** opening the "Biaya & Profitabilitas" tab, **Then** the UI shows Total Biaya Rp 300M, recognized revenue, and derived margin %.

---

### User Story 4 — Accounts Receivable (AR) & Invoicing Overview (Priority: P2)

An Operator issues a Customer Invoice against a project milestone. The AR management view displays all customer invoices with Customer, Invoice Code, Project, Due Date, Total Amount, Amount Paid, Remaining Outstanding, and Collection Status (`NOT_DUE`, `DUE`, `OVERDUE`). When a customer payment is allocated, the remaining balance decreases automatically.

**Why this priority**: Contractors need clear visibility on pending billings and cash collection timelines to maintain liquidity.

**Independent Test**: View the AR screen, search invoices by customer or project, verify paid vs outstanding columns reflect authoritative backend sub-ledger data.

**Acceptance Scenarios**:
1. **Given** a customer invoice of Rp 150.000.000 with Rp 50.000.000 paid, **When** viewing the AR list, **Then** the row shows Rp 50M Paid, Rp 100M Sisa Tagihan, and status `PARTIALLY_PAID`.
2. **Given** an invoice past its due date, **When** rendered in the list, **Then** the Collection Status badge displays `OVERDUE` in high-visibility styling.

---

### User Story 5 — Accounts Payable (AP) & Vendor Bill Overview (Priority: P2)

An Operator views all Vendor Bills across projects. The AP screen shows Vendor, Bill Code, Project, Bill Date, Due Date, Total Nominal, Paid Amount, and Remaining Outstanding. The UI allows allocating a payment transaction against one or multiple bills.

**Why this priority**: Ensures vendor obligations are paid on time without risking duplicate payment or lost bills.

**Independent Test**: Open the AP screen, verify all unpaid and partially paid bills are listed with correct derived balances, and trigger the payment allocation modal.

**Acceptance Scenarios**:
1. **Given** a Vendor Bill with outstanding Rp 30.000.000, **When** a payment of Rp 30.000.000 is allocated, **Then** the bill status updates to `PAID` and outstanding becomes Rp 0.00.

---

### User Story 6 — Review Queue & Ambiguity Resolution (Priority: P1)

An Operator or Manager opens the Review Queue to resolve flagged transactions. The UI displays the review reason badge (`AMOUNT_MISMATCH`, `DUPLICATE_SUSPECTED`, `PROJECT_UNKNOWN`, `MISSING_DOCUMENT`, etc.), allows previewing the attached evidentiary document, provides an input for resolution notes, and lets authorized users resolve flags and approve transactions.

**Why this priority**: Ambiguous transactions must be resolved systematically with human oversight before posting to the ledger.

**Independent Test**: Navigate to `/review-queue`, open a transaction with `PROJECT_UNKNOWN`, assign the missing project with resolution notes, submit resolution, and verify the transaction transitions to `STAGED`.

**Acceptance Scenarios**:
1. **Given** a transaction flagged with `PROJECT_UNKNOWN`, **When** the Operator selects the correct project and submits resolution notes, **Then** the flag is marked resolved in the UI and the transaction becomes eligible for approval.
2. **Given** a transaction with multiple flags, **When** one flag is resolved, **Then** the UI updates the flag status to resolved while keeping the transaction blocked until all flags are resolved.

---

### User Story 7 — Posted Record Immutability & Reversal Workflow (Priority: P1)

A Manager views a posted transaction. The UI renders the transaction details in **read-only mode** (no direct edit or delete buttons). To correct a mistake, the UI provides a prominent "Batalkan / Koreksi (Reversal)" action. The user enters a mandatory reversal reason, and the UI triggers the 3-step correction workflow via the backend.

**Why this priority**: Constitutional requirement. Prevents accidental destruction of accounting history and maintains a complete audit trail.

**Independent Test**: Open a posted transaction, verify edit/delete controls are disabled, click "Reversal", enter reason, confirm, and verify the reversal transaction (`TRX-YYYY-######`) is displayed with link to original.

**Acceptance Scenarios**:
1. **Given** a transaction in `POSTED` status, **When** viewed by any user, **Then** form fields are non-editable and the Delete button is absent.
2. **Given** a Manager clicking "Batalkan / Reversal", **When** they provide the reason "Salah nominal nota" and confirm, **Then** the UI executes the reversal API, updates the original status to `REVERSED`, and presents the new compensating reversal record.

---

### User Story 8 — Document Evidence & Cryptographic Deduplication (Priority: P2)

An Operator uploads receipts, SPK/contracts, invoices, or bank slips. The UI previews the document and displays metadata (`DOC-YYYY-######`, file hash, upload date). If the user attempts to upload a file with an identical SHA-256 hash, the UI displays a clear duplicate warning dialog and links to the existing document.

**Why this priority**: Prevents accidental double-claiming of expenses and keeps evidentiary records organized.

**Independent Test**: Upload a receipt PDF, upload the same file again, verify the UI displays a duplicate warning modal with link to the existing document.

**Acceptance Scenarios**:
1. **Given** an uploaded PDF document, **When** viewing the Document list, **Then** the UI displays document code, file name, thumbnail preview, and linked project/transaction.
2. **Given** a duplicate file upload attempt, **When** the backend returns 409 Conflict, **Then** the UI shows a friendly modal: "Dokumen ini sudah pernah diunggah sebelumnya" with a button to view the original.

---

## 4. Navigation & Screen Structure

The web application layout features a persistent responsive sidebar and top navigation bar:

```text
├── Dashboard (/dashboard)
├── Proyek (/projects)
├── Transaksi (/transactions)
├── Dokumen Bukti (/documents)
├── Pelanggan / Customer (/customers)
├── Vendor & Subkon (/vendors)
├── Piutang Usaha / AR (/receivables)
├── Utang Usaha / AP (/payables)
├── Antrean Review (/review-queue)
├── Akun Kas & Bank (/payment-accounts)
├── Bagan Akun / COA (/chart-of-accounts)
└── Pengaturan (/settings)
    ├── Profil & Organisasi (/settings/organization)
    ├── Pengguna & Hak Akses (/settings/users)
    └── Jejak Audit (/settings/audit-logs)
```

---

## 5. Functional Requirements

### Navigation & Layout
- **FR-UI-001**: System MUST provide a responsive dashboard layout with persistent sidebar navigation and mobile collapsible menu.
- **FR-UI-002**: UI MUST display the active Organization name and the authenticated User's name/role in the top navigation header.

### Transaction Management
- **FR-UI-003**: System MUST provide a simplified Transaction Entry form supporting all standard transaction types without exposing debit/credit selection.
- **FR-UI-004**: Form MUST default to single-project allocation and provide a toggle to add multiple project split lines.
- **FR-UI-005**: Form MUST enforce client-side validation that $\sum \text{Allocations} == \text{Total Nominal}$ before submission.
- **FR-UI-006**: Transaction list MUST provide filters by Status (`STAGED`, `REVIEW_REQUIRED`, `POSTED`, `REVERSED`), Date range, Project, and Transaction Type.
- **FR-UI-007**: Posted transactions MUST be rendered in strictly read-only mode with no destructive edit/delete options.
- **FR-UI-008**: UI MUST provide an auditable Reversal modal for posted transactions requiring mandatory explanation notes.

### Review Queue
- **FR-UI-009**: System MUST provide a dedicated Review Queue screen listing all transactions in `REVIEW_REQUIRED` status with distinct flag badges (`AMOUNT_MISMATCH`, `DUPLICATE_SUSPECTED`, `PROJECT_UNKNOWN`, etc.).
- **FR-UI-010**: Review screen MUST provide document split-view to inspect evidentiary files side-by-side with transaction details.
- **FR-UI-011**: UI MUST allow resolving individual flags with resolution notes and unblock the transaction when all flags are resolved.
- **FR-UI-012**: Approval button MUST enforce role authorization (Manager role required for sensitive transaction types).

### Projects & Costing
- **FR-UI-013**: Project list MUST display project code, name, customer, revised contract value, lifecycle status, derived billing status, and collection status.
- **FR-UI-014**: Project Detail view MUST display:
  - Contract summary (Original, Variation Orders, Revised Contract Value).
  - Real-time Cost Breakdown by category (`MAT`, `SUB`, `LAB`, etc.) and Budget vs Actual variance.
  - Project Profitability card (Recognized Revenue, Actual Cost, Gross Profit, Margin %).
  - Project Cash summary (Invoiced, Received, Outstanding AR, Net Cash surplus/deficit).

### Accounts Receivable (AR) & Accounts Payable (AP)
- **FR-UI-015**: AR screen MUST display all customer invoices with Customer, Project, Invoice Date, Due Date, Total Amount, Paid, Outstanding, and Collection Status badge.
- **FR-UI-016**: AP screen MUST display all vendor bills with Vendor, Project, Bill Date, Due Date, Total Amount, Paid, Outstanding, and Status.
- **FR-UI-017**: UI MUST provide payment allocation modals for both AR and AP allowing partial payment and multi-bill allocation.

### Document Management
- **FR-UI-018**: System MUST provide drag-and-drop document upload with file type validation (PDF, PNG, JPG).
- **FR-UI-019**: UI MUST display friendly duplicate warning modals when backend returns 409 Conflict (SHA-256 duplicate).
- **FR-UI-020**: Document viewer MUST allow previewing PDF and image documents within the browser.

### Master Data & Settings
- **FR-UI-021**: UI MUST provide management tables for Customers, Vendors, and Payment Accounts (Kas, Bank Mandiri, BCA, BRI).
- **FR-UI-022**: COA view MUST render the standard contractor chart of accounts in read-only tree format.
- **FR-UI-023**: System MUST provide an Audit Log viewer with filters by entity, action, and date range.

---

## 6. UX & Design Requirements

1. **Aesthetics**: Clean, modern, high-contrast dashboard with clear financial typography (tabular numbers for currency amounts).
2. **Currency Formatting**: Standard Indonesian Rupiah formatting throughout (`Rp 150.000.000,00`).
3. **Status Badging**:
   - `POSTED` / `PAID` / `ACTIVE` $\to$ Success (Green)
   - `STAGED` / `PARTIALLY_PAID` / `PLANNED` $\to$ Info (Blue)
   - `REVIEW_REQUIRED` / `OVERDUE` $\to$ Warning (Amber / Red)
   - `REVERSED` / `CLOSED` / `CANCELLED` $\to$ Neutral (Gray)
4. **Error Handling & State Feedback**:
   - Inline form field validation with instant helper messages.
   - Non-blocking toast notifications for successful actions.
   - Confirmation dialogs when navigating away from edited/dirty forms.
   - Full-page and card-level skeleton loaders during API fetch states.
   - Empty state cards with friendly illustrations and primary action triggers.

---

## 7. Security & Governance

- **Authentication**: JWT-based authentication with secure token storage.
- **Role Enforcement**: Client-side action hiding paired with backend 403 enforcement.
- **Multi-Tenant Isolation**: Active `organization_id` injected into all API request headers (`X-Organization-ID`).
- **No Committed Secrets**: Frontend builds must not contain hardcoded API keys or credentials.

---

## 8. Success Criteria *(measurable outcomes)*

- **SC-001**: Non-accountant operators can record a standard operational transaction with document attachment in under **60 seconds**.
- **SC-002**: 100% of transaction forms prevent debit/credit account exposure to normal users.
- **SC-003**: 100% of posted transactions are rendered strictly read-only with zero destructive edit/delete mechanisms.
- **SC-004**: Dashboard and Project Profitability cards load and render in under **1.5 seconds**.
- **SC-005**: All monetary amounts display exact currency precision without floating point rounding artifacts.

---

## 9. Assumptions

- The backend REST API implemented in `002-core-financial-domain-model` is running and accessible.
- Users access the application via modern web browsers (Chrome, Edge, Firefox, Safari).
- Initial user onboarding and organization creation will be managed by system administrators.

---

## 10. Explicit Out of Scope

- WhatsApp integration and Hermes automation agent.
- OCR and automated document AI extraction.
- Tax engine computation and automated e-Faktur generation.
- Full formal financial statement publishing (Neraca Standar SAK, Arus Kas Metode Tidak Langsung).
- Payroll and employee attendance management.
- Offline-first local database replication.
