# Contract Specification: Reconciliation Integrity & Invariants

**Document Reference**: `contracts/reconciliation-integrity.md`  
**Feature**: RECON-001  
**Status**: APPROVED CONTRACT  

---

## 1. Terminology

- **Bank Statement Line (`BankStatementLine`)**: A single line item imported from an external bank statement. Represents an immutable cash movement record reported by the banking institution.
- **Financial Target**: An internal company financial record representing a cash ledger leg or commercial event (`JournalLine`, `MoneyMovement`, or `Transaction`).
- **Reconciliation Record (`BankReconciliation`)**: An authoritative association linking exactly one `BankStatementLine` to exactly one Financial Target.
- **Inflow**: Money deposited into the bank account (`BankStatementLine.credit > 0`). In internal books, corresponds to a Debit to a cash asset account or `MovementDirection.IN`.
- **Outflow**: Money withdrawn from the bank account (`BankStatementLine.debit > 0`). In internal books, corresponds to a Credit to a cash asset account or `MovementDirection.OUT`.
- **Full Reconciliation (1:1)**: A reconciliation model where one complete bank statement line is matched to one complete financial target of equal value.

---

## 2. Cardinality Contracts

### 2.1 Bank Statement Line Cardinality
- **Contract**: Exactly one active `BankReconciliation` record may exist per `BankStatementLine`.
- **Enforcement**:
  - Service: `match_manual` verifies that `BankStatementLine.reconciliation_status != MATCHED` and that no active `BankReconciliation` references `statement_line_id`.
  - Database: Partial unique index `uq_bank_reconciliations_statement_line` on `(statement_line_id) WHERE status = 'MATCHED'` (guaranteeing 1:1 active matching while permitting future unmatch/cancellation transitions).
- **Violation Behavior**: HTTP 409 Conflict (`DuplicateEntityException`).

### 2.2 Financial Target Cardinality
- **Contract**: Exactly one `BankStatementLine` may be reconciled against any single Financial Target. A financial target cannot participate in multiple reconciliation records.
- **Enforcement**:
  - Service: `match_manual` verifies that the target ID is not referenced in any existing `BankReconciliation` record.
  - Database: Partial unique indexes on `journal_line_id`, `money_movement_id`, and `transaction_id`.
- **Violation Behavior**: HTTP 409 Conflict (`DuplicateEntityException`).

### 2.3 Single-Target Discriminator
- **Contract**: A `BankReconciliation` record MUST populate exactly one target foreign key (`journal_line_id`, `money_movement_id`, or `transaction_id`). Zero targets (orphan matches) and multiple targets (>1 target populated) are strictly prohibited.
- **Enforcement**:
  - Service: Request validator requires exactly one non-null target identifier.
  - Database: Check constraint `ck_bank_recon_exactly_one_target`.
- **Violation Behavior**: HTTP 422 Unprocessable Content (`InvariantViolationException`).

---

## 3. Supported Target Types & Eligibility

### 3.1 `JournalLine`
- **Definition**: Individual debit or credit leg of a double-entry `JournalEntry`.
- **Ownership**: `JournalEntry.organization_id == organization_id`.
- **Account Eligibility**: Must have `payment_account_id` populated, matching the statement's payment account.
- **Amount & Direction**:
  - For bank Inflow (`credit > 0`): `JournalLine.debit_amount == line.credit` and `JournalLine.credit_amount == Decimal("0.00")`.
  - For bank Outflow (`debit > 0`): `JournalLine.credit_amount == line.debit` and `JournalLine.debit_amount == Decimal("0.00")`.

### 3.2 `MoneyMovement`
- **Definition**: Recorded cash movement record.
- **Ownership**: `MoneyMovement.organization_id == organization_id`.
- **Account Eligibility**: `MoneyMovement.payment_account_id == statement_import.payment_account_id`.
- **Amount & Direction**:
  - For bank Inflow (`credit > 0`): `MoneyMovement.amount == line.credit` and `direction == MovementDirection.IN`.
  - For bank Outflow (`debit > 0`): `MoneyMovement.amount == line.debit` and `direction == MovementDirection.OUT`.

### 3.3 `Transaction`
- **Definition**: Staged/approved business event.
- **Ownership**: `Transaction.organization_id == organization_id`.
- **Eligibility**: `Transaction.workflow_status != WorkflowStatus.REJECTED`.
- **Amount**: `Transaction.amount == (line.credit if line.credit > 0 else line.debit)`.

---

## 4. Amount-Comparison Semantics

1. **Authoritative Bank Amount**:
   ```python
   bank_line_amount = line.credit if line.credit > Decimal("0.00") else line.debit
   ```
2. **Derived Matched Amount**:
   `matched_amount` is determined by `bank_line_amount`. The caller-supplied `matched_amount` is verified to strictly equal `bank_line_amount`. Any discrepancy raises HTTP 422 Unprocessable Content (`InvariantViolationException`).
3. **Exact Target Amount Match**:
   The financial target's cash amount must equal `bank_line_amount` exactly down to 2 decimal places. No partial or rounded matching is permitted in this contract.

---

## 5. Manual vs. Auto-Match Single Source of Truth

- **Unified Validator**: Both manual matching (`POST /reconcile`) and automated matching (`POST /auto-match`) pass through a shared validation routine `_validate_and_resolve_match`.
- **Auto-Match Candidate Selection**:
  - Auto-match queries for `MoneyMovement` and `JournalLine` MUST explicitly join or filter with `WHERE id NOT IN (SELECT target_id FROM bank_reconciliations)`.
  - Intra-batch candidate allocation must track matched IDs in memory during the execution loop to prevent two identical lines in the same import file from claiming the same book candidate.

---

## 6. Concurrency Contract

- **Row Locking**: Matching operations execute inside a transaction that locks the `BankStatementLine` via `SELECT ... FOR UPDATE`.
- **Concurrent Duplicate Handling**: If two concurrent workers attempt to reconcile the same line or the same target simultaneously:
  - Worker 1 acquires lock and commits.
  - Worker 2 waits on lock; upon waking, service validation detects existing match and raises 409 Conflict.
  - If a race bypasses service memory, PostgreSQL unique constraints trigger `UniqueViolation` (SQLSTATE `23505`), failing closed without data corruption.

---

## 7. Database Invariant Strategy

1. `uq_bank_reconciliations_statement_line` (UNIQUE on `statement_line_id WHERE status = 'MATCHED'`)
2. `uq_bank_reconciliations_journal_line` (UNIQUE on `journal_line_id WHERE journal_line_id IS NOT NULL`)
3. `uq_bank_reconciliations_money_movement` (UNIQUE on `money_movement_id WHERE money_movement_id IS NOT NULL`)
4. `uq_bank_reconciliations_transaction` (UNIQUE on `transaction_id WHERE transaction_id IS NOT NULL`)
5. `ck_bank_recon_exactly_one_target` (CHECK that sum of non-null target flags equals 1)
6. `ck_bank_recon_matched_amount_positive` (CHECK `matched_amount > 0`)

*Note on In-Memory SQLite Support*: In `BankReconciliation.__table_args__`, partial indexes must declare both `postgresql_where` and `sqlite_where` to ensure identical constraint behavior across SQLite unit tests and PostgreSQL integration tests.

---

## 8. Dashboard Correctness Semantics

- **Matched Amount**: Sum of `credit + debit` across all `BankStatementLine`s where `reconciliation_status == MATCHED`.
- **Unmatched Bank Amount**: Sum of `credit + debit` across all `BankStatementLine`s where `reconciliation_status == UNMATCHED_BANK`.
- **Unmatched Book Amount**: Direct aggregation of cash `JournalLine`s that have no reconciliation:
  ```sql
  SELECT COALESCE(SUM(jl.debit_amount + jl.credit_amount), 0.00)
  FROM journal_lines jl
  JOIN journal_entries je ON jl.journal_entry_id = je.id
  LEFT JOIN bank_reconciliations br ON jl.id = br.journal_line_id
  WHERE je.organization_id = :org_id
    AND jl.payment_account_id = :payment_account_id
    AND br.id IS NULL;
  ```
  Synthetic subtractions (`total_book - matched_bank`) are strictly prohibited.

---

## 9. Historical Data Boundary & Preflight

- The Alembic forward migration contains a fail-closed inspection query checking:
  1. Duplicate `statement_line_id` (where status = 'MATCHED')
  2. Duplicate `journal_line_id`
  3. Duplicate `money_movement_id`
  4. Duplicate `transaction_id`
  5. Multi-target rows (>1 target populated)
  6. Zero-target rows (all targets NULL)
  7. Non-positive amounts (`matched_amount <= 0`)
  8. Amount discrepancies between statement line and reconciliation record
- If violations exist, the migration aborts with a descriptive exception. No silent deletes or updates are allowed.

---

## 10. Error Contract & Validation Precedence

### 10.1 Validation Precedence Hierarchy
To guarantee zero regressions across multi-tenant security suites (specifically FIN-P1-105 `test_bank_reconciliation_mixed_reference_atomicity_rejected`), service validation MUST strictly execute in the following precedence order:

1. **Precedence 1 — Tenant & Entity Resolution (HTTP 404 `EntityNotFoundException`)**:
   - For *every* non-null target UUID supplied in the request (`journal_line_id`, `money_movement_id`, `transaction_id`), verify entity existence and organization ownership upfront.
   - If any supplied target does not exist or belongs to another tenant, fail immediately with 404 `NOT_FOUND` before checking target count or business invariants.
2. **Precedence 2 — Single-Target Discriminator (HTTP 422 `InvariantViolationException`)**:
   - Assert that exactly one target column is populated.
   - If 0 targets or >1 targets are provided, fail with 422 `INVARIANT_VIOLATION`.
3. **Precedence 3 — Unreconciled Status / Cardinality (HTTP 409 `DuplicateEntityException`)**:
   - Assert `BankStatementLine.reconciliation_status != MATCHED` and no active `BankReconciliation` exists for `statement_line_id`.
   - Assert the resolved target is not already referenced in any active `BankReconciliation`.
   - If already reconciled, fail with 409 `DUPLICATE_ENTITY`.
4. **Precedence 4 — Directional & Amount Integrity (HTTP 422 `InvariantViolationException`)**:
   - Assert bank inflow matches cash debit / `MovementDirection.IN`; bank outflow matches cash credit / `MovementDirection.OUT`.
   - Assert `matched_amount == bank_line_amount == target_amount`.
   - If mismatched, fail with 422 `INVARIANT_VIOLATION`.

### 10.2 Error Response Mapping

| Condition | Exception Class | HTTP Status | Error Code |
| :--- | :--- | :---: | :--- |
| Target not found or cross-tenant ID | `EntityNotFoundException` | 404 | `NOT_FOUND` |
| Zero targets or >1 target provided | `InvariantViolationException` | 422 | `INVARIANT_VIOLATION` |
| Bank statement line already reconciled | `DuplicateEntityException` | 409 | `DUPLICATE_ENTITY` |
| Financial target already reconciled | `DuplicateEntityException` | 409 | `DUPLICATE_ENTITY` |
| Amount mismatch between bank & target | `InvariantViolationException` | 422 | `INVARIANT_VIOLATION` |
| Directional mismatch (e.g. Inflow vs Outflow) | `InvariantViolationException` | 422 | `INVARIANT_VIOLATION` |
| Concurrent database lock/contention | `TransactionContentionError` | 409 | `TRANSACTION_CONTENTION` |

---

## 11. Tenant & Authorization Preservation

- Multi-tenant foreign reference checks from **FIN-P1-105** remain active: referencing a cross-tenant target returns 404 `EntityNotFoundException`, identical to a nonexistent ID.
- Application role guards from **AUTHZ-001** remain active: manual reconciliation endpoints require `ADMIN`, `MANAGER`, or `OPERATOR`.
- Audit provenance: `matched_by` records the authenticated user ID for manual matches.

---

## 12. Explicit Out of Scope

- Double-entry ledger rules and `AccountingEngine` semantics.
- Partial reconciliation, multi-split matching, and over-allocation.
- Foreign exchange (FX) currency translation.
- Application-level unmatch/reversal routes (deferred to future feature).
- Automatic historical cleanup or truncation.
