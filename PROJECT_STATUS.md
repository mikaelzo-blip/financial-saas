# Project Status

- **Last reconciled**: 2026-09-11
- **Current origin/main baseline**: `dd42bad8e8d44fe1bab726cc530fa12d7d9ad642` (Feature 012 post-merge status reconciliation; Git verified)
- **Active branch**: `hermes/fin-001-ar-ap-concurrency`
- **Active feature**: FIN-001 — AR/AP concurrent payment over-allocation remediation. CP1 Spec Kit and executable PostgreSQL evidence are complete; CP2 production remediation has not started.
- **FIN-001 CP1 evidence**: PostgreSQL 16 strict expected RED tests reproduce two independent `60.00` AR and AP allocations committing against one `100.00` source, producing `120.00` authoritative SQL totals. Same-tenant real customer/vendor payment endpoint characterizations pass because Feature-012 `TRX` tenant-sequence allocation serializes requests before allocation-service entry. This incidental endpoint behavior is not the FIN-001 integrity fix. Independent read-only review found zero Critical, High, or Medium findings.
- **FIN-001 CP2 design**: Parent payment/source locks, canonical UUID source-lock ordering, post-lock SQL aggregate validation, and bounded PostgreSQL clean retry remain required at the authoritative allocation boundary. No migration, schema, accounting-policy, API schema, frontend, or historical-data change is approved.
- **Feature 012 status**: COMPLETE and merged through PR #59 using squash merge; CP1-CP7 implementation, regression evidence, independent review, and delivery gates are verified.
- **Feature 012 migration state**: Alembic current and sole head are `023_historical_seq_bootstrap`; Feature 012 final evidence recorded `alembic check` clean.
- **Feature 012 PostgreSQL evidence**: Disposable PostgreSQL 16 matrix passed 88 tests with zero failures/skips; full backend suite passed 522 tests with zero failures/skips when `FEATURE_012_TEST_DATABASE_URL` was explicitly configured.
- **Feature 012 scope result**: Accounting mappings, tax/capitalization/depreciation policy, visible business-code formats, historical business records, unrelated API contracts, frontend behavior, and protected storage remained unchanged.
- **Feature 011 status**: COMPLETE and merged through PR #54 using squash merge.
- **Protected data**: `backend/storage` and `backend/backend/storage` remain untouched. No `.env`, credentials, temporary logs, caches, or codebase-memory artifacts are tracked.
- **Next action**: Begin FIN-001 CP2 only: implement authoritative payment/source locking, canonical source ordering, and fresh post-lock SQL aggregate validation. Do not classify Feature-012 endpoint serialization as allocation-invariant safety.
