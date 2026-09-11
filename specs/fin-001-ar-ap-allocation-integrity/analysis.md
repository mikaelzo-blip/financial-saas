# FIN-001 Design Consistency Analysis

**Feature**: FIN-001 — Serialize AR/AP Allocations and Enforce Source-Balance Integrity
**Checkpoint**: CP1 — PostgreSQL defect reproduction and endpoint characterization only
**Baseline**: `dd42bad8e8d44fe1bab726cc530fa12d7d9ad642`
**Branch**: `hermes/fin-001-ar-ap-concurrency`

## Evidence

A disposable PostgreSQL 16 harness used separate async sessions, independent transactions, and a source-read `asyncio.Barrier(2)`. Current AR and AP services each permit two `60.00` allocations to commit against one `100.00` source, so the final authoritative SQL total is `120.00`. Both active safety assertions are strict expected RED regressions.

Real concurrent same-tenant customer and vendor payment endpoint tests are separate passing characterizations: Feature-012 `TRX` tenant-sequence allocation serializes the second request before it enters the allocation service. The tests hold the first request after transaction-code allocation, observe only one allocation-service entrant, release it, and verify `201`/`422` plus no matching failed-request journal, money movement, or settlement. This is not a source-invariant guarantee; CP2 source/payment locking and fresh SQL aggregate validation remain required.

## Requirement Coverage

| Requirement | Design location | Planned verification | Result |
|---|---|---|---|
| R01 | spec, research, plan, contract | AR independent-session PostgreSQL strict expected RED; CP2 turns it green | CP1 verified / CP2 pending |
| R02 | spec, research, plan, contract | AP independent-session PostgreSQL strict expected RED; CP2 turns it green | CP1 verified / CP2 pending |
| R03 | contract, research, plan | Lock-order/after-lock aggregate behavior tests | Traceable |
| R04 | spec, contract, tasks | Cross-tenant source tests with zero effects | Traceable |
| R05 | spec, contract, data model | Reversed-order no-deadlock PostgreSQL test | Traceable |
| R06 | spec, research, tasks | Forced rollback/no-orphan graph test | Traceable |
| R07 | spec, contract, plan | SQLSTATE retry/exhaustion at-most-once graph test | Traceable |
| R08 | spec, tasks | Existing sequential AR/AP safety suites | Traceable |
| R09 | spec, plan, checklist | Diff/accounting regression review | Traceable |
| R10 | spec, data model, checklist | No-migration/no-data-rewrite review | Traceable |
| R11 | spec, quickstart, tasks | Disposable PostgreSQL independent-session/barrier evidence | Traceable |
| R12 | spec, research, plan, tasks | Dedicated helper fail-closed URL/head validation; required CI job remains CP4 | CP1 helper verified / CP4 pending |
| R13 | spec, research, plan, tasks | Customer/vendor real HTTP sequence-serialization characterization | CP1 verified |
| R14 | spec, research, plan, contract | Service RED evidence remains active until source/payment locks plus fresh SQL aggregates exist | CP1 verified / CP2 pending |

**TOTAL REQUIREMENTS: 14**
**TRACEABLE: 14**
**COVERAGE: 100%**

## Independent Review Resolution

| Finding | Severity | Resolution | Blocking state |
|---|---|---|---|
| ORM identity-map relationship cache can make post-lock balance stale | High | Contract, plan, research, data model, and tasks require fresh post-lock SQL aggregates rather than relationship collections. | Resolved in design |
| Retry helper catches only `IntegrityError` | High | Plan/tasks require `IntegrityError`, `DBAPIError`, and `OperationalError` classification by wrapped SQLSTATE for `40001`, `40P01`, and approved `55P03`. | Resolved in design |
| Service-only race tests miss route orchestration | High | CP1 requires independent concurrent HTTP endpoint tests as well as service tests. | Resolved in design |
| CI can silently skip PostgreSQL tests | High | CP4 requires dedicated `postgres:16` CI service, explicit URL/head validation, and fail-not-skip test support. | Resolved in design |
| Bulk source lock query may not acquire locks in sort order | Medium | Contract/data model require one lock query per canonically sorted source UUID. | Resolved in design |
| Backoff/jitter unspecified | Medium | Retry design/task specifies 50 ms exponential base, cap 200 ms, randomized jitter, and three total attempts. | Resolved in design |
| N=50 may exhaust test pool | Medium | CP1 explicitly requires connection capacity above concurrency count. | Resolved in design |
| Retention release can race with collectible calculation | Medium | FIN-001 includes invoice locking for retention release while preserving retention accounting policy. | Resolved in design |

## Constitution Check

- **PASS**: Derived AR/AP balances remain derived from source/allocation data; no independently maintained balance is introduced.
- **PASS**: Payment/accounting mappings, journal legs, debit/credit rules, transaction types, revenue recognition, and cash classification are unchanged.
- **PASS**: CP1 changes no historical allocation or posted record; CP2 is required before new in-flight source operations are serialized.
- **PASS**: Current tenant-scoped allocation lookup is characterized; CP2 payment/source lock queries must retain organization predicates.
- **PASS**: PostgreSQL is the concurrency authority; no process-local lock or SQLite equivalence claim is used.
- **PASS**: No schema/migration, production database, protected storage, credential, external AI, paid resource, push, or merge action occurs in this checkpoint.

## Design Decision

- **Concurrency policy**: Payment/source pessimistic row locks plus bounded clean PostgreSQL conflict retry.
- **Lock granularity**: One payment row and each targeted invoice/bill row only.
- **Lock order**: Payment first; coalesced source UUIDs in canonical ascending order, one `FOR UPDATE` lock query per source.
- **Post-lock authority**: Explicit SQL allocation aggregates, not ORM relationship collections.
- **Retry**: `40001`, `40P01`, and explicitly verified retry-safe `55P03`; three total attempts; rollback and jittered bounded backoff before retry.
- **Transaction owner**: `get_db` owns final request commit/rollback; `run_in_clean_transaction` owns failed-attempt cleanup/retry dispatch.
- **Migration**: Not required.

## Final Design Result

**Critical: 0**
**High: 0 unresolved**
**Medium: 0 unresolved**
**Low: 0**

CP1 is complete: executable strict expected RED service regressions and passing endpoint characterizations are reconciled, and no production lock/retry code changed. CP2 remains justified and is the next permitted implementation checkpoint.
