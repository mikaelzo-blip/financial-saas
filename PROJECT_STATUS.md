# Project Status

- **Last reconciled**: 2026-09-10
- **Current origin/main baseline**: `1d502016c1133a09de8eedd1e4bf0858c501bd98` (exact commit verified from Git)
- **Active branch**: `hermes/012-tenant-sequence-and-code-integrity-hardening`
- **Active implementation feature**: Feature 012, tenant sequence and code integrity hardening
- **Feature 012 checkpoint**: CP3 database foundation verified: Alembic 022 creates `tenant_sequences` and changes only the approved tenant-scoped business-code uniqueness constraints.
- **Feature 012 baseline**: Alembic head is `022_tenant_sequence_scope`, directly after `021_fixed_asset_enhancements`; `alembic check` reports no unexpected operations.
- **Feature 012 evidence**: CP3 upgrade from 021, fresh install, exact model/DDL agreement, live constraint-name verification, cross-tenant/same-tenant uniqueness semantics, offline SQL generation, downgrade success, safe downgrade abort on cross-tenant duplicates, and missing-constraint fail-closed behavior passed on disposable PostgreSQL 16.
- **Feature 012 implementation state**: CP2 allocator tests and CP3 migration/constraint tests pass. Legacy generator concurrency remains expected-red because caller migration is intentionally deferred to CP4; zero unexpected failures.
- **Feature 012 blockers**: None for CP3. Legacy generator migration and clean transaction retry remain later checkpoints.
- **Feature 012 CP3 scope**: One Alembic revision, `TenantSequence` model/DDL agreement, approved movement/settlement/asset composite uniqueness, migration regression tests, CP2 fixture preservation, and minimal Spec Kit checkpoint-order update. No legacy generator, accounting, API, or retry logic changed.
- **Feature 011 status**: COMPLETE and merged through PR #54 using squash merge.
- **Protected data**: `backend/storage` and `backend/backend/storage` remain untouched. No `.env`, credentials, temporary logs, caches, or codebase-memory artifacts are part of Feature 012.
- **Next action**: Stop after CP3. CP4 may begin only as a separate checkpoint migrating approved legacy business-code generators to the allocator.
