# Technical Research: FIN-001 AR/AP Allocation Concurrency

**Feature**: FIN-001 — Serialize AR/AP Allocations and Enforce Source-Balance Integrity
**Baseline examined**: `dd42bad8e8d44fe1bab726cc530fa12d7d9ad642`
**Date**: 2026-09-11

## Evidence Boundary

The current-main implementation was exercised only against the disposable local PostgreSQL 16 container already used for Feature 012. The disposable harness created isolated organization, counterparty, project, source, and posted payment records; it used two independent async SQLAlchemy sessions and `asyncio.Barrier(2)` before source return. No production connection, production data, schema DDL, migration, or tracked production/test source change was used.

Observed result:

```text
AR_RESULTS=[COMMITTED, COMMITTED]
AR_FINAL_ALLOCATION_TOTAL=120.00
AR_FINAL_ALLOCATION_ROWS=2
AP_RESULTS=[COMMITTED, COMMITTED]
AP_FINAL_ALLOCATION_TOTAL=120.00
AP_FINAL_ALLOCATION_ROWS=2
AR_OVERALLOCATED=True
AP_OVERALLOCATED=True
```

**FIN-001 service-invariant defect reproduced: YES.**

## CP1 Endpoint Characterization

The service reproduction must not be conflated with the real HTTP route boundary. The current same-tenant customer-payment and vendor-payment routes call Feature-012 transaction-code allocation during payment creation before calling the AR/AP allocation services. PostgreSQL serializes the competing `TRX` tenant-sequence update, so the second HTTP request cannot reach the allocation service while the first request is held at its allocation boundary.

CP1 bounded route characterization holds the first real request at the allocation service after its sequence allocation, starts the second same-tenant real request, and verifies that only the first can enter allocation. Once released, the route outcomes are one `201` and one existing invariant `422`; the failed request leaves no matching payment, journal, money movement, or settlement graph. This is legitimate upstream serialization, not source-balance correctness: direct callers and future route changes can still reach the reproduced service/database defect.

## Root Cause

At PostgreSQL `READ COMMITTED`, independent transactions can each read the same committed invoice/bill and loaded allocation collection. `CustomerARService.allocate_customer_payment()` and `VendorAPService.allocate_vendor_payment()` calculate balance and payment-consumption limits from that non-locked snapshot, insert their own allocation, set source status, and flush. They do not lock the source or payment row, and allocation-table rows cannot prevent an aggregate write skew by themselves.

The API routes deepen the stale-read window by reading and validating the invoice/bill outside the `run_in_clean_transaction()` operation:

- AR: `backend/src/api/v1/receivables.py:181-191`
- AP: `backend/src/api/v1/payables.py:125-137`

The service repeats validation inside the operation but still uses a non-locking source read:

- AR allocation: `backend/src/services/receivable_service.py:127-186`
- AP allocation: `backend/src/services/payable_service.py:108-167`

Existing allocation tables contain positive-amount checks and foreign keys, but no aggregate constraint can express `SUM(allocations) <= source balance` across child rows without schema-level mechanisms outside the minimal scope.

## Current Transaction Boundaries

### Request ownership

`get_db()` constructs one `AsyncSession` per request and owns final commit/rollback after the endpoint returns (`backend/src/core/database.py:63-73`). `run_in_clean_transaction()` flushes operations and rolls back only classified Feature-012 generated-code collisions; it does not commit and currently does not classify PostgreSQL serialization/deadlock conflicts (`backend/src/services/transaction_retry.py:71-110`).

### AR flow

```text
POST /customer-payments
  -> route reads invoice and checks outstanding outside retry boundary
  -> run_in_clean_transaction(db, record_payment)
       -> TransactionService.create_transaction(CUSTOMER_PAYMENT)
       -> AccountingEngine.post_transaction
       -> CustomerARService.allocate_customer_payment
            -> read payment, payment allocation aggregate, source + allocations
            -> validate source/payment/counterparty/outstanding
            -> insert allocation; update invoice status; flush
       -> MoneyMovementService.synchronize_payment_money_movement
  -> get_db commits entire request, or rolls back on exception
```

### AP flow

```text
POST /vendor-payments
  -> route reads bill and checks outstanding outside retry boundary
  -> run_in_clean_transaction(db, record_payment)
       -> TransactionService.create_transaction(PAY_VENDOR_BILL)
       -> AccountingEngine.post_transaction
       -> VendorAPService.allocate_vendor_payment
            -> read payment, payment allocation aggregate, source + allocations
            -> validate source/payment/counterparty/outstanding
            -> insert allocation; update bill status; flush
       -> MoneyMovementService.synchronize_payment_money_movement
  -> get_db commits entire request, or rolls back on exception
```

### Boundary findings

| Concern | Current finding | FIN-001 design treatment |
|---|---|---|
| Session owner | `get_db` owns final request commit/rollback | Preserve one request-level owner; retry helper performs rollback before retry only. |
| Source locking | No AR/AP source `FOR UPDATE` | Lock source rows before aggregate reads and validations. |
| Payment consumption | Payment aggregate read is not serialized | Lock payment transaction before payment-total validation. |
| Allocation locking | Existing child rows are read through relationship loading only | Source lock serializes source balance; no child-row lock is needed for the minimum design. |
| Route pre-check | Occurs outside clean transaction | Move authoritative source validation inside the locked operation; route may retain only syntax/auth checks. |
| Retry | Generated-code `IntegrityError` only | Extend with explicit PostgreSQL transient conflict classification and clean rollback. |
| Multi-source ordering | Input iteration order | Coalesce and lock sources in canonical UUID order. |

## Concurrency Policy Options

| Design | Correctness | Deadlock / retry behavior | Complexity | Migration | Decision |
|---|---|---|---|---|---|
| A. Source `SELECT ... FOR UPDATE` | Correct under `READ COMMITTED` when source balance is recalculated after the lock | Deterministic source order prevents same-set lock cycles; waiting request revalidates after lock acquisition | Small, matches SQLAlchemy/PostgreSQL patterns already in repo | No | Selected foundation |
| B. `SERIALIZABLE` plus retry | Correct if every affected operation retries `40001` correctly | More aborts under contention; broad isolation and retry closure audit needed | Larger behavioral surface | No | Rejected as the smallest change |
| C. Database aggregate enforcement | Strong defense in depth | Requires trigger/maintained totals or equivalent; more complex failure semantics | High | Yes | Rejected for minimum remediation |
| D. Hybrid row locks + bounded transient retry | Preserves row-lock correctness and handles residual deadlock/serialization/lock conflicts | Explicit rollback, exponential backoff, bounded retry | Moderate and compatible with Feature 012 retry helper | No | Selected |

## Selected Design

### Concurrency policy

**Pessimistic source-row locking plus bounded clean PostgreSQL conflict retry.** All authoritative balance and payment-total validation occurs inside the same request transaction that owns allocation, posting, status, money-movement, settlement, and audit effects.

### Lock granularity

1. Lock the payment `Transaction` row with `FOR UPDATE` before checking aggregate allocation consumption for that payment.
2. Coalesce source IDs, sort them canonically, and lock each target `CustomerInvoice` or `VendorBill` row with one ordered `SELECT ... FOR UPDATE` per source UUID. Do not rely on a bulk `IN (...) ORDER BY` query to determine physical lock-acquisition order.
3. After every relevant lock is acquired, calculate payment and source allocation totals with explicit SQL `SUM(allocated_amount)` aggregates scoped to the locked payment/source. Do not derive the authoritative post-lock balance from an already-loaded SQLAlchemy relationship collection or identity-map snapshot.
4. Do not lock the entire tenant, all allocation rows, or unrelated payments/sources.

This lock set covers the mutable authoritative parent rows whose state determines whether an insert is valid. A concurrent operation for the same source cannot pass its balance check until it reads the first committed operation and executes fresh aggregate queries after acquiring the lock.

### Lock order

- Lock the payment row first because each operation has one payment and the aggregate payment-cap check must serialize.
- Coalesce source amounts by source UUID.
- Lock sources in `(organization_id, UUID ascending)` order. The organization is constant for a request but included in the contract so AR/AP follow the same stable rule.
- Never lock sources in client input order. A request for `[B, A]` locks `A` then `B`, as does a request for `[A, B]`.

Payment-first does not create a cycle for the intended API flow because one request owns one payment. For potential multi-payment internal batching, FIN-001 does not authorize that operation; it must define a separate canonical payment order before implementation.

### Retry policy

- Retry only database-originated transient PostgreSQL failures attributable to transaction conflicts: SQLSTATE `40001` (serialization failure), `40P01` (deadlock detected), and `55P03` only when an explicitly configured lock conflict/timeout is proven retry-safe.
- Extend retry interception beyond `IntegrityError` to the SQLAlchemy `DBAPIError`/`OperationalError` family and inspect the wrapped PostgreSQL SQLSTATE. Unknown database failures re-raise immediately.
- Roll back before every retry and use a fresh attempt state; closures retain only immutable scalar IDs/values, never expired ORM instances.
- Use bounded exponential backoff with randomized jitter: a 50 ms base delay, doubled per retry, capped at 200 ms before jitter.
- Do not retry domain invariant violations, tenant not-found errors, validation errors, duplicate client submissions, or unknown database errors.
- **Maximum retries**: 3 total attempts, matching the existing Feature 012 hard bound unless targeted test evidence requires a separate approved policy.
- **Conflict response**: after exhaustion, return a controlled HTTP 409 conflict with a stable error code indicating temporary allocation contention; successful serialization followed by insufficient balance remains the existing 422 `INVARIANT_VIOLATION` response.

### Transaction owner

The FastAPI request `AsyncSession` remains the final commit/rollback owner through `get_db`. The `run_in_clean_transaction()` helper owns only retry-attempt cleanup and retry dispatch. The complete route operation—payment creation, posting, source locking/allocation, source status, money movement, settlement, and audit effects—must be inside the retryable closure.

## Accounting Integrity Invariants

### Source and payment invariants

- AR: `SUM(CustomerPaymentAllocation.allocated_amount for invoice) <= invoice.calculate_collectible_amount()`.
- AP: `SUM(VendorPaymentAllocation.allocated_amount for bill) <= bill.total_amount`.
- For either payment: `SUM(its allocations) <= payment.amount`.
- Every allocation is positive and belongs to a posted payment of the compatible transaction type and matching counterparty.
- Source status is derived from the post-allocation authoritative total and never transitions from a failed allocation attempt.

### Transactional integrity invariants

- A failed operation leaves no orphan allocation, payment transaction, journal, journal lines, money movement, settlement, settlement allocation, or audit row.
- Retried attempts leave no failed-attempt financial graph; one logical retry sequence commits at most one graph.
- Tenant predicates remain in every payment/source read. Cross-tenant source IDs fail as not found before allocation.
- Journal debit equals credit remains governed by the existing accounting engine; FIN-001 changes neither mapping nor debit/credit policy.
- Posted history remains immutable; FIN-001 applies only to new in-flight requests.

## Migration Decision

**MIGRATION REQUIRED: NO.**

The selected source-parent row-lock design requires no table, index, constraint, DDL, or data rewrite. Existing child allocation checks/FKs remain in place. The aggregate constraint alternative was rejected because it would require a migration and has not been shown necessary for correctness once authoritative source locks serialize validation.

## CI Audit

Feature 012 PostgreSQL support reads `FEATURE_012_TEST_DATABASE_URL` and calls `pytest.skip()` when it is absent (`backend/tests/integration/f012_postgresql_support.py:20-30`). The GitHub workflow runs the complete pytest suite without provisioning the variable or PostgreSQL (`.github/workflows/quality-gates.yml:53-54`). Therefore a FIN-001 PostgreSQL test reusing that helper could silently skip and leave the workflow green.

FIN-001 must add a narrowly scoped fail-closed gate: a dedicated GitHub Actions job must provision a `postgres:16` service, export the explicit FIN-001 disposable URL, apply/verify the expected Alembic head, and make the named FIN-001 suite fail when its URL is absent, unsafe, unreachable, or at the wrong head. The FIN-001 support helper must fail—not skip—when invoked by that required CI job without its prerequisite. This is in scope because R12 forbids silent omission. Broader modernization of existing optional live PostgreSQL suites remains out of scope.

## Follow-up Observations

- Database aggregate enforcement is a potential future defense-in-depth enhancement but is not required for FIN-001.
- Duplicate independent client submissions require idempotency policy; retry safety does not make two user requests one logical request.
- Existing settlement uniqueness semantics should be independently reviewed if implementation exposes an unrelated duplicate-settlement risk. It is not a precondition for source locking unless a FIN-001 test proves it blocks at-most-once behavior.
