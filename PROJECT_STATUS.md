# Project Status

- **Last reconciled**: 2026-09-10
- **Current origin/main baseline**: `1d502016c1133a09de8eedd1e4bf0858c501bd98` (exact commit verified from Git)
- **Active branch**: `hermes/012-tenant-sequence-and-code-integrity-hardening`
- **Active implementation feature**: Feature 012, tenant sequence and code integrity hardening
- **Feature 012 checkpoint**: CP1 tracked PostgreSQL regression/evidence tests added after the preserved baseline evidence checkpoint.
- **Feature 012 baseline**: Alembic head `021_fixed_asset_enhancements`; merged metadata registration prerequisite present; `uv run alembic check` reports `No new upgrade operations detected.`
- **Feature 012 evidence**: FIN-P1-103 PostgreSQL race/collision and FIN-P1-104 tenant/global constraint mismatch remain verified from disposable PostgreSQL evidence. Counter design, tenant/year/SET scope, rollback, isolation, and restart behavior remain validated.
- **Feature 012 implementation state**: CP1 tracked PostgreSQL regression tests are present; no production implementation or Feature-012 migration has been added. The CP1 suite records 16 expected-red current defects and 8 passing baseline/safe-path tests against disposable PostgreSQL 16.
- **Feature 012 blockers**: None for CP1. Production allocator, migration, and clean transaction retry behavior remain later implementation checkpoints.
- **Feature 012 CP1 evidence**: `test_tenant_sequence_postgresql.py` uses independent async SQLAlchemy sessions and an `asyncio.Barrier` for N=20 candidate/create races; `test_tenant_code_constraints_postgresql.py` verifies the three tenant-local constraint mismatches and preserves global `DocumentSession.session_code` uniqueness. Existing live PostgreSQL schema tests pass 2/2 against migration head `021_fixed_asset_enhancements`.
- **Feature 011 status**: COMPLETE and merged through PR #54 using squash merge. No uncommitted production application code remains.
- **Protected data**: `backend/storage` and `backend/backend/storage` remain untouched. No `.env`, credentials, temporary logs, caches, or codebase-memory artifacts are part of Feature 012.
- **Next action**: Stop after CP1. CP2 may begin only as a separate checkpoint implementing the tenant sequence model and allocator.
