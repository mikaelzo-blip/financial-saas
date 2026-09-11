# Tasks: Tenant Sequence and Code Integrity Hardening

**Input**: Design documents from `/specs/012-tenant-sequence-and-code-integrity-hardening/`

**Prerequisites**: `spec.md`, `research.md`, `plan.md`, `data-model.md`, `contracts/sequence-generator-interface.md`, and `quickstart.md`.

**Implementation boundary**: These tasks cover the completed Feature 012 implementation and CP7 final verification. CP7 adds no product behavior except narrowly scoped corrections proven necessary by final gates.

## Phase 1: Setup and Evidence Gate

- [x] T001 Confirm branch, clean worktree baseline, and current migration head in `PROJECT_STATUS.md`, Git, and PostgreSQL test configuration. The feature branch is based on current `origin/main`; CP1-CP6 implementation and tracked evidence are committed.
- [x] T002 Provision or connect to a disposable PostgreSQL database without committing credentials; verify `023_historical_seq_bootstrap` is the current Alembic head. Docker `postgres:16` evidence is verified on `127.0.0.1:54329`.
- [x] T003 Add and execute tracked PostgreSQL regression tests at `backend/tests/integration/test_tenant_sequence_postgresql.py` for same-tenant concurrent allocation, shared normal/reversal `TRX`, rollback, poisoned-session recovery, posting rollback, and empty-scope bootstrap. Final matrix passes.
- [x] T004 Add and execute tracked cross-tenant mismatch tests at `backend/tests/integration/test_tenant_code_constraints_postgresql.py` covering movement, settlement, and asset codes, same-tenant rejection, and globally unique `DocumentSession.session_code`. Final matrix passes.
- [x] T005 Run the existing live PostgreSQL baseline tests and record exact connection, migration-head, model-registration, and schema results. The chain reaches `023_historical_seq_bootstrap`, and `uv run alembic check` reports no new upgrade operations.

## Phase 2: Foundational Database-Backed Allocation

- [x] T006-T012 Implement and verify namespace rendering, tenant/year/SET scope validation, the `TenantSequence` model, conflict-safe database allocation, caller transaction ownership, bounded collision errors, rollback, and PostgreSQL allocator behavior. Unit and PostgreSQL tests pass.

## Phase 3: User Story 2 — Tenant-Scoped Composite Uniqueness (P1)

- [x] T020 Write failing model/migration tests proving that same-tenant duplicate movement, settlement, and asset codes are rejected while cross-tenant identical codes are accepted after migration.
- [x] T021 Add the Feature 012 forward Alembic revisions after current head `021_fixed_asset_enhancements`: `022_tenant_sequence_scope` creates `tenant_sequences` and converts the three mismatches; `023_historical_seq_bootstrap` seeds sequences monotonically from history.
- [x] T022 In migration 022, create `tenant_sequences` and its non-null unique `(organization_id, namespace, scope_key)` constraint, then create composite constraints before dropping global constraints for `money_movements.movement_code`, `settlements.settlement_code`, and `fixed_assets.asset_code`; do not modify data.
- [x] T023 Update `backend/src/models/money_movement.py` and `backend/src/models/fixed_asset.py` to remove column-level global uniqueness and declare matching `UniqueConstraint` definitions.
- [x] T024 Add migration tests for upgrade, downgrade, offline SQL generation, missing-constraint fail-closed behavior, duplicate-preflight fail-closed behavior, and historical-value preservation.
- [x] T025 Run the migration on a disposable PostgreSQL database, verify actual constraint names through PostgreSQL metadata, and execute the cross-tenant/same-tenant constraint matrix.

## Phase 4: User Story 1 — Race-Proof Core Generators (P1)

- [x] T013-T019 Migrate the shared TRX and all approved year-coded/SET generators to the allocator, preserve every format, verify direct callers and transaction ownership, and execute PostgreSQL concurrency coverage. Final generator matrix passes.

## Phase 5: User Story 3 — Retry, Rollback, and Financial Safety (P2)

- [x] T026-T030 Implement and verify bounded clean-transaction retry, exhausted/non-retryable failure handling, complete financial rollback, at-most-once posting/audit/money effects, and intentional global identifier semantics. Deferred asset/depreciation validation observations remain out of scope.

## Phase 6: Full Verification and Review Gate

- [x] T031 Run focused unit and PostgreSQL integration tests, then the complete backend suite with `uv run pytest -q`. Final results: 88 Feature-012 PostgreSQL tests and 522 backend tests passed; zero failed/skipped.
- [x] T032 Run compile, configured dependency, migration, frontend/build, repository-safety, and whitespace gates. Optional unavailable tools are recorded in `analysis.md`.
- [x] T033 Search remaining internal COUNT/MAX generators and classify the affected inventory; approved business generators use the allocator and non-business matches remain out of scope.
- [x] T034 Review the diff for tenant isolation, transaction boundaries, protected storage exclusion, unchanged formats, no historical rewrites, and no accounting-rule changes. No Critical/High/Medium findings remain.
- [x] T035 Complete `analysis.md` with 100% FR-to-test traceability, explicit final evidence, zero Critical/High/Medium consistency findings, and zero Constitution violations.
- [x] T036 Complete CP7 final verification and documentation reconciliation without starting another feature. CP7 corrections are committed separately after final review and local gates.

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
3. Apply and verify the three composite uniqueness changes and create the allocator foundation migration.
4. Migrate the shared TRX path, then remaining year-coded generators.
5. Add bounded retry and financial invariant regression tests.
6. Run all gates, perform independent review, and stop if any required evidence is unavailable.

No task authorizes renumbering historical records, changing accounting rules, touching protected storage, or silently changing identifier formats.
