# FIN-001 Internal Allocation Concurrency Contract

## Scope

This contract governs internal AR/AP payment allocation services. It does not change public request/response schemas.

## Preconditions

- Caller supplies an authenticated `organization_id`, one payment transaction UUID, and one or more `(source UUID, Decimal amount)` pairs.
- Amounts are positive `Decimal` values.
- The operation uses the caller-owned request `AsyncSession` and does not commit independently.

## CP1 Evidence Boundary

CP1 does not implement this contract. Current AR/AP services remain concurrency-unsafe under independent PostgreSQL transactions, as executable strict expected RED tests demonstrate. Current same-tenant HTTP payment routes serialize upstream at Feature-012 `TRX` transaction-code allocation; that endpoint characteristic is neither this contract nor an allocation-integrity guarantee. CP2 must implement this contract at the authoritative allocation boundary even if upstream serialization remains.

## Required Algorithm

1. Coalesce duplicate source UUIDs by summing amounts.
2. Capture only immutable IDs/scalars for a retryable closure.
3. In the closure, lock the payment transaction scoped to `organization_id` using `SELECT ... FOR UPDATE`.
4. Sort unique source UUIDs by canonical UUID order and lock each source row scoped to `organization_id` with one `SELECT ... FOR UPDATE` per UUID in that exact order. A bulk `IN (...) ORDER BY` query is not sufficient to promise physical lock order.
5. Require one returned locked row per requested source; missing source is tenant-scoped not found.
6. Recompute payment allocation consumption and source outstanding balances after locks using explicit SQL `SUM(allocated_amount)` queries. Do not use cached ORM relationship collections as the authoritative aggregate.
7. Validate posted type, counterparty, status, payment limit, and source limit.
8. Add allocation rows, calculate source statuses under existing policy, and execute existing derived financial effects in the same transaction.
9. Flush; final commit remains with `get_db`.

## Error Semantics

| Condition | Result | Retry? |
|---|---|---|
| Source/payment not found for organization | Existing tenant-scoped not-found response | No |
| Cancelled/wrong counterparty/not posted/non-positive/insufficient balance | Existing `INVARIANT_VIOLATION` (422) | No |
| PostgreSQL `40001`, `40P01`, or explicitly verified retry-safe `55P03` before commit | Roll back full attempt, wait bounded exponential jittered backoff, then retry | Yes, up to 3 total attempts |
| Retry exhaustion | Controlled allocation-contention conflict (409), no database detail | No |
| Unknown DB error | Roll back and propagate existing error policy | No |

## At-Most-Once Boundary

The guarantee covers one logical operation retried internally before commit. It does not equate independently submitted HTTP requests or separate client retries. The implementation must never retry after a successful commit or outside the database transaction that contains the full financial-effect graph.

## Non-Goals

This contract does not authorize schema changes, aggregate triggers, client idempotency, changed accounting mappings, debit/credit changes, or historical record rewrites.
