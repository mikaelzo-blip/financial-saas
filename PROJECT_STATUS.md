# Project Status

- **Last reconciled**: 2026-09-10
- **Current origin/main baseline**: `1d502016c1133a09de8eedd1e4bf0858c501bd98` (exact commit verified from Git)
- **Active branch**: `hermes/012-tenant-sequence-and-code-integrity-hardening`
- **Active implementation feature**: Feature 012, tenant sequence and code integrity hardening
- **Feature 012 checkpoint**: CP2 tenant sequence model and PostgreSQL-backed transactional allocator implemented after CP1 regression evidence.
- **Feature 012 baseline**: Alembic head remains `021_fixed_asset_enhancements`; no Feature-012 migration exists. `alembic check` reports the intentional pending `tenant_sequences` table only, confirmed by a deterministic autogenerate inventory of one `add_table` difference and zero unrelated drift.
- **Feature 012 evidence**: FIN-P1-103 PostgreSQL race/collision and FIN-P1-104 tenant/global constraint mismatch remain verified. The production allocator uses atomic PostgreSQL `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING` keyed by non-null `(organization_id, namespace, scope_key)` and never commits internally.
- **Feature 012 implementation state**: CP2 allocator/model tests pass for first and sequential allocation, N=50 concurrent first-row bootstrap, tenant/namespace/year isolation, explicit `SET|GLOBAL`, rollback, and new-engine continuation. CP1 remains 8 passing baseline/safe-path tests and 16 expected-red legacy generator/constraint tests, with zero unexpected failures.
- **Feature 012 blockers**: None for CP2. Legacy generator migration, Feature-012 migration/constraint changes, and clean transaction retry remain later checkpoints.
- **Feature 012 CP2 scope**: `TenantSequence`, model registration, the integer allocator, and focused unit/PostgreSQL tests only. No legacy generator, accounting, existing uniqueness constraint, or Alembic revision changed.
- **Feature 011 status**: COMPLETE and merged through PR #54 using squash merge. No uncommitted production application code remains.
- **Protected data**: `backend/storage` and `backend/backend/storage` remain untouched. No `.env`, credentials, temporary logs, caches, or codebase-memory artifacts are part of Feature 012.
- **Next action**: Stop after CP2. CP3 may begin only as a separate checkpoint migrating approved legacy business-code generators to the allocator.
