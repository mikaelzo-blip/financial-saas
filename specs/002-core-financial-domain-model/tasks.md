# Implementation Tasks: Core Financial Domain & Architecture

**Feature**: `002-core-financial-domain-model`  
**Branch**: `002-core-financial-domain-model`  
**Spec**: [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)  
**Plan**: [specs/002-core-financial-domain-model/plan.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/plan.md)  
**Data Model**: [specs/002-core-financial-domain-model/data-model.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/data-model.md)  
**API Contract**: [specs/002-core-financial-domain-model/contracts/openapi.yaml](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/contracts/openapi.yaml)  
**Quickstart**: [specs/002-core-financial-domain-model/quickstart.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/quickstart.md)  

---

## Phase 1: Setup & Project Foundation

**Purpose**: Initialize backend modular monolith project structure, dependency management, database connection, and testing harness.

- [X] T001 Initialize Python project structure, dependencies (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `pytest`, `pytest-asyncio`, `httpx`) in `backend/pyproject.toml`
- [X] T002 Configure application settings and environment variables (Database URL, JWT secret, storage path) in `backend/src/core/config.py`
- [X] T003 [P] Configure asynchronous PostgreSQL database engine, session factory, and base model in `backend/src/core/database.py`
- [X] T004 [P] Initialize Alembic migration environment and async migration runner in `backend/alembic/env.py`
- [X] T005 [P] Setup global exception handling and API error response envelope in `backend/src/core/exceptions.py`
- [X] T006 [P] Setup Pytest fixtures, test database engine, and test client in `backend/tests/conftest.py`

**Checkpoint**: Foundation initialized. `pytest` executes successfully against a test PostgreSQL instance.

---

## Phase 2: Foundational Domain & Master Data (Blocking Prerequisites)

**Purpose**: Core entity models, enums, migrations, and shared master data required by all user stories.

- [X] T007 Define domain enums (`user_role`, `project_status`, `billing_status`, `collection_status`, `workflow_status`, `review_flag`, `transaction_type`, `cost_category`, `expense_category`, `account_type`, `normal_balance`, `document_type`) in `backend/src/models/enums.py`
- [X] T008 [P] Implement `Organization` and `User` models in `backend/src/models/organization.py` and `backend/src/models/user.py`
- [X] T009 [P] Implement `Counterparty` (Customer/Vendor) model in `backend/src/models/counterparty.py`
- [X] T010 [P] Implement `ChartOfAccount` and `PaymentAccount` models (without stored balances) in `backend/src/models/coa.py`
- [X] T011 [P] Implement `AuditLog` immutable change log model in `backend/src/models/audit.py`
- [X] T012 Create and apply initial Alembic migration for all master data tables, enums, and foreign keys in `backend/alembic/versions/001_initial_schema.py`
- [X] T013 Implement password hashing, JWT token generation, and user role validation in `backend/src/core/security.py`
- [X] T014 Implement COA standard seeder (accounts 1101 through 8101 per concept) in `backend/src/services/coa_seeder.py`

**Checkpoint**: Core database schema active, seed data populated, tenant boundary ready.

---

## Phase 3: User Story 1 - Project Master Data & Lifecycle Management (Priority: P1)

**Goal**: Define and manage contractor projects, contract values (original, variation, revised), customer relationships, and derived billing/collection statuses.

**Independent Test**: Create project with customer and contract value, transition status through PLANNED -> ACTIVE -> COMPLETED -> CLOSED, verify revised contract value auto-computes, and verify terminal state restrictions.

### Tests for User Story 1
- [X] T015 [P] [US1] Unit test for project lifecycle state transitions and terminal states in `backend/tests/unit/test_project_lifecycle.py`
- [X] T016 [P] [US1] Integration test for project creation and customer relationship in `backend/tests/integration/test_project_service.py`

### Implementation for User Story 1
- [X] T017 [P] [US1] Implement `Project` and `ProjectBudget` models with revised contract value check in `backend/src/models/project.py`
- [X] T018 [P] [US1] Implement Pydantic DTO schemas for project creation, update, and responses in `backend/src/schemas/project.py`
- [X] T019 [US1] Implement `ProjectService` for project creation, sequential code generation (`PRJ-YYYY-###`), status transitions, and derived status evaluation in `backend/src/services/project_service.py`
- [X] T020 [US1] Implement Project REST API endpoints (`GET /projects`, `POST /projects`, `GET /projects/{id}`) in `backend/src/api/v1/projects.py`

**Checkpoint**: Projects can be created, updated, and queried with enforced lifecycle state machines.

---

## Phase 4: User Story 8 - Chart of Accounts, Payment Accounts & Reference Data (Priority: P3)

**Goal**: Manage operational payment accounts (Bank Mandiri, BCA, BRI, Cash) mapped to parent COA 1101, cost categories, and expense categories.

**Independent Test**: Register payment accounts under parent COA 1101, query account directory, and verify no balances are stored in COA table.

### Tests for User Story 8
- [X] T021 [P] [US8] Unit test for COA normal balance rules and payment account mappings in `backend/tests/unit/test_coa_service.py`

### Implementation for User Story 8
- [X] T022 [P] [US8] Implement Pydantic DTO schemas for COA, payment accounts, and categories in `backend/src/schemas/coa.py`
- [X] T023 [US8] Implement `COAService` and `PaymentAccountService` in `backend/src/services/coa_service.py`
- [X] T024 [US8] Implement Reference Data REST API endpoints (`GET/POST /coa`, `GET/POST /payment-accounts`) in `backend/src/api/v1/reference_data.py`

**Checkpoint**: Chart of Accounts and Payment Accounts can be configured and referenced.

---

## Phase 5: User Story 4 - Document Management & File Duplicate Detection (Priority: P2)

**Goal**: Immutable storage of source evidence (PDF, image) with SHA-256 hashing, duplicate prevention, and N:M links to projects and transactions.

**Independent Test**: Upload an invoice PDF, verify `DOC-YYYY-######` generation and SHA-256 hash persistence. Upload the identical file again and verify `EXACT_DUPLICATE` rejection.

### Tests for User Story 4
- [X] T025 [P] [US4] Unit test for SHA-256 file hashing and duplicate detection in `backend/tests/unit/test_document_service.py`
- [X] T026 [P] [US4] Integration test for document upload and project linking in `backend/tests/integration/test_document_upload.py`

### Implementation for User Story 4
- [X] T027 [P] [US4] Implement `Document`, `ProjectDocumentLink`, and `TransactionDocumentLink` models in `backend/src/models/document.py`
- [X] T028 [P] [US4] Implement local filesystem / S3 storage abstraction in `backend/src/services/storage_service.py`
- [X] T029 [US4] Implement `DocumentService` for file ingest, SHA-256 hashing, duplicate checking, and code generation (`DOC-YYYY-######`) in `backend/src/services/document_service.py`
- [X] T030 [US4] Implement Document REST API endpoint (`POST /documents/upload`, `GET /documents/{id}`) in `backend/src/api/v1/documents.py`

**Checkpoint**: Documents are stored immutably with cryptographic duplicate detection.

---

## Phase 6: User Story 2 - Transaction Capture & Allocation Core (Priority: P1)

**Goal**: Single-input capture of financial business events with single-project default, optional multi-project split allocations, and initial validation.

**Independent Test**: Ingest a transaction with split allocations, verify `sum(allocations) == total_amount` validation, and verify initial status is `STAGED`.

### Tests for User Story 2
- [X] T031 [P] [US2] Unit test for transaction allocation sum validation and heuristic duplicate checking in `backend/tests/unit/test_transaction_validation.py`
- [X] T032 [P] [US2] Integration test for transaction capture and document linking in `backend/tests/integration/test_transaction_intake.py`

### Implementation for User Story 2
- [X] T033 [P] [US2] Implement `Transaction`, `TransactionAllocation`, and `TransactionReviewFlag` models in `backend/src/models/transaction.py`
- [X] T034 [P] [US2] Implement Pydantic DTO schemas for single and split transactions in `backend/src/schemas/transaction.py`
- [X] T035 [US2] Implement `DuplicateDetectionService` for heuristic transaction duplicate detection (date + amount + counterparty + account) in `backend/src/services/duplicate_service.py`
- [X] T036 [US2] Implement `TransactionService.create_transaction` with code generation (`TRX-YYYY-######`), allocation validation, and initial status assignment in `backend/src/services/transaction_service.py`
- [X] T037 [US2] Implement Transaction capture REST API endpoints (`GET /transactions`, `POST /transactions`) in `backend/src/api/v1/transactions.py`

**Checkpoint**: Transactions can be captured in single or multi-project split mode without debit/credit input.

---

## Phase 7: User Story 3 - Deterministic Accounting Rule Engine & Atomic Posting (Priority: P1)

**Goal**: Deterministically generate balanced double-entry journal entries from transaction types and allocations upon approval; enforce atomic posting and `Total Debit == Total Credit`.

**Independent Test**: Approve a `VENDOR_BILL` transaction, verify generated journal lines (`Dr 5101 / Cr 2101`), verify `total_debit == total_credit`, and verify transaction becomes `POSTED`. Attempt posting an unbalanced journal and verify it is blocked.

### Tests for User Story 3
- [X] T038 [P] [US3] Unit test for all 35 `TransactionType` deterministic accounting rules and balance invariants in `backend/tests/unit/test_accounting_rules.py`
- [X] T039 [P] [US3] Integration test for atomic approval, journal generation, and posting blocking on imbalance in `backend/tests/integration/test_posting_engine.py`

### Implementation for User Story 3
- [X] T040 [P] [US3] Implement `JournalEntry` and `JournalLine` models with debit/credit CHECK constraints in `backend/src/models/journal.py`
- [X] T041 [P] [US3] Implement `AccountingRuleRegistry` mapping each of the 35 transaction types to debit/credit derivation templates in `backend/src/services/accounting_rules.py`
- [X] T042 [P] [US3] Implement `AccountingEngine.post_transaction` executing rule lookup, line generation, balance check, journal creation, and status transition in `backend/src/services/accounting_engine.py`
- [X] T043 [P] [US3] Implement Transaction approval REST API endpoint (`POST /transactions/{id}/approve`) in `backend/src/api/v1/transactions.py`

**Checkpoint**: Transactions can be posted with deterministic double-entry journals. Unbalanced entries are strictly blocked.

---

## Phase 8: User Story 6 - Vendor AP, Bills, Payments & Advance Management (Priority: P2)

**Goal**: Track vendor bills, payments, AP balance derivation, vendor advances, and review queue routing on settlement excess.

**Independent Test**: Post vendor bill -> AP increases. Post partial payment -> AP decreases, cash decreases, project cost is not duplicated. Settle advance with excess -> excess routes to review with `AMOUNT_MISMATCH`.

### Tests for User Story 6
- [X] T044 [P] [US6] Unit test for AP balance derivation and partial payment allocations in `backend/tests/unit/test_ap_service.py`
- [X] T045 [P] [US6] Integration test for vendor advance creation, settlement, and excess review routing in `backend/tests/integration/test_vendor_advances.py`

### Implementation for User Story 6
- [X] T046 [P] [US6] Implement `VendorBill`, `PaymentAllocation`, `Advance`, and `AdvanceSettlementAllocation` models in `backend/src/models/subledger.py`
- [X] T047 [US6] Implement `APService` for bill registration, payment allocation, outstanding calculation, and advance settlement in `backend/src/services/ap_service.py`
- [X] T048 [US6] Integrate `APService` handlers into `AccountingEngine` for `VENDOR_BILL`, `PAY_VENDOR_BILL`, `VENDOR_ADVANCE`, and `SETTLE_VENDOR_ADVANCE` in `backend/src/services/accounting_engine.py`

**Checkpoint**: Vendor payables and advances are fully automated from transaction postings without duplicate manual tracking.

---

## Phase 9: User Story 5 - Customer AR, Invoicing, Payments & Overpayment Handling (Priority: P2)

**Goal**: Track customer invoices, due dates (with configurable payment terms), payment matching, AR derivation, and review queue routing on overpayment.

**Independent Test**: Post customer invoice -> AR increases and project billing status updates. Post matching payment -> AR decreases. Post overpayment -> routes to review with `AMOUNT_MISMATCH` without auto-advance allocation.

### Tests for User Story 5
- [X] T049 [P] [US5] Unit test for AR invoice due date calculation and overpayment review routing in `backend/tests/unit/test_ar_service.py`
- [X] T050 [P] [US5] Integration test for customer invoice posting, partial payment allocation, and derived collection status in `backend/tests/integration/test_customer_invoicing.py`

### Implementation for User Story 5
- [X] T051 [P] [US5] Implement `CustomerInvoice` model with due date and cancellation flag in `backend/src/models/subledger.py`
- [X] T052 [US5] Implement `ARService` for customer invoice creation, due date resolution (`invoice_date + payment_term_days`), payment allocation, and overpayment excess detection in `backend/src/services/ar_service.py`
- [X] T053 [US5] Integrate `ARService` handlers into `AccountingEngine` for `CUSTOMER_INVOICE` and `CUSTOMER_PAYMENT` in `backend/src/services/accounting_engine.py`

**Checkpoint**: Customer receivables and payments are fully tracked and linked with overpayment safeguards.

---

## Phase 10: User Story 7 - Reversal Workflow, Immutability & Audit Trail (Priority: P2)

**Goal**: Enforce immutability of posted records, provide reversal transaction creation with offsetting journals, and log all critical state changes in append-only audit log.

**Independent Test**: Attempt modifying a posted transaction -> rejected. Call reversal endpoint -> original marked `REVERSED`, new `REVERSAL` transaction created in `POSTED` status, offsetting journal posted, audit entry created.

### Tests for User Story 7
- [X] T054 [P] [US7] Unit test for immutability enforcement on posted transactions in `backend/tests/unit/test_immutability.py`
- [X] T055 [P] [US7] Integration test for transaction reversal lifecycle and audit log recording in `backend/tests/integration/test_reversal_service.py`

### Implementation for User Story 7
- [X] T056 [P] [US7] Implement `AuditService` for append-only change recording (`actor`, `timestamp`, `action`, `entity`, `old_values`, `new_values`, `reason`) in `backend/src/services/audit_service.py`
- [X] T057 [US7] Implement `ReversalService` creating compensating transactions and offsetting journals in `backend/src/services/reversal_service.py`
- [X] T058 [US7] Add pre-update immutability guards in `TransactionService` and database triggers in `backend/src/services/transaction_service.py`
- [X] T059 [US7] Implement Reversal REST API endpoint (`POST /transactions/{id}/reverse`) in `backend/src/api/v1/transactions.py`

**Checkpoint**: Audit trail is active; posted financial data cannot be modified destructively.

---

## Phase 11: Review Queue & Discrepancy Resolution (Cross-Cutting)

**Goal**: Centralized Review Queue for transactions flagged with `AMOUNT_MISMATCH`, `DUPLICATE_SUSPECTED`, `PROJECT_UNKNOWN`, sensitive types, or low confidence; provide resolution workflows.

**Independent Test**: Create transaction with `PROJECT_UNKNOWN` flag -> appears in review queue. Resolve flag with resolution notes -> transaction transitions to `STAGED` / `APPROVED`.

- [X] T060 [P] Integration test for review queue querying and flag resolution lifecycle in `backend/tests/integration/test_review_queue.py`
- [X] T061 Implement `ReviewQueueService` for fetching flagged transactions, adding flags, and recording flag resolutions in `backend/src/services/review_service.py`
- [X] T062 Implement Review Queue REST API endpoints (`GET /review-queue`, `POST /review-queue/{flagId}/resolve`) in `backend/src/api/v1/review_queue.py`

**Checkpoint**: Ambiguous or flagged financial events are systematically managed through the review queue.

---

## Phase 12: Project Costing & Financial Rollups (Cross-Cutting)

**Goal**: Derive project costs by `cost_category` (MAT, SUB, LAB, TRN, TRV, LOG, EQP, SIT, OTH) directly from journal lines and compute project profitability and cash position.

**Independent Test**: Post multiple direct purchases and bills against project -> verify Project Cost Summary reflects sum of debit 5101 lines grouped by category, with zero manual cost entry.

- [X] T063 [P] Unit test for project cost aggregation and margin calculations in `backend/tests/unit/test_project_costing.py`
- [X] T064 Implement `ProjectCostingService` aggregating journal lines by project and cost category in `backend/src/services/project_costing.py`
- [X] T065 Implement Project Financial Summary REST API endpoint (`GET /projects/{id}/summary`) in `backend/src/api/v1/projects.py`

**Checkpoint**: Project costing, margins, and cash positions are derived in real-time from authoritative ledger data.

---

## Phase 13: Financial Integrity & Verification Suite

**Goal**: End-to-end automated verification of all 15 financial invariants, balancing rules, and integration scenarios defined in `quickstart.md`.

- [X] T066 [P] Integration test for full financial cycle (Project -> Bill -> Payment -> Invoice -> Payment -> Reversal) in `backend/tests/integration/test_full_financial_cycle.py`
- [X] T067 [P] Integrity test verifying Balance Sheet Equation `Assets == Liabilities + Equity` holds across all 35 transaction types in `backend/tests/integration/test_balance_sheet_integrity.py`
- [X] T068 Execute quickstart verification scenarios A through E per `quickstart.md` in `backend/tests/integration/test_quickstart_scenarios.py`

---

## Dependencies & Execution Order

```text
Phase 1: Setup (T001-T006)
   │
   ▼
Phase 2: Foundational Master Data & Migrations (T007-T014)
   │
   ├───────────────────────┬───────────────────────┐
   ▼                       ▼                       ▼
Phase 3: US1 Projects   Phase 4: US8 COA        Phase 5: US4 Documents
(T015-T020)             (T021-T024)             (T025-T030)
   │                       │                       │
   └───────────────────────┼───────────────────────┘
                           ▼
                 Phase 6: US2 Transaction Core
                 (T031-T037)
                           │
                           ▼
                 Phase 7: US3 Accounting Engine & Posting
                 (T038-T043)
                           │
   ┌───────────────────────┴───────────────────────┐
   ▼                                               ▼
Phase 8: US6 AP & Advances              Phase 9: US5 AR & Invoicing
(T044-T048)                             (T049-T053)
   │                                               │
   └───────────────────────┬───────────────────────┘
                           ▼
                 Phase 10: US7 Reversal & Audit Trail
                 (T054-T059)
                           │
   ┌───────────────────────┴───────────────────────┐
   ▼                                               ▼
Phase 11: Review Queue                  Phase 12: Project Costing
(T060-T062)                             (T063-T065)
   │                                               │
   └───────────────────────┬───────────────────────┘
                           ▼
                 Phase 13: Invariant & Integrity Suite
                 (T066-T068)
```

---

## Parallel Opportunities

1. **Setup Phase**: T003, T004, T005, T006 can run in parallel once T001/T002 are ready.
2. **Master Data Phase**: T008, T009, T010, T011 can be implemented in parallel before migration T012.
3. **Domain Models (Phases 3, 4, 5)**: Project management (US1), COA/Payment accounts (US8), and Document storage (US4) can proceed in parallel once Phase 2 is complete.
4. **Subledgers (Phases 8, 9)**: AP/Advances (US6) and AR/Invoicing (US5) can be implemented in parallel once Phase 7 (Accounting Engine) is posted.
5. **Cross-Cutting (Phases 11, 12)**: Review Queue and Project Costing rollups can run in parallel.

---

## Implementation Strategy

1. **MVP Increment 1**: Phase 1 (Setup) + Phase 2 (Foundational) + Phase 3 (Projects) + Phase 4 (COA) + Phase 6 (Transactions) + Phase 7 (Accounting Engine). This delivers the core Single-Input Double-Entry posting engine.
2. **MVP Increment 2**: Phase 5 (Documents) + Phase 8 (Vendor AP) + Phase 9 (Customer AR) + Phase 10 (Reversals & Audit). Adds full sub-ledger tracking and auditability.
3. **MVP Increment 3**: Phase 11 (Review Queue) + Phase 12 (Project Costing) + Phase 13 (Full Invariant Suite). Completes all Phase 2 domain model objectives.
