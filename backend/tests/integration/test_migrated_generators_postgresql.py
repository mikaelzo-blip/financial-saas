from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.organization import Organization
from src.services.accounting_engine import AccountingEngine
from src.services.document_service import DocumentService
from src.services.money_movement_service import MoneyMovementService
from src.services.payable_service import VendorAPService
from src.services.project_service import ProjectService
from src.services.receivable_service import CustomerARService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService
from tests.integration.test_historical_sequence_bootstrap_postgresql import (
    insert_history,
    invoke_bootstrap,
)

pytestmark = pytest.mark.postgresql


@pytest.mark.asyncio
async def test_post_bootstrap_continuity_with_actual_generators(
    pg_engine,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify entire chain: historical rows -> 023 bootstrap -> actual CP4 generators."""
    org_a, org_b = uuid4(), uuid4()
    async with pg_session_factory() as session:
        await insert_history(session, org_a, org_b)

    try:
        async with pg_engine.begin() as connection:
            await invoke_bootstrap(connection)

        # Historical state seeded in insert_history:
        # org_a:
        # TRX 2026 -> 147 (reversal)
        # JE 2026  -> 31
        # PRJ 2026 -> 7
        # DOC 2026 -> 11
        # INV 2026 -> 25
        # BIL 2026 -> 9
        # ADV 2025 -> 6
        # REL 2026 -> 8
        # MM 2026  -> 126
        # SET GLOBAL -> 27

        async with pg_session_factory() as session:
            # 1. TransactionService (TRX 2026) -> should be 148
            trx_code = await TransactionService(session).generate_transaction_code(
                org_a, date(2026, 6, 1)
            )
            assert trx_code == "TRX-2026-000148"

            # 2. ReversalService (TRX 2026, shared with TransactionService) -> should be 149
            rev_code = await ReversalService(session).generate_reversal_code(
                org_a, date(2026, 6, 2)
            )
            assert rev_code == "TRX-2026-000149"

            # 3. AccountingEngine (JE 2026) -> should be 32
            je_code = await AccountingEngine(session).generate_entry_number(
                org_a, date(2026, 1, 1)
            )
            assert je_code == "JE-2026-000032"

            # 4. ProjectService (PRJ 2026) -> should be 8 (format: PRJ-YYYY-###)
            prj_code = await ProjectService(session).generate_project_code(
                org_a, date(2026, 1, 1)
            )
            assert prj_code == "PRJ-2026-008"

            # 5. DocumentService (DOC 2026) -> should be 12
            doc_code = await DocumentService(session).generate_document_code(org_a)
            assert doc_code == "DOC-2026-000012"

            # 6. CustomerARService (INV 2026) -> should be 26
            inv_code = await CustomerARService(session).generate_invoice_code(
                org_a, date(2026, 1, 1)
            )
            assert inv_code == "INV-2026-000026"

            # 7. VendorAPService (BIL 2026) -> should be 10
            bil_code = await VendorAPService(session).generate_bill_code(
                org_a, date(2026, 1, 1)
            )
            assert bil_code == "BIL-2026-000010"

            # 8. VendorAPService (ADV 2025) -> should be 7
            adv_code = await VendorAPService(session).generate_advance_code(
                org_a, date(2025, 1, 1)
            )
            assert adv_code == "ADV-2025-000007"

            # 9. CustomerARService (REL 2026) -> should be 9
            rel_code = await CustomerARService(session).generate_retention_release_code(
                org_a, date(2026, 1, 1)
            )
            assert rel_code == "REL-2026-000009"

            # 10. MoneyMovementService (MM 2026) -> should be 127
            mm_code = await MoneyMovementService(session)._generate_movement_code(
                org_a, date(2026, 1, 1)
            )
            assert mm_code == "MM-2026-000127"

            # 11. MoneyMovementService (SET GLOBAL) -> should be 28
            set_code = await MoneyMovementService(session)._generate_settlement_code(org_a)
            assert set_code == "SET-000028"

            await session.commit()

        # Check Org B post-bootstrap continuity:
        async with pg_session_factory() as session:
            # Org B TRX 2026 historical high-water was 7 -> should be 8
            trx_b = await TransactionService(session).generate_transaction_code(
                org_b, date(2026, 6, 1)
            )
            assert trx_b == "TRX-2026-000008"

            # Org B SET GLOBAL historical high-water was 3 -> should be 4
            set_b = await MoneyMovementService(session)._generate_settlement_code(org_b)
            assert set_b == "SET-000004"

            # Org B INV 2027 (empty scope) -> should be 1
            inv_b_empty = await CustomerARService(session).generate_invoice_code(
                org_b, date(2027, 1, 1)
            )
            assert inv_b_empty == "INV-2027-000001"

            await session.commit()

    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(text("DELETE FROM tenant_sequences"))
            await connection.execute(
                text("DELETE FROM organizations WHERE id IN (:a, :b)"),
                {"a": org_a, "b": org_b},
            )


@pytest.mark.asyncio
async def test_n50_mixed_transaction_and_reversal_concurrency(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """N=50 mixed concurrent normal transactions and reversals share one TRX counter without collision."""
    organization_id, _ = test_organizations
    count = 50
    business_date = date(2026, 9, 10)
    barrier = asyncio.Barrier(count + 1)

    async def worker(index: int) -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            if index % 2 == 0:
                code = await TransactionService(session).generate_transaction_code(
                    organization_id, business_date
                )
            else:
                code = await ReversalService(session).generate_reversal_code(
                    organization_id, business_date
                )
            await session.commit()
            return code

    tasks = [asyncio.create_task(worker(i)) for i in range(count)]
    await barrier.wait()
    codes = await asyncio.gather(*tasks)

    assert len(codes) == count
    assert len(set(codes)) == count, f"Expected {count} unique codes, got {len(set(codes))}"
    assert all(code.startswith("TRX-2026-") for code in codes)

    # Extract suffixes and ensure contiguous range 1..50
    suffixes = sorted(int(code.split("-")[2]) for code in codes)
    assert suffixes == list(range(1, count + 1))


@pytest.mark.asyncio
async def test_n50_settlement_global_concurrency(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """N=50 concurrent settlements use SET-###### with GLOBAL scope without collision."""
    organization_id, _ = test_organizations
    count = 50
    barrier = asyncio.Barrier(count + 1)

    async def worker() -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            code = await MoneyMovementService(session)._generate_settlement_code(
                organization_id
            )
            await session.commit()
            return code

    tasks = [asyncio.create_task(worker()) for _ in range(count)]
    await barrier.wait()
    codes = await asyncio.gather(*tasks)

    assert len(codes) == count
    assert len(set(codes)) == count
    assert all(code.startswith("SET-") for code in codes)
    suffixes = sorted(int(code.split("-")[1]) for code in codes)
    assert suffixes == list(range(1, count + 1))


@pytest.mark.asyncio
async def test_tenant_isolation_actual_generators(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """Org A and Org B independently receive the same sequential formatted codes."""
    org_a, org_b = test_organizations
    business_date = date(2026, 9, 10)

    async with pg_session_factory() as session:
        inv_a1 = await CustomerARService(session).generate_invoice_code(org_a, business_date)
        inv_b1 = await CustomerARService(session).generate_invoice_code(org_b, business_date)
        prj_a1 = await ProjectService(session).generate_project_code(org_a, business_date)
        prj_b1 = await ProjectService(session).generate_project_code(org_b, business_date)
        set_a1 = await MoneyMovementService(session)._generate_settlement_code(org_a)
        set_b1 = await MoneyMovementService(session)._generate_settlement_code(org_b)
        await session.commit()

    assert inv_a1 == "INV-2026-000001"
    assert inv_b1 == "INV-2026-000001"
    assert prj_a1 == "PRJ-2026-001"
    assert prj_b1 == "PRJ-2026-001"
    assert set_a1 == "SET-000001"
    assert set_b1 == "SET-000001"


@pytest.mark.asyncio
async def test_year_isolation_actual_generators(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """Different years for the same tenant have independent sequence counters."""
    org_a, _ = test_organizations

    async with pg_session_factory() as session:
        # Generate 3 codes in 2025
        c2025_1 = await TransactionService(session).generate_transaction_code(
            org_a, date(2025, 3, 1)
        )
        c2025_2 = await TransactionService(session).generate_transaction_code(
            org_a, date(2025, 4, 1)
        )
        c2025_3 = await TransactionService(session).generate_transaction_code(
            org_a, date(2025, 5, 1)
        )
        await session.commit()

    assert c2025_1 == "TRX-2025-000001"
    assert c2025_2 == "TRX-2025-000002"
    assert c2025_3 == "TRX-2025-000003"

    async with pg_session_factory() as session:
        # Year 2026 starts at 1, completely unaffected by 2025 high-water mark
        c2026_1 = await TransactionService(session).generate_transaction_code(
            org_a, date(2026, 1, 1)
        )
        await session.commit()

    assert c2026_1 == "TRX-2026-000001"


@pytest.mark.asyncio
async def test_rollback_restores_allocator_sequence_state(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """An uncommitted generator allocation rolls back with the transaction."""
    org_a, _ = test_organizations
    business_date = date(2026, 9, 10)

    async with pg_session_factory() as session:
        code_attempted = await TransactionService(session).generate_transaction_code(
            org_a, business_date
        )
        assert code_attempted == "TRX-2026-000001"
        # Transaction fails or rolls back
        await session.rollback()

    # Next transaction in clean session
    async with pg_session_factory() as session:
        code_clean = await TransactionService(session).generate_transaction_code(
            org_a, business_date
        )
        # Re-allocates 1 because previous transaction rolled back
        assert code_clean == "TRX-2026-000001"
        await session.commit()

    # Next transaction gets 2
    async with pg_session_factory() as session:
        code_next = await TransactionService(session).generate_transaction_code(
            org_a, business_date
        )
        assert code_next == "TRX-2026-000002"
        await session.commit()
