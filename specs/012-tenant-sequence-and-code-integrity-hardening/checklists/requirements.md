# Specification Quality Checklist: Tenant Sequence and Code Integrity Hardening

**Purpose**: Validate specification completeness and quality before proceeding to planning.

## Content Completeness

- [x] CHK001 User stories are prioritized and independently testable.
- [x] CHK002 Acceptance scenarios cover same-tenant concurrency, cross-tenant isolation, rollback, and compatibility.
- [x] CHK003 Edge cases identify year rollover, empty scopes, retries, caller-supplied identifiers, and unavailable PostgreSQL.

## Requirement Clarity

- [x] CHK004 Functional requirements use testable MUST language and measurable outcomes.
- [x] CHK005 Requirements distinguish static risk, confirmed schema mismatch, and unexecuted PostgreSQL reproduction.
- [x] CHK006 Requirements do not require an unapproved code-format or accounting-policy change.

## Consistency & Feasibility

- [x] CHK007 Scope is limited to FIN-P1-103, FIN-P1-104, and directly related identifier-integrity concerns.
- [x] CHK008 PostgreSQL is explicitly authoritative for locking, transaction, and migration semantics.
- [x] CHK009 Proposed migration is non-destructive and requires preflight validation.

## Tenancy & Accounting Invariants

- [x] CHK010 Tenant ownership is required for allocation, persistence, reads, retries, and errors.
- [x] CHK011 Double-entry equality, immutable posted history, reversal correction flow, and deterministic accounting are preserved.
- [x] CHK012 Protected document storage paths are explicitly excluded.

## Notes

- PostgreSQL-specific concurrency reproduction was environment-blocked at the original specification checkpoint, but the later disposable PostgreSQL evidence gate reproduced the defect and validated the counter design.
- The merged Alembic metadata prerequisite is present; the final baseline reaches `023_historical_seq_bootstrap` and `uv run alembic check` reports no new upgrade operations.
- The validated allocator is a tenant/year counter table with transactional row locking, explicit `scope_key="GLOBAL"` for tenant-global SET codes, and bounded retry as defense-in-depth. Production implementation and tracked regression tests are complete and green.
