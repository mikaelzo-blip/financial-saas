# FIN-001 Implementation Plan

**Branch**: `hermes/fin-001-ar-ap-concurrency` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

## Summary

Prevent AR/AP payment allocations from exceeding a source balance under PostgreSQL concurrency. The smallest correct change locks the payment and authoritative source rows inside one request transaction, recalculates all allocation-derived limits after those locks, and retries only narrowly classified transient PostgreSQL transaction conflicts. No schema, migration, accounting, historical-data, API-request, or frontend change is planned.

## Technical Context

**Language/Version**: Python >=3.11
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async, asyncpg, pytest/pytest-asyncio
**Storage**: PostgreSQL is authoritative; SQLite only supports non-concurrency unit coverage
**Testing**: pytest with disposable PostgreSQL 16 integration database and explicit test URL
**Target Platform**: Backend web service and GitHub Actions
**Project Type**: FastAPI backend with React frontend unaffected
**Performance Goal**: Serialize only requests sharing a payment or source; unrelated tenant/source allocations remain concurrent
**Scope**: AR/AP payment allocation, transaction retry classification, PostgreSQL test support, narrow CI gate, and governed documentation

## Constitution Check

| Principle / invariant | Gate | Plan alignment |
|---|---|---|
| Single Input | PASS | One payment event remains one transaction; allocation derives AR/AP settlement. |
| Double-entry and deterministic accounting | PASS | Existing transaction types, accounting engine, mappings, and journal legs are untouched. |
| Cash movement is not expense/revenue | PASS | FIN-001 changes serialization only, not treatment. |
| Derived financial balances | PASS | Source balance continues to derive from allocations; locking protects the derivation. |
| Immutable posted records | PASS | No historical allocation or posted-record rewrite. |
| Audit trail | PASS | Retry rollback tests require no duplicate audit effects. |
| Tenant isolation | PASS | Every locked source and payment query retains organization scope. |
| Transactional database authority | PASS | PostgreSQL rows/locks are authoritative; no process-local lock. |
| Testability and verification | PASS | Barrier-synchronized independent-session PostgreSQL tests are mandatory. |
| Incremental implementation | PASS | Four verified checkpoints, with RED tests before production changes. |

No Constitution violation or complexity exception is approved.

## Design

### Authoritative operation boundary

The payment route must invoke one retryable operation that owns all mutable work:

```text
request session (get_db owns final commit/rollback)
  -> run_in_clean_transaction (roll back failed attempt; dispatch bounded retry)
       -> create payment transaction
       -> post through existing accounting engine
       -> lock payment row FOR UPDATE
       -> coalesce source IDs, lock source rows FOR UPDATE in canonical order
       -> reload/recompute allocation-derived totals after locks
       -> for AR retention release, lock the same invoice before changing released retention
       -> validate payment/source/counterparty/tenant/status limits
       -> add allocation rows and derive source statuses
       -> synchronize money movement / settlement
  -> get_db commits exactly once, otherwise rolls back all effects
```

Route-level source queries that decide eligibility must move into this boundary. Authentication, request-shape validation, and immutable scalar capture remain outside it. The operation closure must retain scalar organization ID, actor ID/role, request values, and source UUIDs only; ORM rows from before rollback must not be dereferenced on a retry.

### Lock protocol

1. Validate non-empty input and coalesce repeated `(source_id, amount)` entries in memory.
2. Select the payment transaction scoped by organization with `FOR UPDATE`; validate compatible posted payment and counterparty.
3. Sort unique source UUIDs by RFC UUID byte/string canonical order; acquire one `SELECT ... FOR UPDATE` source lock per UUID in that sequence. Do not use a bulk `IN (...) ORDER BY` query as proof of physical lock-acquisition order.
4. Verify every requested source was returned; otherwise fail closed as tenant-scoped not found.
5. Execute fresh SQL `SUM(allocated_amount)` queries after all relevant locks for payment consumption and each source balance. Never use an already-loaded relationship collection or identity-map snapshot as an authoritative aggregate.
6. Add all allocations, calculate each source status from the new authoritative total, synchronize existing financial effects, flush, and return.
7. Commit only through the existing request-session owner.

For a same-source race, the second transaction blocks at step 3, sees the first commit after lock acquisition, and rejects its now-excess allocation. For reversed multi-source requests, both try `A` then `B`; no session can hold `A` while waiting for `B` as another holds `B` while waiting for `A`.

### Retry protocol

- Reuse `run_in_clean_transaction` only after its catch boundary includes `IntegrityError`, `DBAPIError`, and `OperationalError`, with a classifier for wrapped PostgreSQL SQLSTATE.
- Preserve its maximum of three total attempts.
- Call `rollback()` before retry; wait a 50 ms exponential base delay, doubled and capped at 200 ms, with randomized jitter.
- Retry `40001`, `40P01`, and only an explicitly verified retry-safe `55P03` lock conflict/timeout.
- Do not retry invariant, authorization, tenant-not-found, client-validation, unknown database, or post-commit failures.
- If retry exhausts, translate to a controlled 409 conflict without exposing database internals.

### API compatibility

No request/response field change is planned. Sequential valid payments retain current behavior. Under true contention, an operation that becomes over-limit after waiting returns the existing domain invariant error; only transient database conflict exhaustion returns the new controlled conflict response.

## Source Structure

```text
backend/
├── src/
│   ├── api/v1/receivables.py       # move authoritative AR source checks inside operation
│   ├── api/v1/payables.py          # move authoritative AP source checks inside operation
│   ├── services/receivable_service.py
│   ├── services/payable_service.py
│   ├── services/transaction_retry.py
│   └── core/exceptions.py          # only if a dedicated contention exception is needed
└── tests/
    └── integration/
        ├── f012_postgresql_support.py or narrowly named FIN-001 support
        ├── test_fin001_ar_ap_concurrency_postgresql.py
        └── test_transaction_recovery_postgresql.py

.github/workflows/quality-gates.yml # narrowly add required FIN-001 PostgreSQL gate
specs/fin-001-ar-ap-allocation-integrity/
```

## Checkpoints

### CP1 — Spec, baseline, and PostgreSQL characterization evidence

Create executable PostgreSQL evidence without production changes. AR/AP service tests use two independent sessions/transactions and a source-read `asyncio.Barrier(2)` to demonstrate the current `120.00` allocation total from competing `60.00` requests against one `100.00` source. They remain strict expected RED regressions until CP2.

Real concurrent `POST /api/v1/customer-payments` and `POST /api/v1/vendor-payments` tests characterize Feature-012 upstream tenant-sequence serialization safely: hold the first request after transaction-code allocation, prove the second has not reached allocation, then release it and verify the normal `201`/`422` result and no failed-request graph. These passing route tests must not claim source-invariant safety. CP1 also records current client input order for multi-source allocation, tenant isolation, `get_db`/`run_in_clean_transaction` ownership, and stale ORM relationship versus fresh SQL aggregate behavior.

**Exit gate**: Tests use independent PostgreSQL sessions/barriers, migration head and PostgreSQL 16 are verified, AR/AP defects are tracked as strict expected RED, route behavior is characterized without production instrumentation, and the named FIN-001 target fails closed rather than substituting SQLite or skipping.

### CP2 — Transaction-scoped locks and deterministic ordering

Implement source/payment row locks and move authoritative validation inside the operation closure. Add canonical source ordering shared by AR/AP. Turn AR/AP race and reversed-order tests green.

**Exit gate**: PostgreSQL AR/AP race and multi-source deadlock tests pass; sequential AR/AP safety regressions remain green; no schema/migration/API/accounting changes.

### CP3 — Retry, rollback, and at-most-once integrity

Extend clean retry only for classified transient PostgreSQL conflicts, add controlled exhaustion response, and prove complete rollback/no duplicate financial effects.

**Exit gate**: Forced retry/rollback tests pass; failed attempts leave no financial graph; one successful logical operation has one posting/journal/allocation/movement/settlement/audit graph.

### CP4 — Full verification, independent review, and delivery readiness

Run focused and complete test suites, PostgreSQL matrix, migration/head checks, dependency/lint/type/build gates, repository safety, consistency analysis, and independent review. The required FIN-001 CI job must use a `postgres:16` service and fail if its explicit database prerequisite is absent or unreachable. Commit/push/PR only after all applicable gates pass; delivery is not authorized by this planning turn.

**Exit gate**: 100% traceability, zero Critical/High findings, required PostgreSQL CI fails closed, and all applicable local gates pass.

## Migration Decision

**MIGRATION REQUIRED: NO.** Parent-row locking uses existing invoice/bill/payment rows and requires no schema change. Do not add an Alembic revision in FIN-001.

## Risks and Guardrails

| Risk | Control |
|---|---|
| Deadlock from reversed source order | Coalesce then canonical UUID sort before `FOR UPDATE`. |
| Stale prevalidation | Make locked service reads authoritative; do not decide balances from route-level reads. |
| Retry duplicates side effects | Entire financial graph remains in one transaction; rollback before retry; test exact persisted counts. |
| Wrong transaction owner | Preserve `get_db` final commit ownership and avoid nested independent commits. |
| Cross-tenant source | Scope source and payment lock queries by organization and assert all requested IDs returned. |
| Silent CI skip | Dedicated FIN-001 PostgreSQL job provisions URL/database and fails missing/unreachable prerequisites. |

## Out of Scope

No migration, aggregate trigger, historical data rewrite, accounting-policy adjustment, frontend change, or client idempotency product change is authorized.
