from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.models.organization import Organization

POSTGRES_URL_ENV = "FIN_001_TEST_DATABASE_URL"
EXPECTED_ALEMBIC_HEAD = "023_historical_seq_bootstrap"


def require_fin001_postgres_url() -> str:
    """Return the explicitly configured local disposable FIN-001 database URL."""
    url = os.environ.get(POSTGRES_URL_ENV)
    if not url:
        pytest.fail(
            f"{POSTGRES_URL_ENV} is required for FIN-001 PostgreSQL tests; "
            "SQLite and skipped execution are not valid evidence."
        )

    parsed = urlsplit(url)
    database_name = (parsed.path or "").lstrip("/").lower()
    if parsed.scheme != "postgresql+asyncpg" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail(
            f"Refusing {POSTGRES_URL_ENV}: use a local postgresql+asyncpg URL "
            "for a disposable PostgreSQL database."
        )
    if not any(token in database_name for token in ("fin001", "test", "disposable")):
        pytest.fail(
            f"Refusing {POSTGRES_URL_ENV}: database name must explicitly identify "
            "a FIN-001, test, or disposable database."
        )
    return url


async def assert_fin001_postgresql_prerequisites(
    session: AsyncSession,
    *,
    expected_database: str,
) -> None:
    version_num = int(await session.scalar(text("SHOW server_version_num")) or 0)
    assert version_num >= 160000, "FIN-001 requires PostgreSQL 16-compatible evidence"
    assert await session.scalar(text("SELECT current_database()")) == expected_database
    revisions = list((await session.scalars(text("SELECT version_num FROM alembic_version"))).all())
    assert revisions == [EXPECTED_ALEMBIC_HEAD], (
        "FIN-001 database must contain exactly the repository Alembic head "
        f"{EXPECTED_ALEMBIC_HEAD}, got {revisions!r}"
    )


@pytest.fixture
async def fin001_pg_engine() -> AsyncIterator[AsyncEngine]:
    url = require_fin001_postgres_url()
    parsed = urlsplit(url)
    expected_database = (parsed.path or "").lstrip("/")
    engine = create_async_engine(
        url,
        echo=False,
        pool_size=20,
        max_overflow=30,
        pool_timeout=30,
    )
    try:
        async with engine.connect() as connection:
            await assert_fin001_postgresql_prerequisites(
                AsyncSession(bind=connection), expected_database=expected_database
            )
    except (AssertionError, SQLAlchemyError) as exc:
        await engine.dispose()
        pytest.fail(f"FIN-001 disposable PostgreSQL prerequisite is invalid: {exc}")

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def fin001_session_factory(
    fin001_pg_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(fin001_pg_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def fin001_organizations(
    fin001_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[UUID, UUID]]:
    organization_ids = (uuid4(), uuid4())
    async with fin001_session_factory() as session:
        session.add_all(
            [
                Organization(
                    id=organization_ids[0],
                    slug=f"fin001-a-{organization_ids[0].hex[:12]}",
                    legal_name="FIN-001 Test Organization A",
                ),
                Organization(
                    id=organization_ids[1],
                    slug=f"fin001-b-{organization_ids[1].hex[:12]}",
                    legal_name="FIN-001 Test Organization B",
                ),
            ]
        )
        await session.commit()

    try:
        yield organization_ids
    finally:
        async with fin001_session_factory() as session:
            parameters = {"org_a": organization_ids[0], "org_b": organization_ids[1]}
            organization_filter = "organization_id IN (:org_a, :org_b)"
            await session.execute(
                text(
                    "DELETE FROM settlement_allocations WHERE settlement_id IN "
                    "(SELECT id FROM settlements WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(
                text(
                    "DELETE FROM customer_payment_allocations WHERE "
                    "payment_transaction_id IN (SELECT id FROM transactions WHERE "
                    + organization_filter + ") OR invoice_id IN "
                    "(SELECT id FROM customer_invoices WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(
                text(
                    "DELETE FROM vendor_payment_allocations WHERE "
                    "payment_transaction_id IN (SELECT id FROM transactions WHERE "
                    + organization_filter + ") OR bill_id IN "
                    "(SELECT id FROM vendor_bills WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(text("DELETE FROM settlements WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM money_movements WHERE " + organization_filter), parameters)
            await session.execute(
                text(
                    "DELETE FROM journal_lines WHERE journal_entry_id IN "
                    "(SELECT id FROM journal_entries WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(text("DELETE FROM journal_entries WHERE " + organization_filter), parameters)
            await session.execute(
                text(
                    "DELETE FROM transaction_allocations WHERE transaction_id IN "
                    "(SELECT id FROM transactions WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(
                text(
                    "DELETE FROM transaction_review_flags WHERE transaction_id IN "
                    "(SELECT id FROM transactions WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(
                text(
                    "DELETE FROM transaction_document_links WHERE transaction_id IN "
                    "(SELECT id FROM transactions WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(text("DELETE FROM customer_retention_releases WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM vendor_advances WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM customer_invoices WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM vendor_bills WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM audit_logs WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM transactions WHERE " + organization_filter), parameters)
            await session.execute(
                text(
                    "DELETE FROM project_document_links WHERE project_id IN "
                    "(SELECT id FROM projects WHERE " + organization_filter + ")"
                ),
                parameters,
            )
            await session.execute(text("DELETE FROM projects WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM documents WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM users WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM counterparties WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM payment_accounts WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM chart_of_accounts WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM tenant_sequences WHERE " + organization_filter), parameters)
            await session.execute(text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"), parameters)
            await session.commit()
