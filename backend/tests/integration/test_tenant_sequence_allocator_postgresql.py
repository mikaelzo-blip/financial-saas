from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.models.tenant_sequence import TenantSequence
from src.services.tenant_sequence_allocator import allocate_next
from tests.integration.f012_postgresql_support import require_feature_012_postgres_url

pytestmark = pytest.mark.postgresql

CONCURRENCY = 50


@pytest.fixture
async def tenant_sequence_schema(pg_engine: AsyncEngine) -> AsyncIterator[None]:
    async with pg_engine.begin() as connection:
        await connection.run_sync(TenantSequence.__table__.create, checkfirst=True)
    try:
        yield
    finally:
        async with pg_engine.begin() as connection:
            await connection.run_sync(TenantSequence.__table__.drop, checkfirst=True)


async def allocate_committed(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    namespace: str,
    scope_key: str,
) -> int:
    async with session_factory() as session, session.begin():
        return await allocate_next(session, organization_id, namespace, scope_key)


async def test_first_allocation_returns_one(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations

    value = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )

    assert value == 1


async def test_sequential_allocations_increment_same_scope(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations

    values = [
        await allocate_committed(
            pg_session_factory, organization_id, "TRX", "2026"
        )
        for _ in range(3)
    ]

    assert values == [1, 2, 3]


async def test_concurrent_first_row_allocations_are_unique_and_contiguous(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    barrier = asyncio.Barrier(CONCURRENCY + 1)

    async def worker() -> int:
        async with pg_session_factory() as session, session.begin():
            await barrier.wait()
            return await allocate_next(session, organization_id, "TRX", "2026")

    tasks = [asyncio.create_task(worker()) for _ in range(CONCURRENCY)]
    await barrier.wait()
    values = await asyncio.gather(*tasks)

    assert len(values) == CONCURRENCY
    assert len(set(values)) == CONCURRENCY
    assert sorted(values) == list(range(1, CONCURRENCY + 1))

    async with pg_session_factory() as session:
        persisted = await session.scalar(
            select(TenantSequence.current_value).where(
                TenantSequence.organization_id == organization_id,
                TenantSequence.namespace == "TRX",
                TenantSequence.scope_key == "2026",
            )
        )
    assert persisted == CONCURRENCY


async def test_tenants_have_independent_counters(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    org_a, org_b = test_organizations

    first_a = await allocate_committed(pg_session_factory, org_a, "TRX", "2026")
    first_b = await allocate_committed(pg_session_factory, org_b, "TRX", "2026")

    assert (first_a, first_b) == (1, 1)


async def test_year_scopes_have_independent_counters(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations

    first_2026 = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )
    second_2026 = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )
    first_2027 = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2027"
    )

    assert (first_2026, second_2026, first_2027) == (1, 2, 1)


async def test_namespaces_have_independent_counters(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations

    first_trx = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )
    first_je = await allocate_committed(
        pg_session_factory, organization_id, "JE", "2026"
    )

    assert (first_trx, first_je) == (1, 1)


async def test_set_uses_explicit_tenant_global_scope(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    org_a, org_b = test_organizations

    values_a = [
        await allocate_committed(pg_session_factory, org_a, "SET", "GLOBAL")
        for _ in range(2)
    ]
    values_b = [
        await allocate_committed(pg_session_factory, org_b, "SET", "GLOBAL")
        for _ in range(2)
    ]

    assert values_a == [1, 2]
    assert values_b == [1, 2]


async def test_rolled_back_first_allocation_does_not_persist(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations

    async with pg_session_factory() as session:
        first = await allocate_next(session, organization_id, "TRX", "2026")
        assert first == 1
        await session.rollback()

    clean_value = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )

    assert clean_value == 1


async def test_rolled_back_increment_does_not_persist(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    committed = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )

    async with pg_session_factory() as session:
        rolled_back = await allocate_next(
            session, organization_id, "TRX", "2026"
        )
        assert rolled_back == 2
        await session.rollback()

    next_committed = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )

    assert (committed, next_committed) == (1, 2)


async def test_new_engine_continues_persisted_counter(
    tenant_sequence_schema: None,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    first = await allocate_committed(
        pg_session_factory, organization_id, "TRX", "2026"
    )

    restarted_engine = create_async_engine(require_feature_012_postgres_url())
    restarted_factory = async_sessionmaker(
        restarted_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        second = await allocate_committed(
            restarted_factory, organization_id, "TRX", "2026"
        )
    finally:
        await restarted_engine.dispose()

    assert (first, second) == (1, 2)
