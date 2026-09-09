# Tasks: Tenant Sequence and Code Integrity Hardening

**Input**: Design documents from `/specs/012-tenant-sequence-and-code-integrity-hardening/`

**Prerequisites**: `spec.md`, `research.md`, `plan.md`, `data-model.md`, `contracts/sequence-generator-interface.md`, and `quickstart.md`.

**Implementation boundary**: These tasks describe future production implementation. This preparation turn creates no backend model, service, migration, or test code.

## Phase 1: Setup and Evidence Gate

- [x] T001 Confirm branch, clean worktree baseline, and current migration head in `PROJECT_STATUS.md`, Git, and PostgreSQL test configuration. The feature branch is correct; the worktree has only untracked Feature 012 specification artifacts and no production source diff.
- [x] T002 Provision or connect to a disposable PostgreSQL database without committing credentials; verify `021_fixed_asset_enhancements` is the current Alembic head. Docker `postgres:16` is running locally as `pg_disposable_f012` on `127.0.0.1:54329`.
- [ ] T003 Add an unmodified PostgreSQL reproduction test at `backend/tests/integration/test_tenant_sequence_postgresql.py` for same-tenant concurrent creates and run it red or document an environment-blocked skip. Throwaway evidence reproduced the behavior, but no tracked integration test was added in this preparation phase.
- [ ] T004 Add an unmodified cross-tenant mismatch reproduction at `backend/tests/integration/test_tenant_code_constraints_postgresql.py` covering movement, settlement, and asset codes; record the current global-constraint rejection before changing production code. Throwaway evidence reproduced the behavior, but no tracked integration test was added in this preparation phase.
- [x] T005 Run the existing live PostgreSQL baseline tests and record exact connection, migration-head, and schema results before any implementation change. The chain applies from scratch to `021_fixed_asset_enhancements`, live constraints were inspected, and the fresh-chain `alembic check` exposed pre-existing model/schema drift.

## Phase 2: Foundational Database-Backed Allocation

- [ ] T006 Write unit tests first for namespace rendering, tenant/year scope keys, shared `TRX` namespace, padding, year rollover, and the approved non-year `SET` scope representation (`scope_key="GLOBAL"`) in `backend/tests/unit/test_sequence_allocator.py`.
- [ ] T007 Run `uv run pytest tests/unit/test_sequence_allocator.py -v` and confirm the new behavior fails for the expected missing allocator contract before adding production implementation.
- [ ] T008 Create the tenant sequence model in `backend/src/models/tenant_sequence.py` and register it through the existing model import path, with a unique scope key on `(organization_id, namespace, scope_key)` where all three columns are `NOT NULL`.
- [ ] T009 Add the allocator implementation in the repository-native service location, exposing `allocate_next(session, organization_id, namespace, scope_key)` as defined in `contracts/sequence-generator-interface.md`.
- [ ] T010 Implement conflict-safe first-row bootstrap and `SELECT ... FOR UPDATE` allocation inside the caller transaction; do not commit independently and do not use an in-process lock.
- [ ] T011 Add bounded exhausted-range and collision errors using existing exception conventions; ensure a failed SQL transaction is not reused after a uniqueness error.
- [ ] T012 Run allocator unit tests and a focused PostgreSQL allocator test; verify tenant isolation, empty-scope concurrency, rollback, and no duplicate committed values.

## Phase 3: User Story 1 — Race-Proof Core Generators (P1)

- [ ] T013 Write failing tests for `TransactionService.generate_transaction_code` and `ReversalService.generate_reversal_code` sharing one tenant/year `TRX` allocation namespace, including concurrent normal/reversal creation.
- [ ] T014 Replace the independent COUNT+1 implementations in `backend/src/services/transaction_service.py` and `backend/src/services/reversal_service.py` with the shared allocator while preserving `TRX-YYYY-######`.
- [ ] T015 Write failing tests for journal entry, project, document, invoice, bill, advance, retention-release, and money-movement generators preserving their exact formats under concurrent creates.
- [ ] T016 Replace the COUNT/max-suffix implementations in `backend/src/services/accounting_engine.py`, `project_service.py`, `document_service.py`, `payable_service.py`, `receivable_service.py`, and `money_movement_service.py` with allocator calls using the correct organization and business-date scope.
- [ ] T017 Add settlement allocation tests for the approved non-year `SET-######` scope (`scope_key="GLOBAL"`) and update `_generate_settlement_code` without inventing a new external format.
- [ ] T018 Verify all direct callers of the modified generators, including HTTP, background worker, WhatsApp/Baileys intake, asynchronous document processing, payment, retention, fixed-asset, and reversal paths; ensure the same `AsyncSession` transaction carries allocation and record creation.
- [ ] T019 Add PostgreSQL N=50 concurrency tests for representative and highest-risk generators, asserting unique committed codes, no partial records, correct organization ownership, and no unhandled collision.

## Phase 4: User Story 2 — Tenant-Scoped Composite Uniqueness (P1)

- [ ] T020 Write failing model/migration tests proving that same-tenant duplicate movement, settlement, and asset codes are rejected while cross-tenant identical codes are accepted after migration.
- [ ] T021 Add a new Alembic revision after `021_fixed_asset_enhancements` that preflights duplicate `(organization_id, code)` tuples and verifies expected live global constraint names before DDL.
- [ ] T022 In the migration, create composite constraints before dropping global constraints for `money_movements.movement_code`, `settlements.settlement_code`, and `fixed_assets.asset_code`; do not modify data.
- [ ] T023 Update `backend/src/models/money_movement.py` and `backend/src/models/fixed_asset.py` to remove column-level global uniqueness and declare matching `UniqueConstraint` definitions.
- [ ] T024 Add migration tests for upgrade, downgrade, offline SQL generation, missing-constraint fail-closed behavior, duplicate-preflight fail-closed behavior, and historical-value preservation.
- [ ] T025 Run the migration on a disposable PostgreSQL database, verify actual constraint names through PostgreSQL metadata, and execute the cross-tenant/same-tenant constraint matrix.

## Phase 5: User Story 3 — Retry, Rollback, and Financial Safety (P2)

- [ ] T026 Write failing tests for bounded retry after a retryable uniqueness collision, clean transaction restart, exhausted retry error, and no partially committed parent/child state.
- [ ] T027 Implement retry handling only at a transaction boundary that can discard the failed session state and request a fresh authoritative allocation; never continue on a failed transaction.
- [ ] T028 Add integration tests for repeated financial requests and posting/reversal flows, asserting at most one authoritative journal posting, balanced debit and credit, immutable posted history, and correct audit attribution.
- [ ] T029 Record caller-supplied `asset_code` validation and depreciation transaction-code length validation as deferred follow-up observations (out of scope for Feature 012 unless proven to block remediation).
- [ ] T030 Add regression tests proving `DocumentSession.session_code`, organization slug, WhatsApp sender phone, and other intentionally global identifiers retain their current semantics.

## Phase 6: Full Verification and Review Gate

- [ ] T031 Run focused unit and PostgreSQL integration tests, then the complete backend suite with `uv run pytest -q`.
- [ ] T032 Run `uv run ruff check src tests`, `uv run mypy src`, Alembic offline/online validation, dependency checks, and applicable frontend/build/safety gates from `AGENTS.md`.
- [ ] T033 Run a repository-wide search for remaining internal COUNT+1/max-suffix generators and classify every remaining match as migrated, intentionally non-business, or separately approved.
- [ ] T034 Review the diff for tenant isolation, transaction boundaries, protected storage exclusion, unchanged formats, no historical rewrites, and no accounting-rule changes.
- [ ] T035 Complete `analysis.md` with 100% FR-to-task traceability, zero Critical/High consistency findings, zero Constitution violations, and explicit PostgreSQL evidence results. Evidence is recorded, but baseline Alembic drift and the unimplemented retry contract remain blockers.
- [x] T036 Stop before implementation delivery if PostgreSQL behavior, migration safety, tenant scope, identifier format, or historical-data compatibility remains unverified; otherwise prepare a separate implementation checkpoint commit. The stop condition is active because baseline drift remains unresolved and no production implementation is authorized.

## Dependencies & Execution Graph

```text
T001 -> T002 -> T003/T004/T005
T003/T004/T005 -> T006/T007
T006/T007 -> T008/T009/T010/T011/T012
T012 -> T013/T014 -> T015/T016/T017/T018/T019
T012 -> T020/T021/T022/T023/T024/T025
T019/T025 -> T026/T027/T028/T029/T030
T028/T030 -> T031/T032/T033/T034/T035/T036
```

## Parallel Execution Opportunities [P]

- T003 and T004 can run in parallel only after T002 provisions the same disposable PostgreSQL baseline.
- T006 and T020 can be designed in parallel, but production implementation must not begin until the evidence gate passes.
- T013 and T015 can be written in parallel because they cover distinct generator groups; both depend on the allocator contract.
- T021/T022 migration work and T013/T015 service tests can proceed in separate worktrees after the foundational allocator contract is reviewed.
- T029 and T030 are independent regression suites and can run in parallel.

## Implementation Strategy

1. Establish real PostgreSQL evidence and capture the current behavior.
2. Implement and verify one allocator vertical slice with tests first.
3. Migrate the shared TRX path, then remaining year-coded generators.
4. Apply and verify the three composite uniqueness changes.
5. Add bounded retry and financial invariant regression tests.
6. Run all gates, perform independent review, and stop if any required evidence is unavailable.

No task authorizes renumbering historical records, changing accounting rules, touching protected storage, or silently changing identifier formats.
