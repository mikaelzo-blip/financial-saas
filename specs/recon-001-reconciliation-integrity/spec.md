# Feature Specification: Bank Reconciliation Integrity (RECON-001)

**Feature**: RECON-001 — Enforce Reconciliation Cardinality, Amount Integrity, and Dashboard Correctness  
**Feature Branch**: `hermes/recon-001-reconciliation-integrity`  
**Status**: SPECIFICATION & ARCHITECTURAL PLANNING  
**Priority**: P1 (Financial Control & Data Integrity)  
**Confidence**: HIGH (Root causes verified by source code and executable probes)  
**Authority**: `.specify/memory/constitution.md`, `docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md`, `AGENTS.md`  
**Baseline Commit**: `e3c33ec3432ecff81c64be02012eaf51b55c5269` (`origin/main`)  

---

## 1. Executive Summary & Problem Statement

Bank reconciliation is a fundamental financial control that proves the completeness and accuracy of cash recorded in company books against external banking records. In `financial-saas`, bank statement lines are imported and reconciled against internal financial records (`JournalLine`, `MoneyMovement`, or `Transaction`) either via manual matching (`POST /api/v1/bank-reconciliation/reconcile`) or the auto-matching engine (`POST /api/v1/bank-reconciliation/imports/{id}/auto-match`).

A rigorous audit and verified probes identified five critical vulnerabilities in the current reconciliation implementation:
1. **Duplicate Bank Statement Line Matching**: `match_manual` does not verify whether a `BankStatementLine` is already reconciled. A single statement line can be reconciled multiple times, creating duplicate active `BankReconciliation` records.
2. **Target Reuse Across Bank Lines**: Multiple distinct bank statement lines can be matched to the exact same financial target (`JournalLine`, `MoneyMovement`, or `Transaction`). The same book cash entry can be claimed repeatedly.
3. **Arbitrary Caller-Controlled Amounts**: The API accepts `matched_amount` directly from request payloads without asserting equality against the bank statement line or the financial target. A caller can submit arbitrary amounts that contradict both bank and ledger reality.
4. **Auto-Match Reused-Target Blindness**: The auto-matching engine fails to filter out already-reconciled financial targets or check for intra-batch collisions, permitting duplicate links when multiple bank lines match the same book record.
5. **Dashboard Distortion**: The `CashCompletenessDashboard` calculates `unmatched_book_amount` via aggregate subtraction (`total_book_cash - matched_amount`) instead of aggregating unreconciled book lines. Under duplicate or arbitrary matches, the dashboard produces mathematically corrupted and misleading metrics.

**Important Operational Boundary**: This turn is strictly limited to Specification, Architecture, and Migration Analysis. No production code, tests, migrations, or CP1 implementation may be committed in this turn.

---

## 2. Domain Model & Cardinality Analysis

### 2.1 Current Implementation State
- **BankStatementLine**: Identified by `id` (UUID), belongs to `organization_id`, associated with `import_id`. Contains `credit` (inflow) and `debit` (outflow) as non-negative `Numeric(18, 2)` decimals. Contains `reconciliation_status` initialized to `UNMATCHED_BANK`.
- **BankReconciliation**: Identified by `id` (UUID), links `statement_line_id` to three nullable target foreign keys: `journal_line_id`, `money_movement_id`, and `transaction_id`. Tracks `matched_amount: Numeric(18, 2)`, `match_rule: String(100)`, `matched_by: UUID` (FK to `users.id`), and `status: ReconciliationStatus` (default `MATCHED`).
- **Database Schema Constraints (Migration 017)**: Defines foreign keys with `ON DELETE CASCADE` on `statement_line_id` and `ON DELETE SET NULL` on target columns. Contains **zero unique constraints** on `statement_line_id` or target columns. Contains **zero check constraints** on target presence or matched amounts.

### 2.2 Proof of Full-Match (1:1) Cardinality Contract
The current product design operates strictly on a **Full-Match (1:1)** cardinality model:
1. **No Partial Balances**: Neither `BankStatementLine` nor `BankReconciliation` maintains a "remaining" or "partially matched" balance column. `BankStatementLine.reconciliation_status` transitions directly from `UNMATCHED_BANK` to `MATCHED`.
2. **Auto-Match Exactness**: `auto_match_statement` matches strictly on `MoneyMovement.amount == line_amount` or `JournalLine.debit_amount == line.credit` / `JournalLine.credit_amount == line.debit`. It assumes full 1:1 parity.
3. **Dashboard Aggregates**: The dashboard sums the entire bank line volume (`l.credit + l.debit`) when `l.reconciliation_status == MATCHED`, which is only mathematically sound under full 1:1 matching.
4. **Target Discrete Semantics**: A posted `JournalLine` represents a single discrete debit or credit leg. Claiming the same leg across multiple bank lines double-counts ledger cash.

Therefore:
- **Can one bank line have multiple active matches by design?** `NO`.
- **Can one target be matched to multiple bank lines by design?** `NO`.
- **Can a single reconciliation be partial by design?** `NO` (partial matching is currently unimplemented in backend services, APIs, and UI).
- **Is `matched_amount` intended to represent full bank-line and target amount?** `YES`.

---

## 3. Core Requirements (RECON-R01 to RECON-R16)

- **RECON-R01 (Statement-Line Cardinality Invariant)**: A bank statement line MUST NOT have more than one active reconciliation record. Any attempt to reconcile an already-matched statement line must be rejected with HTTP 409 Conflict (`DuplicateEntityException`).
- **RECON-R02 (Target Cardinality Invariant)**: A financial target (`JournalLine`, `MoneyMovement`, or `Transaction`) MUST NOT be matched to more than one bank statement line. Any attempt to match an already-reconciled target must be rejected with HTTP 409 Conflict (`DuplicateEntityException`).
- **RECON-R03 (Single-Target Discriminator Invariant)**: Every reconciliation record MUST reference exactly one valid target (`journal_line_id`, `money_movement_id`, or `transaction_id`). Zero targets or multiple targets in a single record are strictly rejected with HTTP 422 Unprocessable Content (`InvariantViolationException`).
- **RECON-R04 (Amount Integrity Invariant)**: The reconciliation `matched_amount` MUST equal the bank statement line amount (`credit` if credit > 0 else `debit`) and MUST equal the target's cash amount. Arbitrary amounts are rejected with HTTP 422 Unprocessable Content (`InvariantViolationException`).
- **RECON-R05 (Directional Consistency Invariant)**: Bank inflow (`credit > 0`) can only match a Cash Debit `JournalLine` or `MovementDirection.IN`. Bank outflow (`debit > 0`) can only match a Cash Credit `JournalLine` or `MovementDirection.OUT`. Directional mismatch is rejected with HTTP 422 Unprocessable Content (`InvariantViolationException`).
- **RECON-R06 (Target Eligibility & Status Invariant)**: Financial targets must be eligible: `Transaction` must not be `REJECTED`, `MoneyMovement` must match the statement's `payment_account_id`, and `JournalLine` must belong to a cash/payment account.
- **RECON-R07 (Auto-Match Target & Line Filtering)**: `auto_match_statement` MUST exclude all financial targets and bank statement lines that already participate in an active `BankReconciliation` record, and must prevent intra-batch collisions.
- **RECON-R08 (Unified Validation Boundary)**: Manual matching and auto-matching MUST share the same domain validation rules and invariants to prevent policy drift.
- **RECON-R09 (Concurrency Safety & Race Defense)**: Concurrent matching requests targeting the same bank statement line or target must fail closed. Pessimistic row locking (`SELECT ... FOR UPDATE` on `BankStatementLine`) and database unique constraints prevent concurrent race conditions.
- **RECON-R10 (Database Constraint Defense-in-Depth)**: The database schema MUST enforce cardinality and target invariants via unique constraints / partial unique indexes and check constraints on `bank_reconciliations`.
- **RECON-R11 (Historical Data Preflight Guard)**: Forward migrations MUST include a fail-closed preflight check that halts on historical duplicate, zero-target, multi-target, or amount-mismatched records. Automatic silent deletion is strictly prohibited.
- **RECON-R12 (Dashboard Correctness)**: `get_cash_completeness_dashboard` MUST derive `unmatched_book_amount` from actual unreconciled `JournalLine`s on payment accounts, rather than aggregate synthetic subtraction.
- **RECON-R13 (Tenant Isolation Preservation)**: Multi-tenant reference validation from FIN-P1-105 MUST be preserved: foreign tenant UUIDs return HTTP 404 `EntityNotFoundException`.
- **RECON-R14 (Authorization & Provenance Preservation)**: Role enforcement from AUTHZ-001 MUST be preserved: `ADMIN`, `MANAGER`, and `OPERATOR` roles are authorized, and `matched_by` provenance is recorded.
- **RECON-R15 (Zero Ledger/Posting Rule Alteration)**: General ledger posting rules, journal balances, `AccountingEngine` behavior, and debit/credit equality MUST remain 100% untouched.
- **RECON-R16 (PostgreSQL Validation Gate)**: Database constraints, concurrency locks, and migration behavior MUST be verified against PostgreSQL 16 in CI.

---

## 4. Failure Mode & Severity Classification

| Characteristic | Evaluation | Explanation |
| :--- | :---: | :--- |
| **Fail-Closed Currently?** | **NO** | Current implementation fails open; accepts duplicates, arbitrary amounts, and reused targets. |
| **Partial Write?** | **NO** | Single reconciliation row is created, but the record itself is invalid. |
| **Durable Invalid Record?** | **YES** | Duplicates and mismatched amounts persist indefinitely in PostgreSQL. |
| **Posted Journal Modified?** | **NO** | Double-entry journals, lines, and balances remain untouched. |
| **Ledger Total Modified?** | **NO** | General ledger totals are not modified. |
| **Reconciliation Control Distorted?** | **YES** | Cash completeness, matched volume, and audit logs are falsified. |
| **Recoverable Through API?** | **NO** | No unmatch or deletion route exists on the API surface. |
| **Cross-Tenant Vulnerability?** | **NO** | FIN-P1-105 tenant reference checks successfully prevent cross-tenant linkage. |
| **Authorized Role Required?** | **YES** | Requires `ADMIN`, `MANAGER`, or `OPERATOR` under AUTHZ-001. |

**Classification**: High-Severity Cash-Control and Reconciliation-Integrity Defect.

---

## 5. Explicit Out of Scope

1. **Accounting Posting Rules**: No alterations to double-entry rules, debit/credit mechanics, or `JournalEntry` generation.
2. **Transaction Processing Lifecycle**: No modifications to transaction approval or posting engines.
3. **Partial Reconciliation Feature**: Implementing multi-split or partial matching is deferred until a formal accounting policy is approved.
4. **Foreign Currency (FX) Reconciliation**: FX gain/loss and currency conversion remain out of scope.
5. **Application-Level Unmatch Route**: While desirable, introducing unmatch/cancellation routes is deferred to a dedicated feature to keep RECON-001 tightly focused on integrity.
6. **Automatic Historical Cleanup**: No migrations may automatically delete or prune historical rows.

---

## 6. Phased Implementation Checkpoints

1. **CP1: Executable RED Reproduction & Characterization Suite** (Strict xfail coverage of 5 defect classes, concurrency characterization, read-only preflight query shape).
2. **CP2: Canonical Reconciliation Integrity Service Boundary** (Unified validation method, single-match guards, single-target discriminator, amount/directional checks, auto-match filtering, row-locking).
3. **CP3: Database Constraints, Migration Safety & Dashboard Correction** (Alembic migration with fail-closed preflight, partial unique indexes, check constraints, dashboard calculation correction).
4. **CP4: Full Regression, Security/Accounting Gate, Independent Review & Remote Delivery** (Comprehensive local test suites, frontend build, CI verification, PR creation, squash merge).
