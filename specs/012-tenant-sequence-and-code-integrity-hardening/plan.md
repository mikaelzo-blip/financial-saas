# Tenant Sequence and Code Integrity Hardening Implementation Plan

> **For agentic workers:** Read `spec.md`, `research.md`, and `data-model.md` before implementation. Execute each task with test-first verification and stop at any unresolved policy, migration-safety, or PostgreSQL-evidence gate.

**Goal:** Replace race-prone tenant-local business-code allocation with database-authoritative allocation and align the three confirmed global uniqueness mismatches with tenant ownership without changing existing formats or historical data.

**Architecture:** Add a small database-backed tenant sequence allocator keyed by organization, namespace, and an explicit year/non-year scope. Services request the next number inside the same transaction that creates the business record; database uniqueness constraints remain defense-in-depth. Add one non-destructive Alembic migration converting movement, settlement, and asset code uniqueness from global single-column constraints to tenant-composite constraints.

**Tech Stack:** Python >=3.11, FastAPI, SQLAlchemy 2 async, PostgreSQL 16+, Alembic, pytest/pytest-asyncio, SQLite only for non-concurrency unit tests.

**Spec:** `specs/012-tenant-sequence-and-code-integrity-hardening/spec.md`

## Global Constraints

- Preserve all existing generated formats and externally visible identifiers.
- Never renumber, regenerate, delete, or rewrite historical financial records.
- Use PostgreSQL as authority for MVCC, row locks, uniqueness, and migration behavior.
- Do not use an in-process Python lock as the authoritative allocator.
- Preserve tenant isolation, deterministic accounting, balanced journals, immutable posted history, and reversal correction flow.
- Leave `backend/storage` and `backend/backend/storage` untouched.
- Do not modify production code until the PostgreSQL evidence, migration safety, and current Alembic baseline gates pass. Those prerequisite gates are now verified; implementation begins at CP1 with tracked regression tests.

---

## Evidence and Scope Gate

The audit was originally performed against commit `538817cc87165835a962c2032c65589fdcbfe09f` and is preserved in the Feature 012 evidence commit. After refresh onto current `origin/main` commit `1d502016c1133a09de8eedd1e4bf0858c501bd98`:

- Reproduced PostgreSQL race risks remain confirmed in normal and reversal transaction, journal, project, document, invoice, bill, advance, retention-release, and money-movement/settlement generators.
- Confirmed tenant/global uniqueness mismatches remain limited to `movement_code`, `settlement_code`, and `asset_code`.
- Disposable PostgreSQL 16 evidence remains valid; the unmodified generators reproduced FIN-P1-103, and the counter design passed independent N=50 and failure/recovery probes.
- The Alembic chain reaches `021_fixed_asset_enhancements`, and the merged metadata prerequisite makes `uv run alembic check` clean. The baseline drift blocker is resolved.
- `DocumentSession.session_code` and UUID-derived technical identifiers remain recorded but excluded from this migration scope.
- Tracked PostgreSQL regression tests and production clean-transaction retry behavior are not yet implemented; they are explicit implementation checkpoints, not design blockers.

### Evidence gate record

- PostgreSQL method: Docker container `pg_disposable_f012`, image `postgres:16`, local-only `127.0.0.1:54329`; disposable database and credentials; no production data.
- Baseline: fresh Alembic upgrade applied all revisions through `021_fixed_asset_enhancements`; current database also reports that head.
- Live constraints: `uq_money_movements_movement_code`, `uq_settlements_settlement_code`, `uq_fixed_assets_asset_code`, and global `uq_document_sessions_session_code` verified.
- FIN-P1-103: reproduced with 50 concurrent candidate allocations and 50 concurrent transaction creates; normal/reversal shared `TRX` collision observed.
- Counter harness: atomic `INSERT ... ON CONFLICT ... RETURNING` passed 50 concurrent first-row allocations, tenant/year/SET scope isolation, rollback, failed-transaction recovery, and new-engine continuation.
- Migration preflight: zero current duplicate tenant/code tuples; transactional simulation proved cross-tenant same-code success and same-tenant rejection, with downgrade blocked once cross-tenant duplicates exist.
- Baseline verification: current merged metadata registration is complete, `021_fixed_asset_enhancements` is the current migration head, and `uv run alembic check` reports `No new upgrade operations detected.`
- Retry implementation checkpoint: the poisoned-session probe verified that PostgreSQL aborts the transaction after a unique violation and that rollback recovers the session; production retry logic is not implemented and must establish a fresh transaction/session boundary.

## Proposed File Structure

### Documentation

- `spec.md`: authoritative requirements, clarifications, user stories, edge cases, and success criteria.
- `research.md`: evidence boundary, generator/constraint inventory, solution comparison, and provisional architecture decision.
- `plan.md`: this implementation design and gates.
- `data-model.md`: counter-table schema, constraints, migration, and transaction semantics.
- `contracts/sequence-generator-interface.md`: internal allocator protocol and error contract.
- `quickstart.md`: PostgreSQL setup, reproduction, migration, and verification commands.
- `tasks.md`: dependency-ordered implementation checklist.
- `analysis.md`: final read-only traceability and consistency gate.

### Production source files proposed for implementation only after gates

- Create or modify the repository-native sequence allocation service under `backend/src/services/`.
- Add the tenant-sequence model under `backend/src/models/` and register it in `backend/src/models/__init__.py` if required by repository conventions.
- Modify the inventoried generator call sites in `transaction_service.py`, `reversal_service.py`, `accounting_engine.py`, `project_service.py`, `document_service.py`, `payable_service.py`, `receivable_service.py`, and `money_movement_service.py`.
- Modify `money_movement.py` and `fixed_asset.py` model constraints.
- Add exactly one forward Alembic revision after current head `021_fixed_asset_enhancements` only after live schema and constraint names are verified.
- Add focused unit and PostgreSQL integration tests under `backend/tests/unit/` and `backend/tests/integration/`.

## Constitution Check

| Principle / invariant | Gate | Plan alignment |
|---|---|---|
| Single Input | PASS | Allocation only assigns identifiers; it does not create a second financial event. |
| Double-entry accounting | PASS | Posting rules and journal legs remain unchanged. |
| Deterministic accounting | PASS | The allocator cannot choose accounts or classifications. |
| Duplicate prevention | EVIDENCE PASS / IMPLEMENTATION PENDING | PostgreSQL counter harness produced unique committed values under N=50; production allocator and bounded retry are not implemented yet. |
| Human review | PASS | No review or approval behavior changes. |
| Immutable posted records | PASS | Historical codes and posted rows are never rewritten. |
| Audit trail | PENDING IMPLEMENTATION | No production allocator or retry path has been changed; existing audit paths remain untouched. |
| Tenant isolation | PASS | Every counter key and affected uniqueness constraint includes organization ownership where the domain is tenant-local. |
| Transactional database authority | PASS | PostgreSQL is the authoritative allocator and migration database. |
| Financial invariants | EVIDENCE PASS / IMPLEMENTATION PENDING | Throwaway rollback probes showed no committed counter allocation after rollback; financial posting code remains unchanged. |
| Protected storage | PASS | Protected storage paths are excluded and must not be accessed. |

**Gate status:** PostgreSQL concurrency, constraint, preflight, first-row, rollback, counter-design, and current Alembic-baseline evidence is available. The prerequisite baseline is clean. Tracked PostgreSQL regression tests and the production poisoned-session retry contract remain implementation work.

## Implementation Checkpoints

### CP1 — Tracked PostgreSQL regression/evidence tests

Add and run the unmodified PostgreSQL reproduction tests for same-tenant allocation races and cross-tenant movement/settlement/asset constraint mismatches. Preserve the observed current failures as evidence, with no production implementation changes in this checkpoint. Add the internal contract from `contracts/sequence-generator-interface.md` to the test boundary.

### CP2 — Tenant sequence model and allocator

Implement the counter table and allocator with a non-null `current_value` and unique scope key `(organization_id, namespace, scope_key)` where `scope_key` is strictly non-null (`YYYY` for year-scoped namespaces, `"GLOBAL"` for tenant-global non-year `SET`), and atomic row lock/update inside the caller’s transaction. Keep sequence gaps on rollback acceptable; never reuse an issued committed code.

### CP3 — Migrate all affected generators

Update each inventoried generator to use one allocator namespace while preserving its exact prefix, year, and padding. Ensure reversal and normal transaction paths share `TRX`. Settlement generator `_generate_settlement_code` uses the `"GLOBAL"` scope key and preserves `SET-######`.

### CP4 — Feature 012 Alembic migration

After preflight duplicate checks and live constraint-name verification, add exactly one forward Alembic revision after `021_fixed_asset_enhancements`. It creates `tenant_sequences` and changes only the three confirmed mismatches to `(organization_id, code)` constraints. Update SQLAlchemy models to match. Verify upgrade and downgrade on a disposable PostgreSQL database; fail closed if expected constraints are absent or duplicate tuples exist.

### CP5 — Clean transaction retry and rollback handling

Implement bounded collision retry only at a transaction boundary that can discard the failed session state and request a fresh authoritative allocation. Never catch and continue on a poisoned transaction. Add exhausted-retry and no-partial-state coverage.

### CP6 — End-to-end and invariant verification

Run N=50 same-tenant creates per representative generator, cross-tenant identical-code scenarios, same-tenant duplicates, rollback, retries, year rollover, no-duplicate-posting, tenant ownership, format compatibility, migration chain, lint, type checks, dependency checks, and full tests. Review all direct callers before delivery. Caller-supplied `asset_code` validation and fixed-asset depreciation transaction-code length validation are recorded as deferred follow-up observations and kept out of scope.

### CP7 — Full verification, review, and delivery evidence

Complete requirement traceability, repository safety review, independent code review, and all applicable local and CI gates before delivery. Do not push or merge an implementation checkpoint without passing its required verification.

## Rollback Strategy

- Before migration: remove the feature branch or revert implementation commits; no historical data changes are permitted.
- Application rollback before migration: deploy the prior code only if no new counter rows or constraints are relied upon by it; counter rows may remain unused and must not be reset or repurposed.
- Migration rollback: use the tested Alembic downgrade only on a schema whose data still satisfies global uniqueness. Before downgrading, run a duplicate global-code preflight; abort downgrade if any cross-tenant duplicate exists. Never delete records to make downgrade pass.
- If composite constraints have enabled legitimate cross-tenant duplicates, rollback is blocked until an explicit non-destructive compatibility decision exists.

## Complexity Tracking

| Complexity | Why needed | Rejected simpler alternative |
|---|---|---|
| Counter table | Empty sequence scopes need a stable row to lock; existing-row `FOR UPDATE` cannot solve first allocation safely. | Locking existing business rows only is racy on empty scopes. |
| Bounded retry | A database constraint protects against unexpected legacy/manual collisions, but retry must use a clean transaction. | Unbounded retry can hang and hide data/infrastructure defects. |
| One migration for three mismatches | Keeps related tenant-scope corrections atomic and reviewable. | Separate ad hoc migrations increase partial-schema risk. |
