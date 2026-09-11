from __future__ import annotations

import asyncio
import importlib.util
from functools import lru_cache
from pathlib import Path
import sys
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from src.models.organization import Organization
from src.services.tenant_sequence_allocator import allocate_next

pytestmark = pytest.mark.postgresql

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "023_seed_tenant_sequences_from_history.py"
)


@lru_cache(maxsize=1)
def load_migration():
    spec = importlib.util.spec_from_file_location("historical_sequence_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


async def insert_history(session: AsyncSession, org_a: UUID, org_b: UUID) -> None:
    counterparty_a = uuid4()
    counterparty_b = uuid4()
    project_a = uuid4()
    project_b = uuid4()
    transaction_a = uuid4()
    transaction_b = uuid4()
    transaction_org_b = uuid4()
    transaction_reversal = uuid4()
    account_a = uuid4()
    account_b = uuid4()
    payment_a = uuid4()
    payment_b = uuid4()
    movement_a = uuid4()
    movement_b = uuid4()
    movement_c = uuid4()
    invoice_a = uuid4()
    invoice_b = uuid4()

    session.add_all(
        [
            Organization(
                id=org_a,
                slug=f"hist-a-{org_a.hex[:12]}",
                legal_name="Historical Bootstrap A",
            ),
            Organization(
                id=org_b,
                slug=f"hist-b-{org_b.hex[:12]}",
                legal_name="Historical Bootstrap B",
            ),
        ]
    )
    await session.flush()

    await session.execute(
        text(
            """
            INSERT INTO counterparties (id, organization_id, name, is_customer, is_vendor,
                                        created_at, updated_at)
            VALUES (:id_a, :org_a, 'Customer A', true, false, now(), now()),
                   (:id_b, :org_b, 'Customer B', true, false, now(), now())
            """
        ),
        {"id_a": counterparty_a, "org_a": org_a, "id_b": counterparty_b, "org_b": org_b},
    )
    await session.execute(
        text(
            """
            INSERT INTO chart_of_accounts
                (id, organization_id, account_code, account_name, account_type,
                normal_balance, report_group, created_at)
                VALUES (:id_a, :org_a, '1101', 'Cash A', 'ASSET', 'DEBIT', 'CURRENT_ASSET', now()),
                  (:id_b, :org_b, '1101', 'Cash B', 'ASSET', 'DEBIT', 'CURRENT_ASSET', now())
            """
        ),
        {"id_a": account_a, "org_a": org_a, "id_b": account_b, "org_b": org_b},
    )
    await session.execute(
        text(
            """
            INSERT INTO payment_accounts
                (id, organization_id, coa_account_id, name, created_at)
            VALUES (:id_a, :org_a, :coa_a, 'Bank A', now()),
                   (:id_b, :org_b, :coa_b, 'Bank B', now())
            """
        ),
        {
            "id_a": payment_a,
            "org_a": org_a,
            "coa_a": account_a,
            "id_b": payment_b,
            "org_b": org_b,
            "coa_b": account_b,
        },
    )

    await session.execute(
        text(
            """
            INSERT INTO transactions
                (id, organization_id, transaction_code, transaction_type, transaction_date,
                 amount, currency, workflow_status, description, source_channel,
                 created_at, updated_at, retention_rate, retention_amount)
            VALUES
                (:trx_a, :org_a, 'TRX-2025-000019', 'DIRECT_PURCHASE', '2025-06-01',
                 100, 'IDR', 'STAGED', 'Historical A 2025', 'WEB', now(), now(), 0, 0),
                (:trx_b, :org_a, 'TRX-2026-000143', 'DIRECT_PURCHASE', '2026-06-01',
                 100, 'IDR', 'STAGED', 'Historical A 2026', 'WEB', now(), now(), 0, 0),
                (:trx_org_b, :org_b, 'TRX-2026-000007', 'DIRECT_PURCHASE', '2026-06-01',
                 100, 'IDR', 'STAGED', 'Historical B 2026', 'WEB', now(), now(), 0, 0),
                (:trx_rev, :org_a, 'TRX-2026-000147', 'REVERSAL', '2026-06-02',
                 100, 'IDR', 'STAGED', 'Historical reversal A 2026', 'WEB', now(), now(), 0, 0)
            """
        ),
        {
            "trx_a": transaction_a,
            "trx_b": transaction_b,
            "trx_org_b": transaction_org_b,
            "trx_rev": transaction_reversal,
            "org_a": org_a,
            "org_b": org_b,
        },
    )

    await session.execute(
        text(
            """
            INSERT INTO journal_entries
                (id, organization_id, entry_number, transaction_id, posting_date,
                 description, total_debit, total_credit, is_balanced, is_reversed, created_at)
            VALUES (:id_a, :org_a, 'JE-2026-000031', :trx_a, '2026-01-01',
                    'Historical journal A', 100, 100, true, false, now()),
                   (:id_b, :org_b, 'JE-2025-000004', :trx_b, '2025-01-01',
                    'Historical journal B', 100, 100, true, false, now())
            """
        ),
        {"id_a": uuid4(), "org_a": org_a, "trx_a": transaction_b,
         "id_b": uuid4(), "org_b": org_b, "trx_b": transaction_org_b},
    )

    await session.execute(
        text(
            """
            INSERT INTO projects
                (id, organization_id, project_code, project_name, customer_id,
                 original_contract_value, variation_order_value, revised_contract_value,
                 start_date, project_status, created_at, updated_at)
            VALUES (:id_a, :org_a, 'PRJ-2026-007', 'Project A', :cp_a, 100, 0, 100,
                    '2026-01-01', 'PLANNED', now(), now()),
                   (:id_b, :org_b, 'PRJ-2025-003', 'Project B', :cp_b, 100, 0, 100,
                    '2025-01-01', 'PLANNED', now(), now())
            """
        ),
        {"id_a": project_a, "org_a": org_a, "cp_a": counterparty_a,
         "id_b": project_b, "org_b": org_b, "cp_b": counterparty_b},
    )

    await session.execute(
        text(
            """
            INSERT INTO documents
                (id, organization_id, document_code, document_type, file_name, mime_type,
                 file_size_bytes, file_hash, storage_path, source_channel, source_metadata,
                 raw_extraction, created_at, processing_status, processing_attempts,
                 extracted_data, matching_results, confidence_scores, candidate_transaction,
                 review_flags, updated_at)
            VALUES (:id_a, :org_a, 'DOC-2026-000011', 'RECEIPT', 'a.pdf', 'application/pdf',
                    5, :hash_a, 'historical/a.pdf', 'WEB', '{}', '{}', now(), 'UPLOADED', 0,
                    '{}', '{}', '{}', '{}', '[]', now()),
                   (:id_b, :org_b, 'DOC-WA-ABC12345', 'RECEIPT', 'b.pdf', 'application/pdf',
                    5, :hash_b, 'historical/b.pdf', 'WHATSAPP', '{}', '{}', now(), 'UPLOADED', 0,
                    '{}', '{}', '{}', '{}', '[]', now())
            
            """
        ),
        {"id_a": uuid4(), "org_a": org_a, "hash_a": uuid4().hex,
         "id_b": uuid4(), "org_b": org_b, "hash_b": uuid4().hex},
    )

    await session.execute(
        text(
            """
            INSERT INTO customer_invoices
                (id, organization_id, invoice_code, customer_id, project_id, invoice_date,
                 due_date, total_amount, transaction_id, status, created_at, updated_at,
                 retention_rate, retention_amount, retention_released_amount, retention_paid_amount)
            VALUES (:id_a, :org_a, 'INV-2025-000300', :cp_a, :project_a, '2025-01-01',
                    '2025-02-01', 100, NULL, 'UNPAID', now(), now(), 0, 0, 0, 0),
                   (:id_b, :org_a, 'INV-2026-000025', :cp_a, :project_a, '2026-01-01',
                    '2026-02-01', 100, NULL, 'UNPAID', now(), now(), 0, 0, 0, 0)
            """
        ),
        {
            "id_a": invoice_a,
            "org_a": org_a,
            "cp_a": counterparty_a,
            "project_a": project_a,
            "id_b": invoice_b,
            "org_b": org_a,
            "cp_b": counterparty_a,
            "project_b": project_a,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO vendor_bills
                (id, organization_id, bill_code, vendor_id, bill_date, due_date,
                 total_amount, status, created_at, updated_at)
            VALUES (:id_a, :org_a, 'BIL-2026-000009', :cp_a, '2026-01-01', '2026-02-01',
                    100, 'UNPAID', now(), now())
            """
        ),
        {"id_a": uuid4(), "org_a": org_a, "cp_a": counterparty_a},
    )
    await session.execute(
        text(
            """
            INSERT INTO vendor_advances
                (id, organization_id, advance_code, vendor_id, advance_date,
                 original_amount, settled_amount, remaining_balance, transaction_id,
                 created_at, updated_at)
            VALUES (:id_a, :org_a, 'ADV-2025-000006', :cp_a, '2025-01-01',
                    100, 0, 100, :trx, now(), now())
            """
        ),
        {"id_a": uuid4(), "org_a": org_a, "cp_a": counterparty_a, "trx": transaction_a},
    )
    await session.execute(
        text(
            """
            INSERT INTO customer_retention_releases
                (id, organization_id, invoice_id, release_code, release_date,
                 release_amount, created_at, updated_at)
            VALUES (:id_a, :org_a, :invoice, 'REL-2026-000008', '2026-03-01',
                    10, now(), now())
            """
        ),
        {"id_a": uuid4(), "org_a": org_a, "invoice": invoice_a},
    )
    await session.execute(
        text(
            """
            INSERT INTO money_movements
                (id, organization_id, movement_code, payment_account_id, direction,
                 amount, movement_date, source_type, created_at, updated_at)
            VALUES (:id_a, :org_a, 'MM-2026-000125', :payment_a, 'IN', 100,
                    '2026-01-01', 'MANUAL', now(), now()),
                   (:id_b, :org_a, 'MM-2026-000126', :payment_a, 'IN', 100,
                    '2026-01-01', 'MANUAL', now(), now()),
                   (:id_c, :org_b, 'MM-2026-000125', :payment_b, 'IN', 100,
                    '2026-01-01', 'MANUAL', now(), now())
            """
        ),
        {
            "id_a": movement_a,
            "org_a": org_a,
            "payment_a": payment_a,
            "id_b": movement_b,
            "id_c": movement_c,
            "org_b": org_b,
            "payment_b": payment_b,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO settlements
                (id, organization_id, settlement_code, money_movement_id,
                 settlement_type, amount, created_at, updated_at)
            VALUES (:id_a, :org_a, 'SET-000019', :movement_a, 'DIRECT_EXPENSE', 100, now(), now()),
                   (:id_b, :org_a, 'SET-000027', :movement_b, 'DIRECT_EXPENSE', 100, now(), now()),
                   (:id_c, :org_b, 'SET-000003', :movement_c, 'DIRECT_EXPENSE', 100, now(), now())
            """
        ),
        {
            "id_a": uuid4(),
            "org_a": org_a,
            "movement_a": movement_a,
            "id_b": uuid4(),
            "movement_b": movement_b,
            "id_c": uuid4(),
            "org_b": org_b,
            "movement_c": movement_c,
        },
    )
    await session.commit()


async def invoke_bootstrap(connection: AsyncConnection) -> None:
    migration = load_migration()

    def run(sync_connection) -> None:
        context = MigrationContext.configure(sync_connection)
        with Operations.context(context):
            migration.upgrade()

    await connection.run_sync(run)


@pytest.mark.asyncio
async def test_bootstrap_seeds_history_and_allocator_continuity(
    pg_engine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_a, org_b = uuid4(), uuid4()
    async with pg_session_factory() as session:
        await insert_history(session, org_a, org_b)
    try:
        async with pg_engine.begin() as connection:
            await invoke_bootstrap(connection)

        async with pg_session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT organization_id, namespace, scope_key, current_value "
                        "FROM tenant_sequences ORDER BY organization_id, namespace, scope_key"
                    )
                )
            ).all()
            state = {(str(org), namespace, scope): value for org, namespace, scope, value in rows}

        assert state[(str(org_a), "TRX", "2025")] == 19
        assert state[(str(org_a), "TRX", "2026")] == 147
        assert state[(str(org_b), "TRX", "2026")] == 7
        assert state[(str(org_a), "SET", "GLOBAL")] == 27
        assert state[(str(org_b), "SET", "GLOBAL")] == 3
        assert state[(str(org_a), "INV", "2025")] == 300
        assert state[(str(org_a), "INV", "2026")] == 25
        assert state[(str(org_a), "DOC", "2026")] == 11
        assert state[(str(org_a), "JE", "2026")] == 31
        assert state[(str(org_b), "JE", "2025")] == 4
        assert state[(str(org_a), "PRJ", "2026")] == 7
        assert state[(str(org_b), "PRJ", "2025")] == 3
        assert state[(str(org_a), "BIL", "2026")] == 9
        assert state[(str(org_a), "ADV", "2025")] == 6
        assert state[(str(org_a), "REL", "2026")] == 8
        assert state[(str(org_a), "MM", "2026")] == 126
        assert state[(str(org_b), "MM", "2026")] == 125
        assert len(state) == 17

        async with pg_session_factory() as session:
            next_trx = await allocate_next(session, org_a, "TRX", "2026")
            await session.commit()
        assert next_trx == 148

        async def allocate_one() -> int:
            async with pg_session_factory() as session:
                value = await allocate_next(session, org_a, "TRX", "2026")
                await session.commit()
                return value

        values = await asyncio.gather(*(allocate_one() for _ in range(50)))
        assert sorted(values) == list(range(149, 199))

        async with pg_session_factory() as session:
            next_set = await allocate_next(session, org_a, "SET", "GLOBAL")
            empty_scope = await allocate_next(session, org_b, "INV", "2027")
            await session.commit()
        assert next_set == 28
        assert empty_scope == 1
    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(text("DELETE FROM tenant_sequences"))
            await connection.execute(text("DELETE FROM organizations WHERE id IN (:a, :b)"), {"a": org_a, "b": org_b})


@pytest.mark.asyncio
async def test_malformed_managed_history_aborts_without_partial_seed(
    pg_engine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            text("INSERT INTO organizations (id, slug, legal_name) VALUES (:id, :slug, 'Malformed History')"),
            {"id": org_id, "slug": f"malformed-{org_id.hex[:12]}"},
        )
        await session.execute(
            text(
                "INSERT INTO transactions "
                "(id, organization_id, transaction_code, transaction_type, transaction_date, amount, "
                "currency, workflow_status, description, source_channel, created_at, updated_at, "
                "retention_rate, retention_amount) "
                "VALUES (:id, :org, 'TRX-2026-NOTNUM', 'DIRECT_PURCHASE', '2026-01-01', 1, 'IDR', "
                "'STAGED', 'Malformed', 'WEB', now(), now(), 0, 0)"
            ),
            {"id": uuid4(), "org": org_id},
        )
        await session.commit()
    try:
        with pytest.raises(load_migration().HistoricalSequenceBootstrapError):
            async with pg_engine.begin() as connection:
                await invoke_bootstrap(connection)

        async with pg_session_factory() as session:
            assert await session.scalar(text("SELECT COUNT(*) FROM tenant_sequences")) == 0
            assert await session.scalar(
                text("SELECT transaction_code FROM transactions WHERE organization_id = :org"),
                {"org": org_id},
            ) == "TRX-2026-NOTNUM"
    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(text("DELETE FROM tenant_sequences"))
            await connection.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


@pytest.mark.asyncio
async def test_existing_sequence_state_merges_monotonically(
    pg_engine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            text("INSERT INTO organizations (id, slug, legal_name) VALUES (:id, :slug, 'Merge History')"),
            {"id": org_id, "slug": f"merge-{org_id.hex[:12]}"},
        )
        await session.execute(
            text(
                "INSERT INTO tenant_sequences "
                "(id, organization_id, namespace, scope_key, current_value) "
                "VALUES (:id, :org, 'TRX', '2026', 150)"
            ),
            {"id": uuid4(), "org": org_id},
        )
        await session.execute(
            text(
                "INSERT INTO transactions "
                "(id, organization_id, transaction_code, transaction_type, transaction_date, amount, "
                "currency, workflow_status, description, source_channel, created_at, updated_at, "
                "retention_rate, retention_amount) VALUES "
                "(:id, :org, 'TRX-2026-000143', 'DIRECT_PURCHASE', '2026-01-01', 1, 'IDR', "
                "'STAGED', 'Merge history', 'WEB', now(), now(), 0, 0)"
            ),
            {"id": uuid4(), "org": org_id},
        )
        await session.commit()
    try:
        async with pg_engine.begin() as connection:
            await invoke_bootstrap(connection)
        async with pg_session_factory() as session:
            assert await session.scalar(
                text(
                    "SELECT current_value FROM tenant_sequences "
                    "WHERE organization_id = :org AND namespace = 'TRX' AND scope_key = '2026'"
                ),
                {"org": org_id},
            ) == 150
    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(text("DELETE FROM tenant_sequences"))
            await connection.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
