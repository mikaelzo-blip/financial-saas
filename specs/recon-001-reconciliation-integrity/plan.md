# Implementation Plan: Bank Reconciliation Integrity (RECON-001)

**Feature**: RECON-001 — Enforce Reconciliation Cardinality, Amount Integrity, and Dashboard Correctness  
**Status**: SPECIFICATION & CHECKPOINT PLANNING  
**Authority**: Constitution v2.0.0, Financial Concept v1, AGENTS.md, Checkpoint-Driven Development Skill  

---

## 1. Architecture Overview & Guiding Principles

1. **Defense-in-Depth (Service + Database)**: Business validation in domain services provides rich, actionable 409/422 responses; database unique constraints and partial indexes provide an immutable, race-free safety barrier.
2. **Single Source of Truth**: Auto-matching and manual matching share a single canonical validation method in `BankReconciliationService`. Auto-match cannot create matches that manual matching would reject.
3. **Fail-Closed on Duplicates and Invariants**: Duplicate statement lines or targets result in HTTP 409 Conflict (`DuplicateEntityException`). Amount mismatches, directional conflicts, or multi/zero targets result in HTTP 422 Unprocessable Content (`InvariantViolationException`).
4. **Historical Data Protection**: Migrations enforce forward constraints with strict preflight verification. Zero automatic or silent deletion of existing data.
5. **Zero Accounting Bleed**: Double-entry ledger journals, balances, and posting engines remain strictly untouched.

---

## 2. Checkpoint Architecture

```text
+-----------------------------------------------------------------------------------+
| CP1: Executable RED Reproduction & Characterization Suite                         |
| - Implement dedicated test suite with strict xfail markers                        |
| - Characterize duplicate statement line match (Probe A)                           |
| - Characterize duplicate target reuse across JL, MM, TX (Probe B)                 |
| - Characterize arbitrary matched_amount acceptance (Probe C)                      |
| - Characterize auto-match target reuse and collision (Probe D)                     |
| - Characterize dashboard distortion (Probe E)                                     |
| - Characterize concurrent race conditions                                         |
| - Implement read-only historical preflight query shape                            |
| - Verify clean baseline, 0 production code changes, 0 migrations                  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP2: Canonical Reconciliation Integrity Service Boundary                          |
| - Implement unified validation method in BankReconciliationService                |
| - Enforce statement-line single-match check (409 Conflict)                        |
| - Enforce target single-match check for JL, MM, TX (409 Conflict)                 |
| - Enforce single-target discriminator check (exactly 1 target required, 422)      |
| - Enforce amount integrity and directional matching (422)                         |
| - Enforce target eligibility (payment account match, non-rejected status)         |
| - Refactor auto_match_statement to exclude used targets and lines                 |
| - Add pessimistic row lock (SELECT ... FOR UPDATE) on BankStatementLine           |
| - Remove strict xfail markers: verify CP1 tests turn GREEN                        |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP3: Database Constraints, Fail-Closed Migration & Dashboard Correction          |
| - Implement Alembic migration 024_reconciliation_integrity_constraints.py:        |
|   * Fail-closed preflight historical check                                        |
|   * Partial unique index on statement_line_id (or unique constraint)              |
|   * Partial unique indexes on journal_line_id, money_movement_id, transaction_id  |
|   * Check constraint: exactly one target FK populated                             |
|   * Check constraint: matched_amount > 0                                          |
| - Update BankReconciliation SQLAlchemy model __table_args__                       |
| - Correct get_cash_completeness_dashboard unmatched_book calculation              |
| - Update legacy unit tests to supply valid target fixtures                        |
| - Verify PostgreSQL migration upgrade/downgrade and concurrency enforcement       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP4: Full Regression, Security Gate, Independent Review & Remote Delivery         |
| - Run complete unit, integration, PostgreSQL, and AUTHZ-001 suites                |
| - Run frontend tests, lint, typecheck, and production build                       |
| - Verify 0 regressions, 0 ledger modifications, clean worktree                    |
| - Independent read-only code review                                               |
| - Push hermes/recon-001-reconciliation-integrity, open PR, monitor GitHub CI     |
+-----------------------------------------------------------------------------------+
```

---

## 3. Detailed Checkpoint Breakdown

### Checkpoint 1: RED Reproduction & Characterization Suite
- **Goal**: Establish an authoritative, executable RED test baseline capturing all 5 defect categories and concurrency vulnerabilities before touching production code.
- **File to Create**: `backend/tests/security/test_recon_001_reconciliation_integrity.py`.
- **Test Scenarios**:
  1. `test_manual_match_duplicate_statement_line_rejected`: Assert 409 Conflict when reconciling an already-matched statement line.
  2. `test_manual_match_duplicate_journal_line_rejected`: Assert 409 Conflict when reconciling a `JournalLine` already reconciled.
  3. `test_manual_match_duplicate_money_movement_rejected`: Assert 409 Conflict when reconciling a `MoneyMovement` already reconciled.
  4. `test_manual_match_duplicate_transaction_rejected`: Assert 409 Conflict when reconciling a `Transaction` already reconciled.
  5. `test_manual_match_zero_targets_rejected`: Assert 422 Unprocessable Content when request specifies no target IDs.
  6. `test_manual_match_multiple_targets_rejected`: Assert 422 Unprocessable Content when request specifies >1 target IDs.
  7. `test_manual_match_amount_mismatch_rejected`: Assert 422 Unprocessable Content when `matched_amount` != bank line amount or target amount.
  8. `test_manual_match_directional_mismatch_rejected`: Assert 422 Unprocessable Content when bank credit is matched against cash credit (or bank debit against cash debit).
  9. `test_auto_match_excludes_already_reconciled_targets`: Assert auto-match skips targets already in `BankReconciliation`.
  10. `test_auto_match_intra_batch_collision_prevention`: Assert two identical bank lines in the same import do not match the same single book target.
  11. `test_dashboard_unmatched_book_calculation_correctness`: Assert `unmatched_book_amount` reflects real unreconciled journal lines rather than `total_book - matched_bank`.
  12. `test_concurrent_manual_match_statement_line_race`: Assert concurrent matching requests for the same statement line fail closed with exactly one winner.
  13. `test_concurrent_manual_match_target_race`: Assert concurrent matching requests for the same target fail closed with exactly one winner.
  14. `test_historical_data_preflight_query_shape`: Test the read-only preflight query on clean and synthetic invalid fixtures.
- **Discipline**: Mark expected failing tests with `@pytest.mark.xfail(strict=True, raises=AssertionError)`. Ensure overall test suite remains executable and green. Zero production code edits.

### Checkpoint 2: Canonical Reconciliation Integrity Service Boundary
- **Goal**: Implement canonical validation and matching rules within `BankReconciliationService`.
- **Target Files**:
  - `backend/src/services/bank_reconciliation_service.py`
  - `backend/src/schemas/bank_reconciliation.py`
- **Key Changes**:
  1. Add `_validate_and_resolve_match(self, organization_id, statement_line, req)`:
     - **Precedence 1 (404 Not Found)**: Validate entity existence and organization ownership for ALL non-null target UUIDs upfront. If cross-tenant or nonexistent, raise `EntityNotFoundException` immediately (preserving FIN-P1-105 atomicity and IDOR anti-oracle rules).
     - **Precedence 2 (422 Invariant Violation)**: Check exactly one of `journal_line_id`, `money_movement_id`, `transaction_id` is populated. If 0 or >1, raise `InvariantViolationException`.
     - **Precedence 3 (409 Duplicate Entity)**: Check statement line is not already matched (`reconciliation_status != ReconciliationStatus.MATCHED` and no active `BankReconciliation` with `status == MATCHED`). Check target is not already referenced in any active `BankReconciliation`. If already reconciled, raise `DuplicateEntityException`.
     - **Precedence 4 (422 Invariant Violation)**: Validate direction and amount equality against bank line (`matched_amount == bank_line_amount == target_amount`). If mismatched, raise `InvariantViolationException`.
  2. Implement row-level lock (`select(...).where(...).with_for_update()`) on `BankStatementLine` during `match_manual`.
  3. Refactor `auto_match_statement`:
     - Exclude `MoneyMovement` and `JournalLine` IDs that appear in `BankReconciliation`.
     - Track matched target IDs within the loop to prevent intra-batch collision.
- **Verification**: Remove `@pytest.mark.xfail` from service-level tests. Confirm all transition to GREEN.

### Checkpoint 3: Database Constraints, Fail-Closed Migration & Dashboard Correction
- **Goal**: Add database schema invariants, fail-closed preflight migration, and fix dashboard metrics.
- **Target Files**:
  - `backend/alembic/versions/024_reconciliation_integrity_constraints.py`
  - `backend/src/models/bank_reconciliation.py`
  - `backend/src/services/bank_reconciliation_service.py`
  - `backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py`
- **Key Changes**:
  1. Alembic Migration `024`:
     - Execute fail-closed preflight queries scanning for historical duplicates, zero-target rows, multi-target rows, non-positive amounts (`matched_amount <= 0`), and amount mismatches. If violations exist, raise `RuntimeError` and halt.
     - Create partial unique indexes / constraints:
       - `uq_bank_reconciliations_statement_line` ON `bank_reconciliations(statement_line_id) WHERE status = 'MATCHED'`.
       - `uq_bank_reconciliations_journal_line` ON `bank_reconciliations(journal_line_id) WHERE journal_line_id IS NOT NULL`.
       - `uq_bank_reconciliations_money_movement` ON `bank_reconciliations(money_movement_id) WHERE money_movement_id IS NOT NULL`.
       - `uq_bank_reconciliations_transaction` ON `bank_reconciliations(transaction_id) WHERE transaction_id IS NOT NULL`.
     - Create check constraints:
       - `ck_bank_recon_exactly_one_target`: Exactly one target column is not null.
       - `ck_bank_recon_matched_amount_positive`: `matched_amount > 0`.
  2. Update `BankReconciliation` model `__table_args__` with both `postgresql_where` and `sqlite_where` for partial indexes and check constraints.
  3. Correct `get_cash_completeness_dashboard`:
     - Calculate `unmatched_book` by directly querying unreconciled cash `JournalLine`s (`LEFT JOIN bank_reconciliations ... WHERE br.id IS NULL`).
  4. Update legacy unit tests:
     - Update `test_bank_reconciliation_p2.py` (`test_cash_completeness_dashboard_and_reconciliation`) to supply a valid target fixture.
     - Align `test_fin_p1_105_tenant_reference_hardening.py` (`test_bank_reconciliation_match_same_tenant_journal_line_accepted`) to ensure positive control fixture has matching directional debit/credit and payment account linkage.
- **Verification**: Run Alembic migration against PostgreSQL; verify table definition, unique indexes, and check constraints.

### Checkpoint 4: Full Regression, Security Gate, Independent Review & Remote Delivery
- **Goal**: Verify full repository stability, execute independent review, and deliver verified PR.
- **Verification Matrix**:
  - Dedicated RECON-001 tests: 100% pass.
  - Backend full suite: unit, integration, PostgreSQL, AUTHZ-001, FIN-P1-105.
  - Frontend suite: `npm test`, `npm run lint`, `npm run build`.
  - Migration validation: `alembic check` clean, single head `024`.
  - Independent Code Review: 0 Critical, 0 High, 0 Medium findings.
  - Remote CI: GitHub Actions green across all jobs.
