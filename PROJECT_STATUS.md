# Project Status

- **Last reconciled**: 2026-09-12
- **Current origin/main baseline**: `dd42bad8e8d44fe1bab726cc530fa12d7d9ad642` (Feature 012 post-merge status reconciliation; Git verified)
- **Active branch**: `hermes/fin-001-ar-ap-concurrency`
- **Active feature**: FIN-001 — AR/AP concurrent payment over-allocation remediation. CP1 (reproduction/characterization), CP2 (source/payment locks & canonical ordering), and CP3 (clean retry, SQLSTATE classification, exhaustion handling) are COMPLETE and verified against PostgreSQL 16.
- **FIN-001 CP1 evidence**: PostgreSQL 16 strict expected RED tests reproduced two independent `60.00` AR and AP allocations committing against one `100.00` source (`120.00` committed). Real endpoint characterizations proved Feature-012 sequence serialization.
- **FIN-001 CP2 evidence**: Implemented authoritative parent payment/source locks, canonical UUID source-lock ordering, and fresh post-lock SQL aggregate validation. All 11 PostgreSQL integration tests in `test_fin001_ar_ap_concurrency_postgresql.py` pass green.
- **FIN-001 CP3 evidence**: Implemented `run_in_clean_transaction` with explicit SQLSTATE classification (`40001`, `40P01`, and approved `55P03`), exponential jittered backoff, clean rollback, session expunge, and bounded exhaustion raising `TransactionContentionError` (HTTP 409). 15 PostgreSQL integration scenarios and 7 unit tests pass green.
- **Feature 012 status**: COMPLETE and merged through PR #59 using squash merge; CP1-CP7 implementation, regression evidence, independent review, and delivery gates are verified.
- **Feature 012 migration state**: Alembic current and sole head are `023_historical_seq_bootstrap`; Feature 012 final evidence recorded `alembic check` clean.
- **Feature 012 PostgreSQL evidence**: Disposable PostgreSQL 16 matrix passed 88 tests with zero failures/skips; full backend suite passed 553 tests with zero failures/skips when `FIN_001_TEST_DATABASE_URL` was explicitly configured.
- **Feature 012 scope result**: Accounting mappings, tax/capitalization/depreciation policy, visible business-code formats, historical business records, unrelated API contracts, frontend behavior, and protected storage remained unchanged.
- **Feature 011 status**: COMPLETE and merged through PR #54 using squash merge.
- **Protected data**: `backend/storage` and `backend/backend/storage` remain untouched. No `.env`, credentials, temporary logs, caches, or codebase-memory artifacts are tracked.
- **Next action**: Begin FIN-001 CP4: full verification, GitHub Actions CI postgres:16 job, consistency analysis traceability, and delivery readiness.
