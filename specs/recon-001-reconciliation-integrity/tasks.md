# Tasks Breakdown: Bank Reconciliation Integrity (RECON-001)

**Feature**: RECON-001 — Enforce Reconciliation Cardinality, Amount Integrity, and Dashboard Correctness
**Status**: CHECKPOINT PLANNING
**Current Branch**: `hermes/recon-001-reconciliation-integrity`

---

## Checkpoint 1: RED Reproduction & Characterization Suite

- [x] **TASK-CP1-01**: Verify baseline environment, git clean worktree, and test dependencies.
- [x] **TASK-CP1-02**: Implement executable characterization test for duplicate statement line matching in `backend/tests/security/test_recon_001_reconciliation_integrity.py` (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
- [x] **TASK-CP1-03**: Implement executable characterization tests for target reuse across `JournalLine`, `MoneyMovement`, and `Transaction` (strict xfail).
- [x] **TASK-CP1-04**: Implement executable characterization tests for single-target discriminator (zero targets and multiple targets in single request, strict xfail).
- [x] **TASK-CP1-05**: Implement executable characterization tests for amount integrity and directional matching (strict xfail).
- [x] **TASK-CP1-06**: Implement executable characterization tests for auto-match target exclusion and intra-batch collisions (strict xfail).
- [x] **TASK-CP1-07**: Implement executable characterization tests for dashboard `unmatched_book_amount` distortion (strict xfail).
- [x] **TASK-CP1-08**: Implement characterization tests for concurrent matching race conditions and historical preflight query validation.
- [x] **TASK-CP1-09**: Run CP1 test suite; assert all xfail tests fail for expected reason; verify 0 production changes, 0 migrations; commit CP1.

---

## Checkpoint 2: Canonical Reconciliation Integrity Service Boundary

- [x] **TASK-CP2-01**: Implement canonical target resolution and validation method `_validate_and_resolve_match` in `BankReconciliationService` respecting strict error precedence: Precedence 1 = Tenant Existence (404), Precedence 2 = Target Discriminator (422), Precedence 3 = Unreconciled Status (409), Precedence 4 = Direction/Amount Integrity (422).
- [x] **TASK-CP2-02**: Enforce statement line single-match check (`reconciliation_status != MATCHED` and no active `BankReconciliation`, raising 409 `DuplicateEntityException`).
- [x] **TASK-CP2-03**: Enforce target single-match check across `JournalLine`, `MoneyMovement`, and `Transaction` (raising 409 `DuplicateEntityException`).
- [x] **TASK-CP2-04**: Enforce single-target discriminator check (exactly one target FK provided, raising 422 `InvariantViolationException`).
- [x] **TASK-CP2-05**: Enforce exact amount equality (`matched_amount == bank_line_amount == target_amount`) and directional consistency (`credit` -> cash debit, `debit` -> cash credit, raising 422 `InvariantViolationException`).
- [x] **TASK-CP2-06**: Enforce target eligibility (payment-account matching; rejected transactions are ineligible reconciliation targets).
- [x] **TASK-CP2-07**: Implement pessimistic row-level locking (`SELECT ... FOR UPDATE`) on `BankStatementLine` in `match_manual` and the selected target row.
- [x] **TASK-CP2-08**: Refactor `auto_match_statement` to exclude already-reconciled targets, prevent intra-batch collisions, and persist through canonical validation.
- [x] **TASK-CP2-09**: Remove CP2-owned strict xfail markers; verify 14 RED cases transition to ordinary passing regressions while dashboard remains strict-XFAIL.
- [x] **TASK-CP2-10**: Run configured verification, complete independent review, and commit CP2.

---

## Checkpoint 3: Database Constraints, Fail-Closed Migration & Dashboard Correction

- [x] **TASK-CP3-01**: Implement Alembic migration `024_recon_integrity_invariants.py` with fail-closed preflight check scanning for historical duplicates (statement lines, JL, MM, TX), zero-target rows, multi-target rows, non-positive amounts (`matched_amount <= 0`), and amount discrepancies.
- [x] **TASK-CP3-02**: Add four active-state partial unique indexes in migration `024` for statement lines, journal lines, money movements, and transactions.
- [x] **TASK-CP3-03**: Add named `ck_bank_recon_exactly_one_target` and `ck_bank_recon_matched_amount_positive` constraints in migration `024`.
- [x] **TASK-CP3-04**: Update `BankReconciliation` metadata with portable partial indexes and named check constraints.
- [x] **TASK-CP3-05**: Correct `get_cash_completeness_dashboard` to aggregate cash `JournalLine`s lacking active journal-line reconciliation references.
- [x] **TASK-CP3-06**: Confirm existing legacy fixtures satisfy the canonical target/direction/account contract; no fixture production semantics were weakened.
- [x] **TASK-CP3-07**: Verify fresh PostgreSQL 16 upgrade/downgrade/re-upgrade, offline SQL, catalog constraints/indexes, 20-worker statement and target races, and zero drift; committed as `120e2a4`.

---

## Checkpoint 4: Full Regression, Security Gate, Independent Review & Remote Delivery

- [x] **TASK-CP4-01**: CI-equivalent complete backend suite after `025_transaction_rejected`: 802 passed, 0 failed, 0 skipped, including AUTHZ-001, FIN-P1-105, FIN-001, accounting, and RECON-001 PostgreSQL tests.
- [x] **TASK-CP4-02**: Final frontend candidate: 66 tests passed; lint, TypeScript typecheck, production build, and production dependency audit passed.
- [x] **TASK-CP4-03**: Fresh PostgreSQL 16 reached `025_transaction_rejected`; Alembic single head/current, zero drift, and offline chain generation passed. CI asserts that head and requires the RECON-001 PostgreSQL group.
- [x] **TASK-CP4-04**: Final independent read-only design and code review passed (0 Critical, 0 High, 0 Medium, 0 Low findings).
- [x] **TASK-CP4-05**: Verify zero Constitution violations and zero ledger modifications.
- [ ] **TASK-CP4-06**: Commit CP4 reconciliation, push branch `hermes/recon-001-reconciliation-integrity`, create PR, monitor GitHub CI to terminal green state, and execute squash merge.
