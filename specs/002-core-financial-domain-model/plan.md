# Implementation Plan: Core Financial Domain & Architecture

**Branch**: `002-core-financial-domain-model` | **Date**: 2026-08-29 | **Spec**: [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)

---

## 1. Technical Context

- **Backend Runtime**: Python 3.12+ with FastAPI, Pydantic v2, and SQLAlchemy 2.0 (asyncpg).
- **Database Engine**: PostgreSQL 16+ (System of record, ACID transactions, exact NUMERIC math, foreign keys, CHECK constraints).
- **Storage Layer**: Local filesystem / S3-compatible object storage for immutable raw documents with SHA-256 integrity verification.
- **Frontend Architecture (Future Phase)**: Modern web frontend (Vite/React/TypeScript) consuming the backend REST API.
- **Testing Framework**: Pytest with automated domain invariant suites (`test_accounting_engine.py`, `test_allocations.py`, `test_integrity.py`).
- **Target Platform**: Containerized Linux (Docker) / Cloud VM with PostgreSQL 16.
- **Architecture Pattern**: Modular Monolith organized by domain boundaries (Accounting, Projects, Documents, Subledgers, Review, Audit).
- **External Integration Pattern**: Authenticated REST API with JWT / API key boundaries; Hermes and WhatsApp integrate through external API endpoints without direct DB access.

---

## 2. Constitution Compliance Check

| Constitution Principle | Implementation Mechanism | Status |
|---|---|---|
| **I. Single Input** | Single `transactions` capture; all journals, AR/AP, project costs, and report balances derived automatically. | PASS |
| **II. Project-Based Accounting** | `Project_ID` dimension attached to transactions, allocations, and journal lines. COA remains concise. | PASS |
| **III. Simple User Experience** | Normal transaction input captures business event only. Users never manually select debit/credit accounts. | PASS |
| **IV. Double-Entry Invariant** | `journal_entries` enforces `CHECK (total_debit = total_credit)` and pre-posting validation in Python `Decimal`. | PASS |
| **V. Deterministic Engine** | `Transaction_Type` + Allocations maps deterministically to `Accounting_Rule` templates. Zero ad-hoc guessing. | PASS |
| **VI. Cash Movement != Expense** | `INTERBANK_TRANSFER` and liability settlements affect balance sheet only. Economic substance rules enforced. | PASS |
| **VII. Document Traceability** | Raw files stored immutably with SHA-256 hash in `documents` and linked via `transaction_document_links`. | PASS |
| **VIII. Duplicate Prevention** | SHA-256 unique index prevents file duplicates; multi-field heuristic flags `DUPLICATE_SUSPECTED`. | PASS |
| **IX. Human Review for Ambiguity** | Ambiguous/flagged transactions routed to `REVIEW_REQUIRED` and `transaction_review_flags`. Never silently posted. | PASS |
| **X. Immutable Posted Records** | Posted rows locked against update/delete. Corrections enforce `Original -> Reversal -> Correcting TRX`. | PASS |
| **XI. Audit Trail** | Append-only `audit_logs` table records who, when, what (old/new JSON), and why. | PASS |
| **XII. Derived Balances** | AR, AP, project costs, and account balances computed dynamically from journals and allocations. | PASS |
| **XIII. Report Integrity** | Reports generated from posted journals; balance sheet enforces `Assets == Liabilities + Equity`. | PASS |
| **XIV. Concept Separation** | Distinct fields for Contract Value, Revenue Recognized, Invoiced, and Cash Received. | PASS |
| **XV. Tax Separation** | Informational tax fields (`tax_base`, `tax_amount`) decoupled from core accounting ledger rules. | PASS |
| **XVI. Open Policy Protection** | Unresolved policies (e.g. depreciation, formal revenue recognition timing) kept configurable without hardcoded assumptions. | PASS |
| **XVII. Review Before Automation** | External agents cannot auto-post sensitive or review-flagged transactions. | PASS |
| **XVIII. API Boundary** | All external traffic passes through authenticated FastAPI endpoints. Direct database access blocked. | PASS |
| **XIX. Hermes Role** | Hermes acts as orchestration client calling the REST API; does not own the ledger. | PASS |
| **XX. Development Responsibility** | Implementation strictly guided by AGY via Spec Kit specifications and tasks. | PASS |
| **XXI. Transactional Database** | PostgreSQL 16 is authoritative system of record; Excel reserved for import/export/reporting. | PASS |
| **XXII. Modular Architecture** | Clean domain layer separation across accounting, projects, subledgers, documents, and auth. | PASS |
| **XXIII. Security & Tenant Boundary** | `organization_id` on all tables, role-based authorization (ADMIN, MANAGER, OPERATOR), least privilege. | PASS |
| **XXIV. Testability** | Comprehensive Pytest suites for balancing, rule determinism, duplicate detection, and sub-ledger math. | PASS |
| **XXV. Incremental Implementation** | Staged delivery following Spec Kit workflows without monolithic code jumps. | PASS |

---

## 3. Architecture: Modular Monolith

```text
                                  +-----------------------+
                                  |    Web Client / UI    |
                                  | (Future Frontend App) |
                                  +-----------+-----------+
                                              |
                                              | HTTPS / JWT
                                              v
+-----------------------+         +-----------+-----------+
|     Hermes Agent      |         |  FastAPI Backend API  |
| (WhatsApp / Ingest)   +-------->+  (Auth, Scopes, JSON) |
+-----------------------+  API Key+-----------+-----------+
                                              |
      +---------------------------------------+---------------------------------------+
      |                       |                       |                       |       |
      v                       v                       v                       v       v
+------------+         +------------+         +---------------+         +---------+ +---------+
|  Projects  |         | Documents  |         |  Transactions |         | Subledg | | Audit & |
|   Module   |         |   Module   |         |   & Review    |         | (AR/AP) | | Review  |
+------------+         +------------+         +-------+-------+         +---------+ +---------+
                                                      |
                                                      v
                                            +-------------------+
                                            | Accounting Engine |
                                            | (Rules, Journals) |
                                            +---------+---------+
                                                      |
                                                      v
                                            +-------------------+
                                            | PostgreSQL 16 DB  |
                                            | (System of Record)|
                                            +-------------------+
```

---

## 4. Domain-to-Database Mapping & Schemas

The full table definitions, column types, constraints, and relationships are documented in detail in [specs/002-core-financial-domain-model/data-model.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/data-model.md).

Key relational mappings:
1. **Tenancy**: `organizations` owns `users`, `counterparties`, `chart_of_accounts`, `payment_accounts`, `projects`, `documents`, and `transactions`.
2. **Projects**: `projects` links to `counterparties` (as customer), child `project_budgets`, and N:M `project_document_links`.
3. **Transactions**: `transactions` holds the single business event, linking to `counterparties`, `payment_accounts`, optional `projects`, and child `transaction_allocations` (for multi-project split mode).
4. **Journals**: `journal_entries` (1:1 with posted `transactions`) contains child `journal_lines` linking to `chart_of_accounts` and `projects`.
5. **Sub-ledgers**: `customer_invoices` (AR) and `vendor_bills` (AP) settled via `payment_allocations`. Prepayments tracked in `advances` and settled via `advance_settlement_allocations`.
6. **Traceability**: `documents` holds SHA-256 file hashes and storage references, linked to transactions via `transaction_document_links`.
7. **Audit & Governance**: `audit_logs` (immutable change events) and `transaction_review_flags` (stateful review items).

---

## 5. Transaction, Allocation & Accounting Engine Workflow

```text
[ Incoming Business Event / Document ]
                  │
                  ▼
       [ Create Transaction ]
                  │
     ┌────────────┴────────────┐
     ▼                         ▼
Single-Project Mode      Split Allocation Mode
 (1 Project + CostCat)    (N Project Allocations)
     │                         │
     └────────────┬────────────┘
                  ▼
    [ Run Validation & Duplicate Checks ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
    Flags Raised?       No Flags
        │                   │
        ▼                   ▼
  REVIEW_REQUIRED         STAGED
        │                   │
  (Human Resolves)          │
        │                   │
        └─────────┬─────────┘
                  ▼
           [ User Approves ]
                  │
                  ▼
     [ Accounting Engine Execution ]
     1. Lookup deterministic rule for Transaction_Type
     2. Generate Journal Entry & Lines (Dr / Cr)
     3. Check Invariant: Sum(Debit) == Sum(Credit)
     4. Update AR / AP / Advances sub-ledgers
     5. Update Project Cost allocations
     6. Lock Transaction as POSTED
                  │
                  ▼
          [ Commit to DB ]
```

---

## 6. AR / AP Sub-Ledger Allocation Model

- **Accounts Receivable (AR)**:
  - Created upon posting `CUSTOMER_INVOICE`.
  - Due date computed from `invoice_date + organization.default_payment_term_days` (overridable per invoice).
  - Outstanding balance = `amount - SUM(allocated_payments)`.
  - If a payment exceeds outstanding balance: routes to Review Queue with `AMOUNT_MISMATCH`. After review, user classifies the excess (Advance, other invoice, unapplied, or refund).
- **Accounts Payable (AP)**:
  - Created upon posting `VENDOR_BILL` or `SUBCONTRACTOR_BILL`.
  - Outstanding balance = `amount - SUM(allocated_payments)`.
  - Payment settles liability (`Dr 2101 / Cr 1101`), preventing double-counted project expense.
- **Advances**:
  - `VENDOR_ADVANCE` / `EMPLOYEE_ADVANCE` / `CUSTOMER_ADVANCE` creates prepayment balance.
  - Settlement exceeds balance: routes to Review Queue with `AMOUNT_MISMATCH`.

---

## 7. Audit & Immutability Strategy

- **Immutability of Posted Rows**:
  - A database trigger / application rule prevents direct `UPDATE` or `DELETE` on financial attributes of transactions in `POSTED`, `RECONCILED`, or `REVERSED` status.
- **Reversals**:
  - Calling `/transactions/{id}/reverse` creates a new transaction (`transaction_type = 'REVERSAL'`) with equal-and-opposite journal lines.
  - The original transaction's status transitions to `REVERSED`.
- **Append-Only Audit Log**:
  - The `audit_logs` table records every state transition, entity creation, modification, and reversal with previous and current JSON snapshots.

---

## 8. Authentication, Authorization & API Boundary

- **Authentication**: JWT Bearer tokens for interactive users; API Key authentication for backend automated services (e.g. Hermes).
- **Role-Based Access Control (RBAC)**:
  - `ADMIN`: COA management, payment accounts, organization settings, user management.
  - `MANAGER`: All Operator actions + required approver for sensitive transaction types (`OWNER_WITHDRAWAL`, `REVERSAL`, `JOURNAL_ADJUSTMENT`, related-party, tax adjustments).
  - `OPERATOR`: Document intake, staging transactions, approving routine operational transactions.
  - `VIEWER`: Read-only reporting access.
- **API Boundary Protection**:
  - Hermes and WhatsApp bridges submit payloads via `/api/v1/documents/upload` and `/api/v1/transactions`. They do not possess database credentials.

---

## 9. Error Handling & Invariant Enforcement

1. **Unbalanced Journal Guard**: If any rule or manual adjustment produces a journal where `total_debit != total_credit`, posting aborts with HTTP `422 Unprocessable Entity` and the database transaction rolls back.
2. **Duplicate File Guard**: Uploading a file matching an existing SHA-256 hash returns HTTP `409 Conflict` referencing the existing `DOC-ID`.
3. **Invalid Transition Guard**: Status state machines strictly enforce allowed transitions. Attempting an invalid jump (e.g., `CAPTURED -> POSTED`) raises a validation exception.
4. **Tenant Isolation Guard**: All ORM repository queries automatically append `WHERE organization_id = current_org_id`.

---

## 10. Project Structure & Code Layout

```text
financial-saas/
├── backend/
│   ├── alembic/                      # Database migrations
│   ├── src/
│   │   ├── core/                     # Config, database session, security, exceptions
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/                   # SQLAlchemy ORM entity models
│   │   │   ├── organization.py
│   │   │   ├── user.py
│   │   │   ├── counterparty.py
│   │   │   ├── coa.py
│   │   │   ├── project.py
│   │   │   ├── document.py
│   │   │   ├── transaction.py
│   │   │   ├── journal.py
│   │   │   ├── subledger.py
│   │   │   └── audit.py
│   │   ├── schemas/                  # Pydantic v2 DTO schemas
│   │   │   ├── project.py
│   │   │   ├── transaction.py
│   │   │   ├── document.py
│   │   │   ├── journal.py
│   │   │   └── review.py
│   │   ├── services/                 # Domain logic & engines
│   │   │   ├── accounting_engine.py  # Deterministic rule engine & posting
│   │   │   ├── duplicate_service.py  # Hash & heuristic duplicate detection
│   │   │   ├── subledger_service.py  # AR/AP & advance settlement logic
│   │   │   ├── project_service.py    # Project cost & profitability rollup
│   │   │   └── audit_service.py      # Append-only audit logger
│   │   ├── api/                      # FastAPI routers
│   │   │   ├── v1/
│   │   │   │   ├── auth.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── transactions.py
│   │   │   │   ├── journals.py
│   │   │   │   └── review_queue.py
│   │   └── main.py                   # FastAPI application entrypoint
│   ├── tests/
│   │   ├── unit/                     # Accounting engine, duplicate logic tests
│   │   ├── integration/              # Database transactions, posting flows
│   │   └── conftest.py               # Pytest fixtures & test DB
│   ├── pyproject.toml                # Dependencies & tool configs
│   └── Dockerfile                    # Container definition
├── specs/                            # Spec Kit artifacts
└── docs/                             # Business & domain concepts
```

---

## 11. Implementation Phases

- **Phase 1: Foundation & Migrations**
  - Setup Python environment, SQLAlchemy 2.0 async engine, and Alembic.
  - Create all tables, enums, indexes, and constraints in PostgreSQL.
- **Phase 2: Core Domain Services**
  - Implement master data services (Organizations, Users, COA, Payment Accounts, Counterparties).
  - Implement Document storage service with SHA-256 duplicate hashing.
- **Phase 3: Transaction & Accounting Engine**
  - Implement single-input transaction capture and staging.
  - Implement deterministic `Accounting_Engine` mapping all 35 `Transaction_Type` items to balanced double-entry journals.
  - Enforce `Total Debit == Total Credit` guard.
- **Phase 4: Sub-Ledgers & Allocations**
  - Implement AR (`customer_invoices`), AP (`vendor_bills`), and `payment_allocations`.
  - Implement Multi-Project Split Allocations (`transaction_allocations`).
  - Implement Advance tracking and settlement.
- **Phase 5: Review Queue & Reversals**
  - Implement heuristic transaction duplicate detection and review flag engine.
  - Implement audit-compliant reversal service.
- **Phase 6: Project Cost & Reporting Rollups**
  - Implement dynamic project cost aggregation (by `cost_category`), margin %, and cash surplus/deficit calculations.
  - Implement financial statement queries (Trial Balance, P&L, Balance Sheet).

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Floating point arithmetic inaccuracies | High | Enforce `decimal.Decimal` in Python and `NUMERIC(18,2)` in PostgreSQL across all monetary operations. |
| Accidental double-posting of payments | High | Idempotency keys on API endpoints and atomic DB transactions for payment allocations. |
| Incomplete review resolution | Medium | Database and service layer block `APPROVED` / `POSTED` transition while unresolved review flags exist. |
| Performance degradation on dynamic ledger queries | Medium | Composite indexes on `journal_lines(account_id, project_id)` and `transactions(workflow_status, date)`. |

---

## 13. Explicit Deferred Items

1. **Frontend UI Implementation**: Web user interface is deferred to a subsequent frontend phase.
2. **WhatsApp / OCR Ingestion Pipeline**: Direct WhatsApp webhook and AI OCR processing are deferred to Phase 7/8.
3. **Formal Tax Filing Automation**: Detailed tax rates and electronic tax reporting are deferred as OPEN POLICY items.
4. **Periodic Depreciation Scheduler**: Asset capitalization and depreciation batch jobs deferred to future asset management phase.
