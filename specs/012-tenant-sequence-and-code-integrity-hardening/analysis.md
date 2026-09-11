# Feature 012 Final Consistency Analysis

**Feature**: `012-tenant-sequence-and-code-integrity-hardening`
**Final checkpoint**: CP7
**Base main**: `1d502016c1133a09de8eedd1e4bf0858c501bd98`
**Feature implementation head before CP7 corrections**: `a148de03e9e9ca981b9031d8b8ab6f31858ab7a2`
**Final verification date**: 2026-09-11

## Final evidence boundary

All PostgreSQL evidence used here ran against disposable Docker container `pg_disposable_f012`, image `postgres:16`, local host port `127.0.0.1:54329`, database identity `feature012_disposable`, user `f012_test`, with credentials held only in process environment. No production database, production credentials, protected storage, or production financial data was used.

The verified Alembic revision is `023_historical_seq_bootstrap`. It is the sole head. `alembic check` reports `No new upgrade operations detected.` The historical bootstrap is intentionally online-only because its fail-closed parser must inspect historical PostgreSQL rows; offline SQL generation emits the schema migration chain without attempting data inspection or seeding.

## Requirement traceability matrix

| Requirement | Production implementation | Migration / schema | Authoritative test(s) | Status |
|---|---|---|---|---|
| FR-001 inventory and route every internal generator | `backend/src/services/tenant_sequence_allocator.py`; migrated generators in `transaction_service.py`, `reversal_service.py`, `accounting_engine.py`, `project_service.py`, `document_service.py`, `payable_service.py`, `receivable_service.py`, `money_movement_service.py` | `022_tenant_sequence_and_scoped_uniqueness.py` creates allocator table | `test_migrated_generators_postgresql.py`; `test_feature_012_cp6_postgresql.py` | TRACEABLE |
| FR-002 atomic year-scoped namespaces | `tenant_sequence_allocator.allocate_next()` and all nine year namespace call sites | `tenant_sequences` unique `(organization_id, namespace, scope_key)` | `test_tenant_sequence_allocator_postgresql.py`; `test_tenant_sequence_postgresql.py`; CP6 namespace concurrency tests | TRACEABLE |
| FR-003 atomic non-year SET namespace | `MoneyMovementService._generate_settlement_code()` uses `scope_key="GLOBAL"` | Non-null `scope_key` in `tenant_sequences`; schema foundation in revision 022 | allocator SET isolation/concurrency tests; CP6 SET concurrency test | TRACEABLE |
| FR-004 shared normal/reversal TRX namespace | `TransactionService.generate_transaction_code()` and `ReversalService.generate_reversal_code()` both allocate `TRX` | allocator scope key is shared by namespace/year | `test_tenant_sequence_postgresql.py::test_normal_and_reversal_paths_share_transaction_namespace`; CP6 mixed normal/reversal test | TRACEABLE |
| FR-005 preserve formats, API compatibility, history | Existing prefixes/padding retained at generator call sites; no historical-row updates | 022/023 migrations perform no business-code rewrites | `test_migrated_generators_postgresql.py`; historical bootstrap continuity tests | TRACEABLE |
| FR-006 tenant isolation | Organization ID is validated and part of every allocator key; service reads retain organization predicates; retry closures capture tenant-safe scalars | FK and composite uniqueness include `organization_id` | allocator tenant isolation; generator tenant isolation; constraint cross-tenant tests; full backend suite | TRACEABLE |
| FR-007 change only three confirmed global mismatches | Model constraints changed only for movement, settlement, and asset codes | `022_tenant_sequence_and_scoped_uniqueness.py` replaces exactly the three approved constraints | `test_tenant_code_constraints_postgresql.py`; `test_tenant_code_migration_postgresql.py` | TRACEABLE |
| FR-008 same-tenant duplicate rejection | Database remains the defense-in-depth authority | Composite unique constraints in revision 022 | movement, settlement, and asset same-tenant rejection tests | TRACEABLE |
| FR-009 one transaction/no partial records | Allocator does not commit; API write paths use `run_in_clean_transaction`; document storage is deleted on persistence failure | Counter and business writes share caller transaction | rollback tests in allocator, tenant sequence, CP6, and transaction recovery suites; document file safety regression | TRACEABLE |
| FR-010 bounded clean retry/no duplicate posting | `backend/src/services/transaction_retry.py`, hard bound of three, classified generated-code constraints only | N/A | `test_transaction_recovery_postgresql.py`; CP6 at-most-once posting/reversal tests | TRACEABLE |
| FR-011 accounting, immutability, reversal, audit invariants | Retry wrappers preserve existing posting services and actor propagation; no debit/credit rules changed | N/A | CP6 financial graph retry test; posting/reversal tests; complete backend suite | TRACEABLE |
| FR-012 PostgreSQL-specific verification | PostgreSQL support fixture requires explicit `FEATURE_012_TEST_DATABASE_URL` and rejects non-disposable targets | Alembic chain verified from base through 023 | 88-test Feature-012 PostgreSQL matrix; 522-test full backend run; live schema test | TRACEABLE |
| FR-013 preflight, fail-closed, non-destructive migration | Historical parser raises `HistoricalSequenceBootstrapError` for unresolved managed identifiers | Revision 022 preflights constraints/duplicates; revision 023 parses and seeds monotonically online | migration constraint tests; historical malformed-history, continuity, and monotonic-merge tests | TRACEABLE |
| FR-014 intentional global identifiers remain global | No changes to organization slug, sender phone, or document-session global semantics | No migration for these identifiers | `test_tenant_code_constraints_postgresql.py::test_document_session_code_remains_globally_unique`; full backend suite | TRACEABLE |
| FR-015 protected storage untouched | Feature diff excludes `backend/storage` and `backend/backend/storage` | N/A | repository safety check; git diff path review | TRACEABLE |
| FR-016 classify excluded/related identifiers | Historical migration explicitly recognizes approved out-of-scope prefixes; unrelated caller-supplied and UUID-derived identifiers were not migrated | No schema change for excluded identifiers | historical out-of-scope classification unit tests; global-identifier regression tests | TRACEABLE |
| FR-017 complete regression and concurrency matrix | Allocator, retry boundary, generator migration, and storage cleanup implementations | Alembic current/head/check and migration tests | 88-test Feature-012 PostgreSQL matrix; 522-test full backend suite; frontend gates | TRACEABLE |

**TOTAL REQUIREMENTS: 17**
**TRACEABLE: 17**
**UNTRACEABLE: 0**
**COVERAGE: 100%**

## CP1–CP6 invariant verification

- **CP1 — PostgreSQL reproduction/regression evidence: VERIFIED.** Tracked PostgreSQL regression suites execute against the disposable database; the final matrix has no skips.
- **CP2 — Database-backed TenantSequence allocator: VERIFIED.** PostgreSQL row-conflict allocation, tenant/year/namespace isolation, rollback, and engine persistence tests pass.
- **CP3 — Alembic foundation and historical bootstrap: VERIFIED.** Revisions 022 and 023 apply from the base chain; historical values are parsed, merged monotonically, and malformed managed history fails closed.
- **CP4 — Approved generators migrated: VERIFIED.** TRX, JE, PRJ, DOC, INV, BIL, ADV, REL, MM, and SET are covered by migrated-generator and CP6 PostgreSQL tests with existing formats.
- **CP5 — Clean retry and rollback recovery: VERIFIED.** Retry is bounded to three attempts, rolls back before retry, classifies only generated-code constraints, and leaves failed financial graphs uncommitted.
- **CP6 — End-to-end invariants: VERIFIED.** Concurrency, tenant/year/SET isolation, shared TRX, at-most-once effects, historical continuity, rollback integrity, and orphan prevention pass in PostgreSQL.

## Final gate results

- Feature-012 PostgreSQL matrix: **88 passed, 0 failed, 0 skipped**.
- Full backend suite with `FEATURE_012_TEST_DATABASE_URL`: **522 passed, 0 failed, 0 skipped**.
- PostgreSQL matrix includes normal/reversal/mixed TRX, JE/PRJ/DOC/INV/BIL/ADV/REL/MM/SET, tenant/year isolation, historical continuity, monotonic merge, malformed history fail-closed, rollback, clean retry, non-retryable failure, bounded retry, at-most-once transaction/journal/allocation/audit/money-movement/settlement effects, orphan prevention, and new-engine persistence.
- Alembic: current and sole head `023_historical_seq_bootstrap`; check clean; offline chain generated successfully from backend with 63,445 bytes and revision markers through 023.
- Python compile: passed.
- Dependency integrity: `pip check` passed; locked production `pip-audit==2.9.0` passed.
- Repository safety: passed; no tracked environment files, credentials, private keys, or obvious live-token signatures.
- Frontend: Vitest **26 files / 66 tests passed**; lint, typecheck, and build passed. Existing lint/Vite chunk/config warnings remain non-failing.
- Optional `ruff`, `mypy`, `bandit`, and `safety` executables are not available in the environment and are not configured repository gates.
- `git diff --check`: passed.

## Scope review

Feature 012 intentionally changed database-backed identifier allocation, three tenant-scoped uniqueness constraints, historical sequence bootstrap, transaction retry boundaries, affected API transaction ownership, and the associated unit/PostgreSQL regression suites. It did not change accounting mappings, tax policy, capitalization policy, depreciation policy, visible business-code formats, historical business records, unrelated API contracts, frontend behavior, or protected storage.

## Final consistency result

**Critical findings: 0. High findings: 0. Medium findings: 0. Low findings: 2 (deferred non-blocking observations).**

Independent delegated subagent review returned `APPROVED`:
- `F012-LOW-01`: outer-scope pre-validation inspection queries in payable/receivable endpoints before `run_in_clean_transaction` (inner transaction refetches with `populate_existing=True`; deferred refinement).
- `F012-LOW-02`: opening balance random hex suffix `OPB-` intentionally excluded from sequential allocator; recognized and skipped safely by migration 023.

The stale live-schema head assertion and the offline Alembic invocation were final-gate compatibility defects and were corrected narrowly: the test now asserts 023, and the online-only historical bootstrap explicitly no-ops during offline SQL rendering while preserving authoritative online validation/seeding. No unrelated product behavior was added.

**Spec Kit result: 100% requirement traceability, zero Critical/High/Medium consistency issues, zero Constitution violations.**
