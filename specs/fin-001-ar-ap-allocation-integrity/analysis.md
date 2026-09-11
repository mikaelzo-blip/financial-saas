# FIN-001 Design Consistency Analysis

**Feature**: FIN-001 — Serialize AR/AP Allocations and Enforce Source-Balance Integrity
**Checkpoint**: CP4 — Full verification, CI PostgreSQL gate, traceability, and delivery readiness
**Baseline**: `dd42bad8e8d44fe1bab726cc530fa12d7d9ad642`
**Branch**: `hermes/fin-001-ar-ap-concurrency`

## Evidence

A disposable PostgreSQL 16 harness proved the remediation across four discrete checkpoints:
1. **CP1**: Strict expected RED service tests reproduced concurrent over-allocation under independent sessions/transactions (two 60.00 allocations committing 120.00 against 100.00 balance). Endpoint characterization proved Feature-012 sequence serialization.
2. **CP2**: Implemented authoritative pessimistic row locks (`SELECT ... FOR UPDATE`), payment locking before source locking, canonical `(organization_id, UUID ascending)` lock order, and fresh SQL aggregate calculations (`_calculate_invoice_payment_allocated_amount`, `_calculate_bill_paid_amount`, `_calculate_payment_allocated_amount`). All CP1 RED tests turned green; N=50 and reversed-order deadlock tests passed.
3. **CP3**: Implemented `run_in_clean_transaction` with explicit SQLSTATE classification (`40001`, `40P01`, and approved `55P03`), exponential jittered backoff, session rollback and expunge before retry, and bounded exhaustion raising `TransactionContentionError` (HTTP 409). 15 PostgreSQL scenarios and 7 unit tests passed green.
4. **CP4**: Configured dedicated `postgres:16` service container in `.github/workflows/quality-gates.yml` with fail-closed prerequisites, online Alembic migration check, single-head check (`023_historical_seq_bootstrap`), zero-drift verification (`alembic check`), and mandatory execution of all 33 FIN-001 PostgreSQL tests. Full backend (553 passed, 2 pre-existing skips explained) and frontend test/lint/typecheck/build suites passed clean.

## Requirement Coverage

| Requirement | Design location | Verification | Result |
|---|---|---|---|
| R01 (AR source protection) | spec, contract, receivable_service.py | `test_fin001_ar_ap_concurrency_postgresql.py::test_ar_service_race_*`, `test_scenario_n_n50_*` | Verified |
| R02 (AP source protection) | spec, contract, payable_service.py | `test_fin001_ar_ap_concurrency_postgresql.py::test_ap_service_race_*`, `test_scenario_n_n50_*` | Verified |
| R03 (Source locks in transaction) | contract, receivable_service.py, payable_service.py | `test_tenant_isolation_and_identity_map_aggregate_characterization` | Verified |
| R04 (Tenant isolation) | spec, contract, tasks | `test_tenant_isolation_concurrent_locks_do_not_block_different_tenants`, `test_scenario_k_*` | Verified |
| R05 (Deterministic multi-source order) | spec, contract, data-model | `test_multi_source_reversed_order_canonical_locking_prevents_deadlock`, `test_duplicate_source_ids_*` | Verified |
| R06 (Full rollback on failure) | spec, transaction_retry.py | `test_scenario_d_non_retryable_*`, `test_scenario_e_retry_exhaustion_*` | Verified |
| R07 (At-most-once retry effects) | spec, transaction_retry.py | `test_scenario_a_sqlstate_40001_*`, `test_scenario_b_sqlstate_40p01_*`, `test_scenario_h_*`, `test_scenario_i_*` | Verified |
| R08 (Sequential compatibility) | spec, tasks | `test_customer_payment_uat.py`, `test_vendor_payment_safety.py`, `test_scenario_o_*`, `test_scenario_g_*` | Verified |
| R09 (Accounting policy unchanged) | spec, plan, checklist | Diff review + `test_financial_integrity.py`, `test_posting_flow.py`, `test_reversal_flow.py` | Verified |
| R10 (Historical records unchanged) | spec, data-model | Zero migrations created, `alembic heads`, `alembic check` clean at `023_historical_seq_bootstrap` | Verified |
| R11 (PostgreSQL evidence mandatory) | spec, quickstart, fin001_postgresql_support.py | `require_fin001_postgres_url` fails closed on SQLite / missing URL; 33 PG16 tests executed | Verified |
| R12 (CI fails closed) | spec, quality-gates.yml | Dedicated `postgres:16` service container, fail-closed URL/PG16 check, explicit FIN-001 test group | Verified |
| R13 (Endpoint characterization) | spec, research, plan | `test_customer_payment_endpoint_characterizes_*`, `test_vendor_payment_endpoint_characterizes_*` | Verified |
| R14 (No incidental-correctness reliance) | spec, plan, contract | Authoritative service-level locking & SQL aggregates verified independently of endpoint serialization | Verified |

**TOTAL REQUIREMENTS: 14**
**TRACEABLE: 14**
**COVERAGE: 100%**

## Independent Review Resolution

| Finding | Severity | Resolution | Blocking state |
|---|---|---|---|
| ORM identity-map relationship cache can make post-lock balance stale | High | Implemented explicit post-lock SQL aggregates (`_calculate_invoice_payment_allocated_amount`, `_calculate_bill_paid_amount`, `_calculate_payment_allocated_amount`). | Resolved |
| Retry helper catches only `IntegrityError` | High | Extended `transaction_retry.py` to catch `DBAPIError`, `OperationalError`, and `asyncpg.PostgresError`; classified `40001`, `40P01`, and approved `55P03`. | Resolved |
| Service-only race tests miss route orchestration | High | Added real concurrent HTTP endpoint characterization tests alongside service barrier tests. | Resolved |
| CI can silently skip PostgreSQL tests | High | Added dedicated `postgres:16` service container to `.github/workflows/quality-gates.yml`, explicit URL check, online migration check, and mandatory test execution step. | Resolved |
| Bulk source lock query may not acquire locks in sort order | Medium | Iterated through canonically sorted UUIDs acquiring one single-row lock per source. | Resolved |
| Backoff/jitter unspecified | Medium | Implemented 50 ms exponential base, 200 ms cap, randomized jitter, and 3 total attempts in `calculate_retry_backoff`. | Resolved |
| N=50 may exhaust test pool | Medium | Configured pool size 20, max_overflow 30 (50 connections capacity). | Resolved |
| Retention release can race with collectible calculation | Medium | FIN-001 includes invoice locking for retention release while preserving retention accounting policy. | Resolved |
| Cross-path lock order between payment and retention release | Medium | If concurrent payment and retention release race on the same invoice and tenant sequence, PostgreSQL raises 40P01 (deadlock_detected), which is caught by `run_in_clean_transaction`, rolled back cleanly, expunged, and retried with jittered backoff up to 3 attempts with at-most-once financial effects. | Resolved |

## Constitution Check

- **PASS**: Derived AR/AP balances remain derived from source/allocation data; no independently maintained balance is introduced.
- **PASS**: Payment/accounting mappings, journal legs, debit/credit rules, transaction types, revenue recognition, and cash classification are unchanged.
- **PASS**: No historical allocation or posted record modified; zero schema migrations introduced.
- **PASS**: Tenant isolation enforced across payment, source, allocation, and retry paths.
- **PASS**: PostgreSQL 16 is the concurrency authority; no process-local lock or SQLite equivalence claim is used.
- **PASS**: No production database, protected storage, credential, external AI, paid resource, push, or merge action occurs without authorization.

## Design Decision

- **Concurrency policy**: Authoritative pessimistic row locks (`SELECT ... FOR UPDATE`) plus bounded clean PostgreSQL conflict retry.
- **Lock granularity**: One payment row and each targeted invoice/bill row only.
- **Lock order**: Payment first; coalesced source UUIDs in canonical ascending order, one `FOR UPDATE` lock query per source.
- **Post-lock authority**: Explicit SQL allocation aggregates, not ORM relationship collections.
- **Retry**: `40001`, `40P01`, and explicitly verified retry-safe `55P03`; three total attempts; rollback, session expunge, and jittered bounded backoff before retry.
- **Transaction owner**: `get_db` owns final request commit/rollback; `run_in_clean_transaction` owns failed-attempt cleanup/retry dispatch.
- **Migration**: Not required.

## Final Result

**Critical: 0**
**High: 0**
**Medium: 0**
**Low: 0**

CP1–CP4 are fully complete, verified against local and CI-configured PostgreSQL 16, and ready for PR creation and remote CI execution.
