# Quickstart: Bank Reconciliation Integrity (RECON-001)

## 1. Environment & Baseline Verification

Ensure you are working from the repository root:
```bash
git branch --show-current
# Expected: hermes/recon-001-reconciliation-integrity

git status --short
# Expected: clean (or only active Spec Kit files)

git rev-parse HEAD
# Baseline commit: e3c33ec3432ecff81c64be02012eaf51b55c5269
```

---

## 2. Checkpoint Verification Recipes

### Checkpoint 1 (CP1): RED Reproduction Suite
Run the characterization tests (expected strict xfail):
```bash
cd backend
uv run pytest tests/security/test_recon_001_reconciliation_integrity.py -v
```

### Checkpoint 2 (CP2): Service Hardening
Run service-level unit tests after removing strict xfail:
```bash
cd backend
uv run pytest tests/security/test_recon_001_reconciliation_integrity.py -k "not concurrent and not migration" -v
uv run pytest tests/unit/test_bank_reconciliation_p2.py -v
```

### Checkpoint 3 (CP3): Database Constraints & Migrations
Run Alembic offline validation and PostgreSQL integration tests:
```bash
cd backend
# Offline SQL migration generation check
uv run alembic upgrade head --sql

# Run with PostgreSQL (when container or database service is provisioned)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/financial_saas_test" \
uv run pytest tests/integration/test_reconciliation_concurrency_pg.py -v
```

### Checkpoint 4 (CP4): Full Quality Gates
Run complete regression before PR creation:
```bash
# Backend Full Suite
cd backend
uv run pytest -q

# Code Hygiene
uv run python -m compileall src tests

# Frontend Gates
cd ../frontend
npm test -- --run
npm run lint
npm run build
```

---

## 3. Database Preflight Query Execution (Read-Only)

Inspect live database for historical duplicate or invalid reconciliation records:
```bash
cd backend
uv run python -c "
import asyncio
from src.core.database import async_session_factory
from sqlalchemy import text

async def check():
    async with async_session_factory() as s:
        # Check duplicate statement lines
        res = await s.execute(text('SELECT statement_line_id, count(*) FROM bank_reconciliations GROUP BY statement_line_id HAVING count(*) > 1'))
        print('Duplicate Statement Lines:', res.fetchall())
asyncio.run(check())
"
```
