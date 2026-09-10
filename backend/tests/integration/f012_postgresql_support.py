from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.models.organization import Organization

POSTGRES_URL_ENV = "FEATURE_012_TEST_DATABASE_URL"


def require_feature_012_postgres_url() -> str:
    """Return only an explicitly named local disposable PostgreSQL URL."""
    url = os.environ.get(POSTGRES_URL_ENV)
    if not url:
        pytest.skip(
            f"{POSTGRES_URL_ENV} is not set; CP1 requires disposable PostgreSQL "
            "and will not substitute SQLite."
        )

    parsed = urlsplit(url)
    database_name = (parsed.path or "").lstrip("/").lower()
    if parsed.scheme != "postgresql+asyncpg" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail(
            f"Refusing {POSTGRES_URL_ENV}: use a local postgresql+asyncpg URL "
            "for a disposable PostgreSQL test database."
        )
    if not any(token in database_name for token in ("test", "f012", "disposable")):
        pytest.fail(
            f"Refusing {POSTGRES_URL_ENV}: database name must identify a test, "
            "Feature-012, or disposable database."
        )
    return url


@pytest.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        require_feature_012_postgres_url(),
        echo=False,
        pool_size=20,
        max_overflow=30,
        pool_timeout=30,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT version()"))
    except SQLAlchemyError as exc:
        await engine.dispose()
        pytest.fail(f"Feature-012 disposable PostgreSQL prerequisite unavailable: {exc}")

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def pg_session_factory(
    pg_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture
async def test_organizations(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[tuple[UUID, UUID]]:
    organization_ids = (uuid4(), uuid4())
    async with pg_session_factory() as session, session.begin():
        session.add_all(
            [
                Organization(
                    id=organization_ids[0],
                    slug=f"f012-a-{organization_ids[0].hex[:12]}",
                    legal_name="Feature 012 Test Organization A",
                ),
                Organization(
                    id=organization_ids[1],
                    slug=f"f012-b-{organization_ids[1].hex[:12]}",
                    legal_name="Feature 012 Test Organization B",
                ),
            ]
        )

    try:
        yield organization_ids
    finally:
        async with pg_session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM organizations WHERE id IN (:org_a, :org_b)"),
                {"org_a": organization_ids[0], "org_b": organization_ids[1]},
            )


async def assert_postgresql_migration_head(
    session: AsyncSession,
    expected_head: str = "022_tenant_sequence_scope",
) -> None:
    result = await session.execute(text("SELECT version_num FROM alembic_version"))
    assert result.scalar_one() == expected_head
