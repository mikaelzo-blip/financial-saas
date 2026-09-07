import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.config import settings
from scripts.verify_accounting_baseline import verify_accounting_baseline


@pytest.mark.asyncio
async def test_live_accounting_baseline_safety():
    """Verify accounting safety baseline against live PostgreSQL."""
    try:
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL not reachable: {e}")

    await verify_accounting_baseline()
