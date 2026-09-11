from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.audit import AuditLog
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    AccountType,
    DocumentType,
    MovementDirection,
    MovementSourceType,
    NormalBalance,
    ProjectStatus,
    SettlementType,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.project import Project
from src.models.payable import VendorAdvance, VendorBill
from src.models.receivable import CustomerInvoice, CustomerRetentionRelease
from src.models.transaction import Transaction
from src.schemas.money_movement import MoneyMovementCreate, SettlementCreate
from src.schemas.project import ProjectCreate
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.document_service import DocumentService
from src.services.money_movement_service import MoneyMovementService
from src.services.payable_service import VendorAPService
from src.services.project_service import ProjectService
from src.services.receivable_service import CustomerARService
from src.services.reversal_service import ReversalService
from src.services.tenant_sequence_allocator import allocate_next
from src.services.transaction_retry import run_in_clean_transaction
from src.services.transaction_service import TransactionService
from tests.integration.test_historical_sequence_bootstrap_postgresql import (
    invoke_bootstrap,
    load_migration,
)

pytestmark = pytest.mark.postgresql

CONCURRENCY = 50
BUSINESS_DATE = date(2026, 9, 10)


async def _allocate_concurrently(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    reversal: bool,
) -> list[str]:
    barrier = asyncio.Barrier(CONCURRENCY + 1)

    async def worker() -> str:
        async with session_factory() as session:
            await barrier.wait()
            if reversal:
                code = await ReversalService(session).generate_reversal_code(
                    organization_id, BUSINESS_DATE
                )
            else:
                code = await TransactionService(session).generate_transaction_code(
                    organization_id, BUSINESS_DATE
                )
            await session.commit()
            return code

    tasks = [asyncio.create_task(worker()) for _ in range(CONCURRENCY)]
    await barrier.wait()
    return await asyncio.gather(*tasks)


@pytest.mark.parametrize("reversal", [False, True], ids=["normal", "reversal"])
async def test_n50_each_transaction_path_is_unique_and_monotonic(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
    reversal: bool,
) -> None:
    organization_id, _ = test_organizations

    codes = await _allocate_concurrently(
        pg_session_factory,
        organization_id,
        reversal,
    )

    assert len(codes) == CONCURRENCY
    assert len(set(codes)) == CONCURRENCY
    assert all(code.startswith("TRX-2026-") for code in codes)
    suffixes = sorted(int(code.rsplit("-", 1)[1]) for code in codes)
    assert suffixes == list(range(1, CONCURRENCY + 1))


@pytest.mark.parametrize(
    "malformed_code",
    [
        "BAD-2026-000001",
        "TRX-2026-NOTNUM",
        "TRX-2026-00001",
        "TRX-0000-000001",
    ],
    ids=["incorrect-prefix", "nonnumeric-suffix", "invalid-width", "invalid-year"],
)
async def test_postgresql_malformed_history_aborts_without_partial_sequence_state(
    pg_engine,
    pg_session_factory: async_sessionmaker[AsyncSession],
    malformed_code: str,
) -> None:
    organization_id = uuid4()
    transaction_id = uuid4()
    async with pg_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO organizations (id, slug, legal_name) "
                "VALUES (:id, :slug, 'CP6 malformed history')"
            ),
            {"id": organization_id, "slug": f"cp6-malformed-{organization_id.hex[:12]}"},
        )
        await session.execute(
            text(
                "INSERT INTO transactions "
                "(id, organization_id, transaction_code, transaction_type, transaction_date, "
                "amount, currency, workflow_status, description, source_channel, created_at, "
                "updated_at, retention_rate, retention_amount) VALUES "
                "(:id, :organization_id, :code, 'DIRECT_PURCHASE', :transaction_date, 1, 'IDR', "
                "'STAGED', 'CP6 malformed history', 'WEB', now(), now(), 0, 0)"
            ),
            {
                "id": transaction_id,
                "organization_id": organization_id,
                "code": malformed_code,
                "transaction_date": BUSINESS_DATE,
            },
        )
        await session.commit()

    try:
        with pytest.raises(load_migration().HistoricalSequenceBootstrapError):
            async with pg_engine.begin() as connection:
                await invoke_bootstrap(connection)

        async with pg_session_factory() as session:
            sequence_count = await session.scalar(
                text(
                    "SELECT COUNT(*) FROM tenant_sequences "
                    "WHERE organization_id = :organization_id"
                ),
                {"organization_id": organization_id},
            )
            assert sequence_count == 0
            assert await session.scalar(
                text(
                    "SELECT transaction_code FROM transactions WHERE id = :transaction_id"
                ),
                {"transaction_id": transaction_id},
            ) == malformed_code
    finally:
        async with pg_engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM tenant_sequences WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await connection.execute(
                text("DELETE FROM organizations WHERE id = :organization_id"),
                {"organization_id": organization_id},
            )


@pytest.mark.parametrize(
    ("namespace", "code", "scope_kind", "suffix_width"),
    [
        ("TRX", "TRX-2026-NOTNUM", "YEAR", 6),
        ("JE", "JE-2026-00001", "YEAR", 6),
        ("PRJ", "PRJ-2026-0001", "YEAR", 3),
        ("DOC", "DOC-2026-00000A", "YEAR", 6),
        ("INV", "INV-0000-000001", "YEAR", 6),
        ("BIL", "BIL-2026-0000000", "YEAR", 6),
        ("ADV", "ADV-2026-ABCDEF", "YEAR", 6),
        ("REL", "REL-2026-00001", "YEAR", 6),
        ("MM", "MM-2026-000000X", "YEAR", 6),
        ("SET", "SET-2026-000001", "GLOBAL", 6),
    ],
)
async def test_all_managed_namespaces_reject_malformed_historical_codes(
    namespace: str,
    code: str,
    scope_kind: str,
    suffix_width: int,
) -> None:
    migration = load_migration()
    with pytest.raises(migration.HistoricalSequenceBootstrapError):
        migration._parse_historical_code(
            namespace=namespace,
            code=code,
            suffix_width=suffix_width,
            scope_kind=scope_kind,
        )


async def _concurrent_results(tasks: list[asyncio.Task], timeout: float = 120.0) -> list:
    return await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)


async def _create_posted_direct_purchase(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    account_id: UUID,
    index: int,
) -> UUID:
    async with session_factory() as session:
        transaction = Transaction(
            organization_id=organization_id,
            transaction_code=f"CP6-ORIGINAL-{index:03d}-{uuid4().hex[:8]}",
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=BUSINESS_DATE,
            amount=Decimal("10.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.POSTED,
            description=f"CP6 concurrent reversal original {index}",
        )
        session.add(transaction)
        await session.flush()
        journal = JournalEntry(
            organization_id=organization_id,
            entry_number=f"CP6-ORIGINAL-JE-{index:03d}-{uuid4().hex[:8]}",
            transaction_id=transaction.id,
            posting_date=BUSINESS_DATE,
            description=transaction.description,
            total_debit=Decimal("10.00"),
            total_credit=Decimal("10.00"),
            is_balanced=True,
        )
        session.add(journal)
        await session.flush()
        session.add_all(
            [
                JournalLine(
                    journal_entry_id=journal.id,
                    line_number=1,
                    account_id=account_id,
                    debit_amount=Decimal("10.00"),
                    credit_amount=Decimal("0.00"),
                ),
                JournalLine(
                    journal_entry_id=journal.id,
                    line_number=2,
                    account_id=account_id,
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("10.00"),
                ),
            ]
        )
        await session.commit()
        return transaction.id


@pytest.mark.parametrize("reversal", [False, True], ids=["normal-records", "reversal-records"])
async def test_n50_transaction_code_allocations_commit_business_records(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
    reversal: bool,
) -> None:
    organization_id, _ = test_organizations
    if not reversal:
        barrier = asyncio.Barrier(CONCURRENCY)

        async def worker(index: int) -> str:
            async with pg_session_factory() as session:
                await barrier.wait()
                code = await TransactionService(session).generate_transaction_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    Transaction(
                        organization_id=organization_id,
                        transaction_code=code,
                        transaction_type=TransactionType.DIRECT_PURCHASE,
                        transaction_date=BUSINESS_DATE,
                        amount=Decimal("10.00") + index,
                        currency="IDR",
                        workflow_status=WorkflowStatus.APPROVED,
                        description=f"CP6 committed normal transaction {index}",
                    )
                )
                await session.commit()
                return code

        codes = await _concurrent_results(
            [asyncio.create_task(worker(index)) for index in range(CONCURRENCY)]
        )
        async with pg_session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.organization_id == organization_id,
                    Transaction.description.like("CP6 committed normal transaction %"),
                )
            )
        assert count == CONCURRENCY
    else:
        async with pg_session_factory() as session:
            account = ChartOfAccount(
                organization_id=organization_id,
                account_code="CP6-REV-1101",
                account_name="CP6 reversal account",
                account_type=AccountType.ASSET,
                normal_balance=NormalBalance.DEBIT,
                report_group="CP6",
            )
            session.add(account)
            await session.commit()
            account_id = account.id
        original_ids = await _concurrent_results(
            [
                asyncio.create_task(
                    _create_posted_direct_purchase(
                        pg_session_factory, organization_id, account_id, index
                    )
                )
                for index in range(CONCURRENCY)
            ]
        )

        async def worker(original_id: UUID) -> str:
            async with pg_session_factory() as session:
                reversal, _ = await ReversalService(session).reverse_transaction(
                    organization_id,
                    original_id,
                    reason="CP6 concurrent reversal",
                    reversal_date=BUSINESS_DATE,
                )
                await session.commit()
                return reversal.transaction_code

        codes = await _concurrent_results(
            [asyncio.create_task(worker(original_id)) for original_id in original_ids]
        )
        async with pg_session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.organization_id == organization_id,
                    Transaction.transaction_type == TransactionType.REVERSAL,
                    Transaction.description.like("REVERSAL OF %CP6 concurrent reversal%"),
                )
            )
        assert count == CONCURRENCY

    assert len(codes) == CONCURRENCY
    assert len(set(codes)) == CONCURRENCY
    assert sorted(int(code.rsplit("-", 1)[1]) for code in codes) == list(
        range(1, CONCURRENCY + 1)
    )


async def test_n50_mixed_committed_normal_and_reversal_records_share_trx_sequence(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    async with pg_session_factory() as session:
        account = ChartOfAccount(
            organization_id=organization_id,
            account_code="CP6-MIX-1101",
            account_name="CP6 mixed account",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="CP6",
        )
        session.add(account)
        await session.commit()
        account_id = account.id

    original_ids = await _concurrent_results(
        [
            asyncio.create_task(
                _create_posted_direct_purchase(
                    pg_session_factory, organization_id, account_id, index
                )
            )
            for index in range(CONCURRENCY // 2)
        ]
    )
    reversal_ids = set(original_ids)
    barrier = asyncio.Barrier(CONCURRENCY + 1)

    async def normal_worker(index: int) -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            code = await TransactionService(session).generate_transaction_code(
                organization_id, BUSINESS_DATE
            )
            session.add(
                Transaction(
                    organization_id=organization_id,
                    transaction_code=code,
                    transaction_type=TransactionType.DIRECT_PURCHASE,
                    transaction_date=BUSINESS_DATE,
                    amount=Decimal("20.00") + index,
                    currency="IDR",
                    workflow_status=WorkflowStatus.APPROVED,
                    description=f"CP6 mixed normal {index}",
                )
            )
            await session.commit()
            return code

    async def reversal_worker(original_id: UUID) -> str:
        async with pg_session_factory() as session:
            await barrier.wait()
            reversal, _ = await ReversalService(session).reverse_transaction(
                organization_id,
                original_id,
                reason="CP6 mixed reversal",
                reversal_date=BUSINESS_DATE,
            )
            await session.commit()
            return reversal.transaction_code

    tasks = [
        asyncio.create_task(normal_worker(index))
        for index in range(CONCURRENCY // 2)
    ] + [
        asyncio.create_task(reversal_worker(original_id))
        for original_id in reversal_ids
    ]
    await barrier.wait()
    codes = await _concurrent_results(tasks)
    assert len(codes) == CONCURRENCY
    assert len(set(codes)) == CONCURRENCY
    assert sorted(int(code.rsplit("-", 1)[1]) for code in codes) == list(
        range(1, CONCURRENCY + 1)
    )

    async with pg_session_factory() as session:
        normal_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.organization_id == organization_id,
                Transaction.description.like("CP6 mixed normal %"),
            )
        )
        reversal_count = await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.organization_id == organization_id,
                Transaction.transaction_type == TransactionType.REVERSAL,
                Transaction.description.like("REVERSAL OF %CP6 mixed reversal%"),
            )
        )
    assert normal_count == CONCURRENCY // 2
    assert reversal_count == CONCURRENCY // 2


async def test_retryable_collision_through_real_transaction_posting_is_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    await _seed_standard_posting_fixtures(pg_session_factory, organization_id)
    conflict_transaction_id = uuid4()
    conflict_entry_number = "JE-2026-999900"
    async with pg_session_factory() as session:
        session.add(
            Transaction(
                id=conflict_transaction_id,
                organization_id=organization_id,
                transaction_code="TRX-2025-999900",
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2025, 1, 1),
                amount=Decimal("999.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.POSTED,
                description="CP6 posting collision fixture",
            )
        )
        await session.flush()
        session.add(
            JournalEntry(
                organization_id=organization_id,
                entry_number=conflict_entry_number,
                transaction_id=conflict_transaction_id,
                posting_date=date(2025, 1, 1),
                description="CP6 posting collision fixture",
                total_debit=Decimal("999.00"),
                total_credit=Decimal("999.00"),
                is_balanced=True,
            )
        )
        await session.commit()

    original_generate = AccountingEngine.generate_entry_number
    generated_entry_calls = 0

    async def injected_entry_number(self, organization_id: UUID, posting_date=None) -> str:
        nonlocal generated_entry_calls
        generated = await original_generate(self, organization_id, posting_date)
        generated_entry_calls += 1
        return conflict_entry_number if generated_entry_calls == 1 else generated

    monkeypatch.setattr(AccountingEngine, "generate_entry_number", injected_entry_number)
    attempts = 0
    attempted_transaction_ids: list[UUID] = []

    async def operation(session: AsyncSession) -> JournalEntry:
        nonlocal attempts
        attempts += 1
        transaction = await TransactionService(session).create_transaction(
            organization_id,
            TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("125.00"),
                description="CP6 real posting retry",
            ),
        )
        attempted_transaction_ids.append(transaction.id)
        return await AccountingEngine(session).post_transaction(
            organization_id, transaction.id
        )

    async with pg_session_factory() as session:
        journal = await run_in_clean_transaction(session, operation)
        await session.commit()

    assert attempts == 2
    assert generated_entry_calls == 2
    assert len(attempted_transaction_ids) == 2
    assert journal.is_balanced is True
    async with pg_session_factory() as session:
        transaction_rows = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.organization_id == organization_id,
                    Transaction.description == "CP6 real posting retry",
                )
            )
        ).all()
        assert len(transaction_rows) == 1
        assert transaction_rows[0].id == journal.transaction_id
        assert transaction_rows[0].workflow_status == WorkflowStatus.POSTED
        assert await session.scalar(
            select(func.count()).select_from(JournalEntry).where(
                JournalEntry.transaction_id == journal.transaction_id,
            )
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(JournalLine).join(JournalEntry).where(
                JournalEntry.transaction_id == journal.transaction_id,
            )
        ) == 2
        assert await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_id == journal.transaction_id,
                AuditLog.action == "POST",
            )
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.id == attempted_transaction_ids[0],
            )
        ) == 0


async def _seed_standard_posting_fixtures(
    session_factory: async_sessionmaker[AsyncSession], organization_id: UUID
) -> None:
    async with session_factory() as session:
        await seed_standard_coa(session, organization_id)
        await session.commit()


async def test_retryable_collision_through_real_reversal_is_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    await _seed_standard_posting_fixtures(pg_session_factory, organization_id)
    async with pg_session_factory() as session:
        original = await TransactionService(session).create_transaction(
            organization_id,
            TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("130.00"),
                description="CP6 real reversal original",
            ),
        )
        await session.commit()
    async with pg_session_factory() as session:
        await AccountingEngine(session).post_transaction(organization_id, original.id)
        await session.commit()

    conflict_transaction_id = uuid4()
    conflict_entry_number = "JE-2026-999901"
    async with pg_session_factory() as session:
        session.add(
            Transaction(
                id=conflict_transaction_id,
                organization_id=organization_id,
                transaction_code="TRX-2025-999901",
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2025, 1, 1),
                amount=Decimal("998.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.POSTED,
                description="CP6 reversal collision fixture",
            )
        )
        await session.flush()
        session.add(
            JournalEntry(
                organization_id=organization_id,
                entry_number=conflict_entry_number,
                transaction_id=conflict_transaction_id,
                posting_date=date(2025, 1, 1),
                description="CP6 reversal collision fixture",
                total_debit=Decimal("998.00"),
                total_credit=Decimal("998.00"),
                is_balanced=True,
            )
        )
        await session.commit()

    original_generate = AccountingEngine.generate_entry_number
    generated_entry_calls = 0

    async def injected_entry_number(self, organization_id: UUID, posting_date=None) -> str:
        nonlocal generated_entry_calls
        generated = await original_generate(self, organization_id, posting_date)
        generated_entry_calls += 1
        return conflict_entry_number if generated_entry_calls == 1 else generated

    monkeypatch.setattr(AccountingEngine, "generate_entry_number", injected_entry_number)
    attempts = 0

    async def operation(session: AsyncSession) -> tuple[Transaction, JournalEntry]:
        nonlocal attempts
        attempts += 1
        return await ReversalService(session).reverse_transaction(
            organization_id,
            original.id,
            reason="CP6 real reversal retry",
            reversal_date=BUSINESS_DATE,
        )

    async with pg_session_factory() as session:
        reversal, reversal_journal = await run_in_clean_transaction(session, operation)
        await session.commit()

    assert attempts == 2
    assert generated_entry_calls == 2
    assert reversal_journal.is_balanced is True
    async with pg_session_factory() as session:
        assert await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.organization_id == organization_id,
                Transaction.reversal_of_id == original.id,
            )
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(JournalEntry).where(
                JournalEntry.transaction_id == reversal.id,
            )
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(JournalLine).join(JournalEntry).where(
                JournalEntry.transaction_id == reversal.id,
            )
        ) == 2
        assert await session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.entity_id == original.id,
                AuditLog.action == "REVERSAL",
            )
        ) == 1
        original_journal = await session.scalar(
            select(JournalEntry).where(JournalEntry.transaction_id == original.id)
        )
        assert original_journal is not None
        assert original_journal.is_reversed is True
        assert original_journal.reversal_entry_id == reversal_journal.id


@pytest.mark.parametrize(
    "namespace",
    ["TRX", "JE", "PRJ", "DOC", "INV", "BIL", "ADV", "REL", "MM", "SET"],
)
async def test_concurrent_namespace_generators_commit_business_records(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
    namespace: str,
) -> None:
    """Concurrent generated identifiers are persisted as tenant-owned records."""
    organization_id, _ = test_organizations
    async with pg_session_factory() as session:
        await seed_standard_coa(session, organization_id)
        await seed_standard_payment_accounts(session, organization_id)
        customer = Counterparty(
            organization_id=organization_id,
            name="CP6 generator customer",
            is_customer=True,
        )
        vendor = Counterparty(
            organization_id=organization_id,
            name="CP6 generator vendor",
            is_vendor=True,
        )
        session.add_all([customer, vendor])
        await session.flush()
        project = Project(
            organization_id=organization_id,
            project_code="CP6-SUPPORT-PROJECT",
            project_name="CP6 generator support project",
            customer_id=customer.id,
            start_date=BUSINESS_DATE,
            project_status=ProjectStatus.ACTIVE,
        )
        session.add(project)
        await session.flush()
        payment_account = await session.scalar(
            select(PaymentAccount).where(
                PaymentAccount.organization_id == organization_id,
            )
        )
        assert payment_account is not None
        customer_id, vendor_id, project_id, payment_account_id = (
            customer.id,
            vendor.id,
            project.id,
            payment_account.id,
        )
        invoice_id = project_id
        if namespace == "REL":
            invoice = CustomerInvoice(
                organization_id=organization_id,
                invoice_code="CP6-REL-SUPPORT-INVOICE",
                customer_id=customer_id,
                project_id=project_id,
                invoice_date=BUSINESS_DATE,
                due_date=BUSINESS_DATE + timedelta(days=30),
                total_amount=Decimal("10.00"),
                retention_rate=Decimal("0.1000"),
                retention_amount=Decimal("1.00"),
                retention_released_amount=Decimal("0.00"),
                retention_paid_amount=Decimal("0.00"),
                status="UNPAID",
            )
            session.add(invoice)
            await session.flush()
            invoice_id = invoice.id
        await session.commit()

    count = 10

    async def worker(index: int) -> str:
        async with pg_session_factory() as session:
            if namespace == "TRX":
                code = await TransactionService(session).generate_transaction_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    Transaction(
                        organization_id=organization_id,
                        transaction_code=code,
                        transaction_type=TransactionType.DIRECT_PURCHASE,
                        transaction_date=BUSINESS_DATE,
                        amount=Decimal("10.00"),
                        currency="IDR",
                        workflow_status=WorkflowStatus.APPROVED,
                        description=f"CP6 persisted {namespace} {index}",
                    )
                )
            elif namespace == "JE":
                transaction = Transaction(
                    organization_id=organization_id,
                    transaction_code=f"CP6-JE-TRX-{index}-{uuid4().hex[:8]}",
                    transaction_type=TransactionType.DIRECT_PURCHASE,
                    transaction_date=BUSINESS_DATE,
                    amount=Decimal("10.00"),
                    currency="IDR",
                    workflow_status=WorkflowStatus.POSTED,
                    description=f"CP6 persisted {namespace} {index}",
                )
                session.add(transaction)
                await session.flush()
                code = await AccountingEngine(session).generate_entry_number(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    JournalEntry(
                        organization_id=organization_id,
                        entry_number=code,
                        transaction_id=transaction.id,
                        posting_date=BUSINESS_DATE,
                        description=transaction.description,
                        total_debit=Decimal("10.00"),
                        total_credit=Decimal("10.00"),
                        is_balanced=True,
                    )
                )
            elif namespace == "PRJ":
                code = await ProjectService(session).generate_project_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    Project(
                        organization_id=organization_id,
                        project_code=code,
                        project_name=f"CP6 persisted project {index}",
                        customer_id=customer_id,
                        start_date=BUSINESS_DATE,
                        project_status=ProjectStatus.PLANNED,
                    )
                )
            elif namespace == "DOC":
                code = await DocumentService(session).generate_document_code(organization_id)
                session.add(
                    Document(
                        organization_id=organization_id,
                        document_code=code,
                        document_type=DocumentType.RECEIPT,
                        file_name=f"cp6-{index}.pdf",
                        mime_type="application/pdf",
                        file_size_bytes=5,
                        file_hash=hashlib.sha256(f"cp6-{namespace}-{index}".encode()).hexdigest(),
                        storage_path=f"documents/cp6/{index}.pdf",
                        source_channel="WEB",
                        source_metadata={},
                        raw_extraction={},
                        extracted_data={},
                        matching_results={},
                        confidence_scores={},
                        candidate_transaction={},
                        review_flags=[],
                    )
                )
            elif namespace == "INV":
                code = await CustomerARService(session).generate_invoice_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    CustomerInvoice(
                        organization_id=organization_id,
                        invoice_code=code,
                        customer_id=customer_id,
                        project_id=project_id,
                        invoice_date=BUSINESS_DATE,
                        due_date=BUSINESS_DATE + timedelta(days=30),
                        total_amount=Decimal("10.00"),
                        retention_rate=Decimal("0.0000"),
                        retention_amount=Decimal("0.00"),
                        retention_released_amount=Decimal("0.00"),
                        retention_paid_amount=Decimal("0.00"),
                        status="UNPAID",
                    )
                )
            elif namespace == "BIL":
                code = await VendorAPService(session).generate_bill_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    VendorBill(
                        organization_id=organization_id,
                        bill_code=code,
                        vendor_id=vendor_id,
                        bill_date=BUSINESS_DATE,
                        due_date=BUSINESS_DATE + timedelta(days=30),
                        total_amount=Decimal("10.00"),
                        status="UNPAID",
                    )
                )
            elif namespace == "ADV":
                transaction = Transaction(
                    organization_id=organization_id,
                    transaction_code=f"CP6-ADV-TRX-{index}-{uuid4().hex[:8]}",
                    transaction_type=TransactionType.VENDOR_ADVANCE,
                    transaction_date=BUSINESS_DATE,
                    amount=Decimal("10.00"),
                    currency="IDR",
                    workflow_status=WorkflowStatus.POSTED,
                    description=f"CP6 persisted {namespace} {index}",
                )
                session.add(transaction)
                await session.flush()
                code = await VendorAPService(session).generate_advance_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    VendorAdvance(
                        organization_id=organization_id,
                        advance_code=code,
                        vendor_id=vendor_id,
                        advance_date=BUSINESS_DATE,
                        original_amount=Decimal("10.00"),
                        settled_amount=Decimal("0.00"),
                        remaining_balance=Decimal("10.00"),
                        transaction_id=transaction.id,
                    )
                )
            elif namespace == "REL":
                code = await CustomerARService(session).generate_retention_release_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    CustomerRetentionRelease(
                        organization_id=organization_id,
                        invoice_id=invoice_id,
                        release_code=code,
                        release_date=BUSINESS_DATE,
                        release_amount=Decimal("1.00"),
                    )
                )
            elif namespace == "MM":
                code = await MoneyMovementService(session)._generate_movement_code(
                    organization_id, BUSINESS_DATE
                )
                session.add(
                    MoneyMovement(
                        organization_id=organization_id,
                        movement_code=code,
                        payment_account_id=payment_account_id,
                        direction=MovementDirection.IN,
                        amount=Decimal("10.00"),
                        movement_date=BUSINESS_DATE,
                        source_type=MovementSourceType.MANUAL,
                        description=f"CP6 persisted {namespace} {index}",
                    )
                )
            else:
                code = await MoneyMovementService(session)._generate_settlement_code(
                    organization_id
                )
                movement = MoneyMovement(
                    organization_id=organization_id,
                    movement_code=f"CP6-SET-MM-{index}-{uuid4().hex[:8]}",
                    payment_account_id=payment_account_id,
                    direction=MovementDirection.IN,
                    amount=Decimal("10.00"),
                    movement_date=BUSINESS_DATE,
                    source_type=MovementSourceType.MANUAL,
                    description=f"CP6 persisted {namespace} {index}",
                )
                session.add(movement)
                await session.flush()
                settlement = Settlement(
                    organization_id=organization_id,
                    settlement_code=code,
                    money_movement_id=movement.id,
                    settlement_type=SettlementType.DIRECT_EXPENSE,
                    amount=Decimal("10.00"),
                )
                session.add(settlement)
                await session.flush()
                session.add(
                    SettlementAllocation(
                        settlement_id=settlement.id,
                        amount=Decimal("10.00"),
                    )
                )
            await session.commit()
            return code

    codes = await _concurrent_results(
        [asyncio.create_task(worker(index)) for index in range(count)]
    )
    widths = {"PRJ": 3, "SET": 6}.get(namespace, 6)
    prefixes = {"SET": "SET-", "PRJ": "PRJ-2026-", "DOC": "DOC-2026-"}
    prefix = prefixes.get(namespace, f"{namespace}-2026-")
    assert len(codes) == count
    assert len(set(codes)) == count
    assert all(code.startswith(prefix) for code in codes)
    assert sorted(int(code.rsplit("-", 1)[1]) for code in codes) == list(
        range(1, count + 1)
    )
    assert all(len(code.rsplit("-", 1)[1]) == widths for code in codes)
