# Quickstart & Test Verification Guide: Feature 012

This guide is for a disposable non-production PostgreSQL database. Do not place credentials in the repository or command history. The evidence gate used Docker `postgres:16` in `pg_disposable_f012`, exposed only on `127.0.0.1:54329`; credentials remained in an ignored environment file. The commands below are reproducible evidence commands, not production instructions.

## 1. Baseline and PostgreSQL availability

From the repository root:

```bash
git switch hermes/012-tenant-sequence-and-code-integrity-hardening
git status --short
cd backend
uv run alembic current
uv run pytest tests/integration/test_live_postgresql_schema.py -rs
```

The integration test must connect to a real PostgreSQL database and verify the current migration head (`021_fixed_asset_enhancements`). The refreshed Feature 012 branch reaches that head, and the merged metadata prerequisite makes `uv run alembic check` clean. Feature 012 implementation may proceed from this baseline after the tracked PostgreSQL regression-test checkpoint is added.

## 2. Concurrency reproduction

Use the repository’s PostgreSQL integration configuration and a disposable database. The implementation-stage test must use independent async PostgreSQL sessions, not the shared in-memory SQLite fixture.

Required scenarios:

```bash
cd backend
uv run pytest tests/integration/test_tenant_sequence_postgresql.py -v -rs
uv run pytest tests/integration/test_tenant_code_constraints_postgresql.py -v -rs
```

The tests must assert:

- N=50 same-tenant creates yield N committed unique codes for each representative namespace.
- Normal and reversal paths share `TRX-YYYY-######` without collision.
- Cross-tenant identical movement, settlement, and asset codes succeed after migration.
- Same-tenant duplicates remain rejected.
- Failed allocation/create attempts leave no partial business record, child record, journal, or posting.
- Retry paths use a clean transaction and do not duplicate a financial posting.
- Every resulting row has the initiating organization owner.

Before implementation, an unmodified reproduction should be added/run to document the current static-risk behavior. If PostgreSQL is unavailable, mark the test skipped/blocked; never substitute SQLite as concurrency evidence.

## 3. Migration validation

On a disposable database:

```bash
cd backend
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/unit/test_tenant_code_migration.py -v
uv run alembic downgrade -1
uv run alembic upgrade head
```

The migration test must inspect actual PostgreSQL constraint names, run tuple-duplicate preflights, verify upgrade/downgrade behavior, and prove that historical identifier values are unchanged. Downgrade must refuse to recreate global constraints if legitimate cross-tenant duplicates exist.

## 4. Full verification gates

```bash
cd backend
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```

Run the project’s applicable dependency, frontend, and safety checks from `AGENTS.md` before delivery. A green SQLite suite alone is insufficient for this feature.
