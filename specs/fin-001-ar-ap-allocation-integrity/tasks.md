# Tasks: FIN-001 AR/AP Allocation Concurrency

**Input**: [spec.md](spec.md), [research.md](research.md), [plan.md](plan.md), [data-model.md](data-model.md), and [allocation concurrency contract](contracts/allocation-concurrency-contract.md).

**Boundary**: This task list is implementation planning only. It authorizes no production code, schema, migration, historical-data, accounting-policy, push, or merge action in the present design checkpoint.

## CP1 — Spec, Reproduction, and PostgreSQL Characterization Tests

- [x] T001 Reconcile `PROJECT_STATUS.md`, Git branch/worktree, `origin/main`, Alembic head, and the disposable PostgreSQL 16 harness before test completion.
- [x] T002 Verify dedicated FIN-001 PostgreSQL support accepts only an explicit disposable URL, validates the migrated sole head, and fails required FIN-001 execution closed when unavailable.
- [x] T003 Add AR two-session service barrier evidence: one `100.00` invoice and two independent `60.00` allocations. The active safety assertion is strict expected RED because current committed total is `120.00`.
- [x] T004 Add equivalent AP two-session PostgreSQL strict expected RED evidence: one `100.00` bill and two independent `60.00` allocations commit `120.00`.
- [x] T005 Add real concurrent customer/vendor HTTP characterizations. They observe Feature-012 tenant-sequence serialization before allocation, then verify one `201`, one `422`, and no matching failed-request journal/movement/settlement graph. They do not claim source safety.
- [x] T006 Add current reversed multi-source input-order characterization; current services preserve client order, so CP2 must coalesce and lock canonical UUID order.
- [x] T007 Add tenant-isolation, `get_db`/`run_in_clean_transaction` ownership, and stale identity-map versus fresh SQL aggregate characterizations.
- [x] T008 Run the FIN-001 suite on disposable PostgreSQL; preserve AR/AP source-safety assertions as strict expected RED rather than weakening, skipping, or treating endpoint serialization as the fix.

**CP1 gate**: Verified AR/AP service defect with independent PostgreSQL sessions/barriers; verified endpoint serialization as a separate characterization; no production implementation changed; named FIN-001 PostgreSQL execution fails closed rather than substituting SQLite or skipping. N=50 contention, source locks, canonical locking, retry policy, and full failed-attempt graph assertions remain CP2/CP3 work.

## CP2 — Source/Payment Locks and Deterministic Ordering

- [ ] T010 Implement shared canonical coalescing and UUID-ordering behavior in the AR/AP allocation paths without changing public API payloads.
- [ ] T011 Update `backend/src/services/receivable_service.py` to lock the posted payment and target invoices inside the authoritative operation, calculate post-lock payment/source totals with explicit SQL aggregates, then validate and derive status.
- [ ] T012 Update `backend/src/services/payable_service.py` symmetrically for payment and vendor-bill locks and explicit post-lock aggregates.
- [ ] T013 Update `CustomerARService.release_customer_retention()` to lock the invoice before changing `retention_released_amount`, sharing the source-lock protocol without changing retention accounting policy.
- [ ] T014 Update `backend/src/api/v1/receivables.py` and `backend/src/api/v1/payables.py` so authoritative source eligibility/balance checks occur only inside the locked operation boundary.
- [ ] T015 Turn the AR/AP service/HTTP race, N=50, multi-source ordering, tenant, payment-integrity, retention interaction, and sequential regression tests green.

**CP2 gate**: PostgreSQL source total never exceeds balance; no reversed-input deadlock; route/service behavior retains tenant and accounting semantics; no migration/API schema/accounting change.

## CP3 — Retry, Rollback, and At-Most-Once Effects

- [ ] T016 Extend `backend/src/services/transaction_retry.py` to catch `IntegrityError`, `DBAPIError`, and `OperationalError`; classify only PostgreSQL `40001`, `40P01`, and explicitly verified retry-safe `55P03`, preserve three total attempts, and apply 50 ms exponential capped (200 ms) jittered backoff after rollback.
- [ ] T017 Add a controlled allocation-contention exception/handler only if existing exception types cannot represent retry exhaustion without leaking DB details.
- [ ] T018 Keep payment creation, posting, allocation, status, money movement, settlement, and audit effects in the same retryable transaction closure; audit all direct AR/AP payment callers.
- [ ] T019 Turn forced transient conflict, rollback, exhausted retry, no-orphan, and at-most-once graph tests green.

**CP3 gate**: Failed attempts persist no transaction/journal/allocation/movement/settlement/audit graph; a successful retry commits exactly one graph; invariant failures are not retried.

## CP4 — Full Verification, Review, and Delivery Readiness

- [ ] T020 Provision a dedicated `postgres:16` GitHub Actions service for the required FIN-001 concurrency job; export its explicit test URL, run migrations/head validation, and assert missing/unreachable/unsafe prerequisites fail rather than skip.
- [ ] T021 Run focused FIN-001 PostgreSQL tests, existing Feature 012 PostgreSQL/recovery suites, sequential AR/AP tests, and complete backend suite.
- [ ] T022 Run dependency check, configured lint/type checks, frontend test/lint/type/build where applicable, Alembic head/check/offline chain, repository safety, `git diff --check`, and staged-diff review.
- [ ] T023 Complete `analysis.md` with 100% R01–R12 traceability and independent-review resolution; require zero Critical/High findings and zero Constitution violations.
- [ ] T024 Follow repository delivery workflow only after all gates: concise checkpoint commits, push `hermes/fin-001-ar-ap-concurrency`, PR, GitHub CI, and merge eligibility review. This is not authorized in the current design turn.

## Dependencies and Execution Order

```text
T001 -> T002 -> T003/T004/T005/T006/T007/T008 -> T009
T009 -> T010 -> T011/T012 -> T013/T014 -> T015
T015 -> T016/T017 -> T018 -> T019
T019 -> T020 -> T021/T022 -> T023 -> T024
```

- T003–T007 can be designed in parallel but execute against the same verified disposable migration baseline.
- T010 and T011 are symmetrical but touch distinct services; shared helpers/contract must be reviewed before parallel implementation.
- No task may introduce a schema migration or historical rewrite. If evidence makes either necessary, stop and request explicit scope approval.
