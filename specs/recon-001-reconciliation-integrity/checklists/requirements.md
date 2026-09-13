# Requirements Traceability Checklist: RECON-001

**Feature**: RECON-001 — Enforce Reconciliation Cardinality, Amount Integrity, and Dashboard Correctness
**Status**: SPECIFICATION & CHECKPOINT PLANNING

---

## 1. Requirement Traceability Matrix

| Req ID | Description | CP Target | Implementation Verification | Status |
| :--- | :--- | :---: | :--- | :---: |
| **RECON-R01** | Statement line cardinality (at most 1 active match per line) | CP1, CP2, CP3 | Tested in `test_manual_match_duplicate_statement_line_rejected`; enforced in service & DB index. | Planned |
| **RECON-R02** | Target cardinality (target matched at most once across all lines) | CP1, CP2, CP3 | Tested in `test_manual_match_duplicate_*_rejected`; enforced in service & DB partial indexes. | Planned |
| **RECON-R03** | Single-target discriminator (exactly 1 target FK populated) | CP1, CP2, CP3 | Tested in `test_manual_match_*_targets_rejected`; enforced in service & DB check constraint. | Planned |
| **RECON-R04** | Amount integrity (`matched_amount == bank_line == target`) | CP1, CP2 | Tested in `test_manual_match_amount_mismatch_rejected`; enforced in service validation. | Planned |
| **RECON-R05** | Directional consistency (Inflow -> Debit, Outflow -> Credit) | CP1, CP2 | Tested in `test_manual_match_directional_mismatch_rejected`; enforced in service validation. | Planned |
| **RECON-R06** | Target eligibility (payment account match, non-rejected status) | CP1, CP2 | Tested in unit suite; enforced in service validation. | Planned |
| **RECON-R07** | Auto-match excludes already-reconciled targets & prevents collisions | CP1, CP2 | Tested in `test_auto_match_excludes_*`; enforced in `auto_match_statement`. | Planned |
| **RECON-R08** | Unified validation boundary for manual and auto-match | CP2 | Service code structure enforces shared `_validate_and_resolve_match`. | Planned |
| **RECON-R09** | Concurrency safety via row-level locking + DB constraints | CP1, CP2, CP3 | Tested in `test_concurrent_manual_match_*_race`; enforced via `FOR UPDATE` + DB indexes. | Planned |
| **RECON-R10** | Database defense-in-depth (unique indexes & check constraints) | CP3 | Verified via Alembic migration `024` and PostgreSQL schema inspection. | Planned |
| **RECON-R11** | Historical data preflight guard in Alembic migration | CP1, CP3 | Tested in `test_historical_data_preflight_query_shape`; migration fails closed on bad data. | Planned |
| **RECON-R12** | Dashboard correctness: `unmatched_book` from unreconciled lines | CP1, CP3 | Tested in `test_dashboard_unmatched_book_*`; direct SQL query replaces synthetic subtraction. | Planned |
| **RECON-R13** | Multi-tenant reference validation preserved (FIN-P1-105) | CP1, CP4 | Full regression suite passes; cross-tenant target UUIDs return 404. | Planned |
| **RECON-R14** | Role authorization preserved (`ADMIN`/`MANAGER`/`OPERATOR`) | CP1, CP4 | Full regression suite passes; AUTHZ-001 tests pass. | Planned |
| **RECON-R15** | Zero double-entry ledger or posting rule modifications | CP1, CP4 | Verified in accounting regression slice; 0 ledger code modified. | Planned |
| **RECON-R16** | Mandatory PostgreSQL validation in CI | CP3, CP4 | Real PostgreSQL 16 executes integration tests and Alembic migrations. | Planned |

---

## 2. Checkpoint Quality Gates

### Checkpoint 1 (CP1) Gate:
- [ ] Executable RED reproduction suite implemented in `test_recon_001_reconciliation_integrity.py`.
- [ ] All RED tests decorated with `@pytest.mark.xfail(strict=True, raises=AssertionError)`.
- [ ] Overall test suite passes without unexpected errors.
- [ ] Zero production application code modified.
- [ ] Zero migrations added or applied.
- [ ] Clean worktree and atomic git commit.

### Checkpoint 2 (CP2) Gate:
- [ ] `_validate_and_resolve_match` implemented in `BankReconciliationService`.
- [ ] `match_manual` enforces single-match, single-target, amount equality, and directional consistency.
- [ ] `auto_match_statement` refactored to filter out used targets and prevent intra-batch collisions.
- [ ] Row-level lock (`SELECT ... FOR UPDATE`) added to `BankStatementLine`.
- [ ] Strict xfail markers removed; CP1 service-level tests transition to GREEN.
- [ ] Unit test suite passes without regression.
- [ ] Clean worktree and atomic git commit.

### Checkpoint 3 (CP3) Gate:
- [ ] Alembic migration `024_recon_integrity_invariants.py` created with fail-closed preflight check.
- [ ] Partial unique indexes and check constraints applied to `bank_reconciliations`.
- [ ] `BankReconciliation` SQLAlchemy model updated with matching constraints.
- [ ] `get_cash_completeness_dashboard` updated to calculate `unmatched_book` via direct unreconciled query.
- [ ] Legacy unit test `test_cash_completeness_dashboard_and_reconciliation` updated to supply a valid target.
- [ ] PostgreSQL integration tests pass.
- [ ] Clean worktree and atomic git commit.

### Checkpoint 4 (CP4) Gate:
- [ ] Complete backend test suite passes (0 failures, 0 unexpected skips).
- [ ] Frontend tests, linter, typecheck, and build pass.
- [ ] Alembic single head (`024`) and zero schema drift (`alembic check`).
- [ ] Independent code review completed with 0 Critical, 0 High, 0 Medium findings.
- [ ] Branch pushed, PR created, GitHub CI passes terminal green, PR squash-merged to main.
