from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.exceptions import InvariantViolationException
from src.models.enums import TransactionType, WorkflowStatus
from src.models.journal import JournalEntry
from src.models.transaction import Transaction
from src.services.accounting_engine import AccountingEngine
from src.services.document_service import DocumentService
from src.services.money_movement_service import MoneyMovementService
from src.services.payable_service import VendorAPService
from src.services.project_service import ProjectService
from src.services.receivable_service import CustomerARService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService
from tests.integration.f012_postgresql_support import assert_postgresql_migration_head

pytestmark = pytest.mark.postgresql

N = 20
BUSINESS_DATE = date(2026, 9, 10)


async def allocate_concurrently(
    session_factory: async_sessionmaker[AsyncSession],
    allocator: Callable[[AsyncSession], Awaitable[str]],
    count: int = N,
) -> list[str]:
    barrier = asyncio.Barrier(count + 1)

    async def worker() -> str:
        async with session_factory() as session:
            await barrier.wait()
            return await allocator(session)

    tasks = [asyncio.create_task(worker()) for _ in range(count)]
    await barrier.wait()
    return await asyncio.gather(*tasks)


async def assert_unique_candidates(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    allocator: Callable[[AsyncSession], Awaitable[str]],
    expected_prefix: str,
) -> None:
    codes = await allocate_concurrently(session_factory, allocator)
    assert len(codes) == N
    assert len(set(codes)) == N, (
        f"required {N} unique {expected_prefix} candidates, got {len(set(codes))}; "
        "the current COUNT/MAX allocator is expected to be red"
    )
    assert all(code.startswith(expected_prefix) for code in codes)


async def count_transactions(session: AsyncSession, organization_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.organization_id == organization_id
            )
        )
        or 0
    )


async def test_postgresql_baseline_is_current(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        await assert_postgresql_migration_head(session)


@pytest.mark.parametrize(
    ("factory", "prefix"),
    [
        (
            lambda session, org_id: TransactionService(session).generate_transaction_code(
                org_id, BUSINESS_DATE
            ),
            "TRX-2026-",
        ),
        (
            lambda session, org_id: AccountingEngine(session).generate_entry_number(
                org_id, BUSINESS_DATE
            ),
            "JE-2026-",
        ),
        (
            lambda session, org_id: ProjectService(session).generate_project_code(
                org_id, BUSINESS_DATE
            ),
            "PRJ-2026-",
        ),
        (
            lambda session, org_id: DocumentService(session).generate_document_code(org_id),
            "DOC-2026-",
        ),
        (
            lambda session, org_id: VendorAPService(session).generate_bill_code(
                org_id, BUSINESS_DATE
            ),
            "BIL-2026-",
        ),
        (
            lambda session, org_id: VendorAPService(session).generate_advance_code(
                org_id, BUSINESS_DATE
            ),
            "ADV-2026-",
        ),
        (
            lambda session, org_id: CustomerARService(session).generate_invoice_code(
                org_id, BUSINESS_DATE
            ),
            "INV-2026-",
        ),
        (
            lambda session, org_id: CustomerARService(
                session
            ).generate_retention_release_code(org_id, BUSINESS_DATE),
            "REL-2026-",
        ),
        (
            lambda session, org_id: MoneyMovementService(session)._generate_movement_code(
                org_id, BUSINESS_DATE
            ),
            "MM-2026-",
        ),
        (
            lambda session, org_id: MoneyMovementService(session)._generate_settlement_code(
                org_id
            ),
            "SET-",
        ),
    ],
    ids=["transaction", "journal", "project", "document", "bill", "advance", "invoice", "release", "movement", "settlement"],
)
async def test_count_max_generators_are_unique_under_postgresql_concurrency(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
    factory: Callable[[AsyncSession, UUID], Awaitable[str]],
    prefix: str,
) -> None:
    organization_id, _ = test_organizations
    await assert_unique_candidates(
        pg_session_factory,
        organization_id,
        lambda session: factory(session, organization_id),
        prefix,
    )


async def test_transaction_creation_commits_n_unique_codes(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    barrier = asyncio.Barrier(N + 1)

    async def create_transaction(index: int) -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            code = await TransactionService(session).generate_transaction_code(
                organization_id, BUSINESS_DATE
            )
            session.add(
                Transaction(
                    id=uuid4(),
                    organization_id=organization_id,
                    transaction_code=code,
                    transaction_type=TransactionType.DIRECT_PURCHASE,
                    transaction_date=BUSINESS_DATE,
                    amount=Decimal("100.00"),
                    currency="IDR",
                    workflow_status=WorkflowStatus.APPROVED,
                    description=f"Feature 012 concurrency test {index}",
                )
            )
            await session.commit()
            return code

    tasks = [asyncio.create_task(create_transaction(index)) for index in range(N)]
    await barrier.wait()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    committed_codes = [result for result in results if isinstance(result, str)]
    uniqueness_failures = [result for result in results if isinstance(result, IntegrityError)]
    assert len(committed_codes) == N, (
        f"required {N} committed transactions, got {len(committed_codes)}; "
        f"unique constraint failures: {len(uniqueness_failures)}"
    )
    assert len(set(committed_codes)) == N

    async with pg_session_factory() as session:
        assert await count_transactions(session, organization_id) == N


async def test_normal_and_reversal_paths_share_transaction_namespace(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    barrier = asyncio.Barrier(3)

    async def normal() -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            return await TransactionService(session).generate_transaction_code(
                organization_id, BUSINESS_DATE
            )

    async def reversal() -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            return await ReversalService(session).generate_reversal_code(
                organization_id, BUSINESS_DATE
            )

    normal_task = asyncio.create_task(normal())
    reversal_task = asyncio.create_task(reversal())
    await barrier.wait()
    normal_code, reversal_code = await asyncio.gather(normal_task, reversal_task)

    assert normal_code != reversal_code, (
        "normal and reversal allocation must draw from one collision-safe TRX "
        "namespace; current independent COUNT scans are expected to collide"
    )
    assert normal_code.startswith("TRX-2026-")
    assert reversal_code.startswith("TRX-2026-")


async def test_first_row_bootstrap_contract_is_unique_for_concurrent_empty_scope(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    await assert_unique_candidates(
        pg_session_factory,
        organization_id,
        lambda session: TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        ),
        "TRX-2026-",
    )


async def test_failed_transaction_rolls_back_without_partial_authoritative_record(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    async with pg_session_factory() as session:
        code = await TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        )
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="Feature 012 rollback test",
            )
        )
        await session.flush()
        await session.rollback()

        assert await count_transactions(session, organization_id) == 0
        clean_code = await TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        )
        assert clean_code == code


async def test_integrity_error_requires_rollback_before_clean_retry(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    duplicate_code = "TRX-2026-999999"
    async with pg_session_factory() as session:
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=duplicate_code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="Feature 012 poisoned session seed",
            )
        )
        await session.commit()

        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=duplicate_code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="Feature 012 poisoned session duplicate",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()

        with pytest.raises(PendingRollbackError):
            await count_transactions(session, organization_id)

        await session.rollback()
        assert await count_transactions(session, organization_id) == 1

        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code="TRX-2026-999998",
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="Feature 012 clean retry",
            )
        )
        await session.commit()
        assert await count_transactions(session, organization_id) == 2


async def test_posting_failure_leaves_no_journal_or_transaction(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    transaction_id = uuid4()
    async with pg_session_factory() as session:
        transaction = Transaction(
            id=transaction_id,
            organization_id=organization_id,
            transaction_code="TRX-2026-123456",
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=BUSINESS_DATE,
            amount=Decimal("100.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            description="Feature 012 failed posting",
        )
        session.add(transaction)
        await session.flush()
        with pytest.raises(InvariantViolationException):
            await AccountingEngine(session).post_transaction(
                organization_id, transaction_id, BUSINESS_DATE
            )
        await session.rollback()

        assert await session.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.id == transaction_id)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(JournalEntry).where(
                JournalEntry.transaction_id == transaction_id
            )
        ) == 0
