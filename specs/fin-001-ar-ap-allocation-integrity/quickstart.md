# FIN-001 Verification Quickstart

## Safety Boundary

Use only a disposable local PostgreSQL database. Never use production credentials or financial data. FIN-001 planning and CP1 RED evidence do not create a migration or modify application schema.

## Prerequisites

- Run commands from `backend/` with the repository-managed environment (`uv run ...`).
- Set an explicit FIN-001 disposable PostgreSQL URL using `postgresql+asyncpg`, localhost/127.0.0.1, and a clearly test/disposable database name.
- Export the same target as `DATABASE_URL` when Alembic requires it; do not rely on a default application database.
- Apply the current Alembic chain and assert `023_historical_seq_bootstrap` before interpreting test results.

## Design-Phase Reproduction

The disposable, non-repository harness used in the design checkpoint is:

```text
C:/Users/Fikri/AppData/Local/Temp/fin001_repro.py
```

It uses two independent sessions and an `asyncio.Barrier(2)`. On the current unmodified baseline it produced `120.00` allocated against `100.00` for both AR and AP. This is a deliberately disposable evidence tool, not production or tracked test code.

## CP1 Expected-RED and Characterization Commands

The tracked CP1 suite uses strict expected failures for the AR/AP source-safety assertions. Expected `XFAIL` means PostgreSQL reproduced the approved current defect. Passing endpoint, tenant, ownership, input-order, and identity-map tests are characterizations, not a claim that allocation safety is already fixed.

Illustrative commands:

```bash
cd backend
unset FIN_001_TEST_DATABASE_URL
uv run pytest -q tests/integration/test_fin001_ar_ap_concurrency_postgresql.py
# Expected: prerequisite failure, never a skip or SQLite fallback.
```

Then run the disposable PostgreSQL suite:

```bash
cd backend
export FIN_001_TEST_DATABASE_URL='postgresql+asyncpg://.../fin001_disposable'
export DATABASE_URL="$FIN_001_TEST_DATABASE_URL"
uv run alembic upgrade head
uv run pytest -q tests/integration/test_fin001_ar_ap_concurrency_postgresql.py
```

Expected before CP2: AR/AP source-safety assertions report strict `XFAIL` because two `60.00` allocations can commit against one `100.00` source. Customer/vendor endpoint characterizations pass because Feature-012 transaction-code allocation serializes same-tenant requests upstream. Fixture, import, migration, event-loop, cleanup, or URL-validation failures are unexpected harness failures and must be repaired before classifying expected RED evidence.

## CP2–CP3 Green Tests

After locks and retry behavior are implemented:

```bash
uv run pytest -q tests/integration/test_fin001_ar_ap_concurrency_postgresql.py
uv run pytest -q tests/integration/test_transaction_recovery_postgresql.py
uv run pytest -q tests/integration/test_customer_payment_uat.py tests/integration/test_vendor_payment_safety.py
```

Required assertions include independent sessions/barriers, N=50 contention where meaningful, final source/payment totals, reversed-order no-deadlock completion, rollback cleanup, at-most-once effects, tenant rejection, and source/payment statuses.

## Final Local Gates

```bash
uv run pytest -q
uv run pip check
uv run alembic heads
uv run alembic check
uv run alembic upgrade head --sql > "$LOCALAPPDATA/Temp/fin001-migrations.sql"
git diff --check
bash .github/scripts/check-repository-safety.sh
git status --short --branch
```

Run configured frontend test/lint/type/build gates when the delivery checkpoint requires repository-wide verification. Do not claim PostgreSQL coverage if the dedicated FIN-001 gate skipped or selected SQLite.
