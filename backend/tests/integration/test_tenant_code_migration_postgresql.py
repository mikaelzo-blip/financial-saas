from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from tests.integration.f012_postgresql_support import assert_postgresql_migration_head

pytestmark = pytest.mark.postgresql


async def test_feature_012_migration_is_applied(
    pg_session_factory,
) -> None:
    async with pg_session_factory() as session:
        await assert_postgresql_migration_head(
            session,
            expected_head="023_historical_seq_bootstrap",
        )
        assert await session.scalar(
            text("SELECT to_regclass('public.tenant_sequences')")
        ) == "tenant_sequences"


@pytest.mark.parametrize(
    ("table_name", "constraint_name", "definition"),
    [
        (
            "money_movements",
            "uq_money_movements_org_code",
            "UNIQUE (organization_id, movement_code)",
        ),
        (
            "settlements",
            "uq_settlements_org_code",
            "UNIQUE (organization_id, settlement_code)",
        ),
        (
            "fixed_assets",
            "uq_fixed_assets_org_code",
            "UNIQUE (organization_id, asset_code)",
        ),
        (
            "document_sessions",
            "uq_document_sessions_session_code",
            "UNIQUE (session_code)",
        ),
    ],
)
async def test_feature_012_live_unique_constraints(
    pg_session_factory,
    table_name: str,
    constraint_name: str,
    definition: str,
) -> None:
    async with pg_session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = CAST(:table_name AS regclass)
                  AND conname = :constraint_name
                  AND contype = 'u'
                """
            ),
            {"table_name": f"public.{table_name}", "constraint_name": constraint_name},
        )
        assert result.scalar_one() == definition


async def test_feature_012_obsolete_global_constraints_are_absent(
    pg_session_factory,
) -> None:
    async with pg_session_factory() as session:
        result = await session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conname IN (
                    'uq_money_movements_movement_code',
                    'uq_settlements_settlement_code',
                    'uq_fixed_assets_asset_code'
                )
                """
            )
        )
        assert result.scalars().all() == []
