from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.enums import TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.tenant_sequence_allocator import SequenceCollisionError
from src.services.transaction_retry import (
    MAX_TRANSACTION_RETRY_ATTEMPTS,
    is_retryable_generated_code_collision,
    run_in_clean_transaction,
)
from src.services.transaction_service import TransactionService

pytestmark = pytest.mark.postgresql

BUSINESS_DATE = date(2026, 9, 10)


async def count_transactions(session: AsyncSession, organization_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(Transaction).where(
                Transaction.organization_id == organization_id
            )
        )
        or 0
    )


async def test_retry_reopens_clean_transaction_and_commits_one_business_effect(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    conflicting_code = "TRX-2026-999999"

    async with pg_session_factory() as session:
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=conflicting_code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="CP5 collision fixture",
            )
        )
        await session.commit()

    attempts = 0

    async def operation(session: AsyncSession) -> str:
        nonlocal attempts
        attempts += 1
        generated_code = await TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        )
        code = conflicting_code if attempts == 1 else generated_code
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="CP5 retry success",
            )
        )
        await session.flush()
        return code

    async with pg_session_factory() as session:
        result = await run_in_clean_transaction(session, operation)
        await session.commit()

    assert attempts == 2
    assert result == "TRX-2026-000001"
    async with pg_session_factory() as session:
        assert await count_transactions(session, organization_id) == 2
        sequence_value = await session.scalar(
            select(func.max(Transaction.transaction_code)).where(
                Transaction.organization_id == organization_id
            )
        )
        assert sequence_value == conflicting_code


async def test_retry_bound_is_three_and_failed_attempts_leave_no_business_records(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    conflicting_code = "TRX-2026-999998"

    async with pg_session_factory() as session:
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=conflicting_code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="CP5 exhausted retry fixture",
            )
        )
        await session.commit()

    attempts = 0

    async def operation(session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        await TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        )
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code=conflicting_code,
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("100.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="CP5 exhausted retry attempt",
            )
        )
        await session.flush()

    async with pg_session_factory() as session:
        with pytest.raises(SequenceCollisionError):
            await run_in_clean_transaction(session, operation)

    assert MAX_TRANSACTION_RETRY_ATTEMPTS == 3
    assert attempts == MAX_TRANSACTION_RETRY_ATTEMPTS
    async with pg_session_factory() as session:
        assert await count_transactions(session, organization_id) == 1


async def test_retry_rejects_attempts_above_hard_bound(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with pg_session_factory() as session:
        with pytest.raises(ValueError, match="between 1 and 3"):
            await run_in_clean_transaction(session, lambda _: _never_called(), max_attempts=4)


async def _never_called() -> None:
    raise AssertionError("the operation must not run when the retry bound is invalid")


async def test_caller_supplied_invoice_and_bill_code_collisions_are_not_retryable() -> None:
    class RetrySession:
        info: dict[str, object] = {}

        async def flush(self) -> None:
            pass

        async def rollback(self) -> None:
            pass

    for constraint_name in (
        "uq_customer_invoices_org_code",
        "uq_vendor_bills_org_code",
    ):
        attempts = 0
        error = IntegrityError(
            "duplicate",
            (),
            SimpleNamespace(constraint_name=constraint_name),
        )

        async def operation(_: AsyncSession) -> None:
            nonlocal attempts
            attempts += 1
            raise error

        with pytest.raises(IntegrityError):
            await run_in_clean_transaction(RetrySession(), operation)  # type: ignore[arg-type]
        assert attempts == 1
        assert not is_retryable_generated_code_collision(error, ())
        assert is_retryable_generated_code_collision(
            error,
            ("INV",) if constraint_name.endswith("invoices_org_code") else ("BIL",),
        )


async def test_check_constraint_error_is_not_retried(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    organization_id, _ = test_organizations
    attempts = 0

    async def operation(session: AsyncSession) -> None:
        nonlocal attempts
        attempts += 1
        session.add(
            Transaction(
                organization_id=organization_id,
                transaction_code="TRX-2026-000001",
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=BUSINESS_DATE,
                amount=Decimal("-1.00"),
                currency="IDR",
                workflow_status=WorkflowStatus.APPROVED,
                description="CP5 non-retryable check violation",
            )
        )
        await session.flush()

    async with pg_session_factory() as session:
        with pytest.raises(IntegrityError):
            await run_in_clean_transaction(session, operation)

    assert attempts == 1


async def test_retry_rolls_back_complete_financial_side_effect_graph(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    """A journal-code collision removes every failed-attempt financial side effect."""
    from src.models.audit import AuditLog
    from src.models.coa import ChartOfAccount, PaymentAccount
    from src.models.enums import (
        AccountType,
        MovementDirection,
        MovementSourceType,
        NormalBalance,
        SettlementType,
    )
    from src.models.journal import JournalEntry, JournalLine
    from src.models.money_movement import Settlement, SettlementAllocation, MoneyMovement
    from src.models.transaction import TransactionAllocation
    from src.services.accounting_engine import AccountingEngine

    organization_id, _ = test_organizations
    conflict_transaction_id = uuid4()
    conflict_journal_id = uuid4()
    conflict_journal_number = f"JE-2026-{uuid4().hex[:6]}"

    async with pg_session_factory() as session:
        account = ChartOfAccount(
            organization_id=organization_id,
            account_code="CP5-1101",
            account_name="CP5 test cash",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="ASSETS",
        )
        session.add(account)
        await session.flush()
        payment_account = PaymentAccount(
            organization_id=organization_id,
            coa_account_id=account.id,
            name="CP5 test bank",
        )
        conflict_transaction = Transaction(
            id=conflict_transaction_id,
            organization_id=organization_id,
            transaction_code="TRX-2026-900000",
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=BUSINESS_DATE,
            amount=Decimal("100.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.POSTED,
            description="CP5 journal collision fixture",
        )
        session.add_all([payment_account, conflict_transaction])
        await session.flush()
        session.add(
            JournalEntry(
                id=conflict_journal_id,
                organization_id=organization_id,
                entry_number=conflict_journal_number,
                transaction_id=conflict_transaction_id,
                posting_date=BUSINESS_DATE,
                description="CP5 journal collision fixture",
                total_debit=Decimal("100.00"),
                total_credit=Decimal("100.00"),
                is_balanced=True,
            )
        )
        await session.commit()
        account_id = account.id
        payment_account_id = payment_account.id

    attempts = 0
    successful_transaction_id: UUID | None = None

    async def operation(session: AsyncSession) -> UUID:
        nonlocal attempts, successful_transaction_id
        attempts += 1
        transaction_id = uuid4()
        transaction_code = await TransactionService(session).generate_transaction_code(
            organization_id, BUSINESS_DATE
        )
        transaction = Transaction(
            id=transaction_id,
            organization_id=organization_id,
            transaction_code=transaction_code,
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=BUSINESS_DATE,
            amount=Decimal("100.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.POSTED,
            description="CP5 complete graph retry",
        )
        session.add(transaction)
        await session.flush()

        session.add(
            TransactionAllocation(
                transaction_id=transaction_id,
                amount=Decimal("100.00"),
            )
        )
        generated_entry_number = await AccountingEngine(session).generate_entry_number(
            organization_id, BUSINESS_DATE
        )
        entry_number = conflict_journal_number if attempts == 1 else generated_entry_number
        journal = JournalEntry(
            organization_id=organization_id,
            entry_number=entry_number,
            transaction_id=transaction_id,
            posting_date=BUSINESS_DATE,
            description="CP5 complete graph retry",
            total_debit=Decimal("100.00"),
            total_credit=Decimal("100.00"),
            is_balanced=True,
        )
        session.add(journal)
        await session.flush()
        session.add_all([
            JournalLine(
                journal_entry_id=journal.id,
                line_number=1,
                account_id=account_id,
                debit_amount=Decimal("100.00"),
                credit_amount=Decimal("0.00"),
            ),
            JournalLine(
                journal_entry_id=journal.id,
                line_number=2,
                account_id=account_id,
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("100.00"),
            ),
            AuditLog(
                organization_id=organization_id,
                entity_name="Transaction",
                entity_id=transaction_id,
                action="CP5_RETRY_GRAPH",
                new_values={"transaction_code": transaction_code},
            ),
        ])
        movement = MoneyMovement(
            organization_id=organization_id,
            movement_code=f"MM-2026-{900000 + attempts:06d}",
            payment_account_id=payment_account_id,
            direction=MovementDirection.OUT,
            amount=Decimal("100.00"),
            movement_date=BUSINESS_DATE,
            source_type=MovementSourceType.MANUAL,
            description="CP5 complete graph retry",
        )
        session.add(movement)
        await session.flush()
        settlement = Settlement(
            organization_id=organization_id,
            settlement_code=f"SET-{900000 + attempts:06d}",
            money_movement_id=movement.id,
            transaction_id=transaction_id,
            settlement_type=SettlementType.DIRECT_EXPENSE,
            amount=Decimal("100.00"),
        )
        session.add(settlement)
        await session.flush()
        session.add(
            SettlementAllocation(
                settlement_id=settlement.id,
                amount=Decimal("100.00"),
            )
        )
        await session.flush()
        successful_transaction_id = transaction_id
        return transaction_id

    try:
        async with pg_session_factory() as session:
            result = await run_in_clean_transaction(session, operation)
            await session.commit()

        assert attempts == 2
        assert result == successful_transaction_id
        async with pg_session_factory() as session:
            assert await session.scalar(
                select(func.count()).select_from(Transaction).where(
                    Transaction.organization_id == organization_id,
                    Transaction.description == "CP5 complete graph retry",
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(TransactionAllocation).where(
                    TransactionAllocation.transaction_id == result,
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(JournalEntry).where(
                    JournalEntry.transaction_id == result,
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(JournalLine).join(JournalEntry).where(
                    JournalEntry.transaction_id == result,
                )
            ) == 2
            assert await session.scalar(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.entity_id == result,
                    AuditLog.action == "CP5_RETRY_GRAPH",
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(MoneyMovement).where(
                    MoneyMovement.organization_id == organization_id,
                    MoneyMovement.description == "CP5 complete graph retry",
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(Settlement).where(
                    Settlement.transaction_id == result,
                )
            ) == 1
            assert await session.scalar(
                select(func.count()).select_from(SettlementAllocation).join(Settlement).where(
                    Settlement.transaction_id == result,
                )
            ) == 1
    finally:
        async with pg_session_factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM settlement_allocations WHERE settlement_id IN (SELECT id FROM settlements WHERE organization_id = :org_id)"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM settlements WHERE organization_id = :org_id"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM money_movements WHERE organization_id = :org_id AND description = 'CP5 complete graph retry'"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM journal_lines WHERE journal_entry_id IN (SELECT id FROM journal_entries WHERE organization_id = :org_id)"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM journal_entries WHERE organization_id = :org_id"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM audit_logs WHERE organization_id = :org_id AND action = 'CP5_RETRY_GRAPH'"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM transaction_allocations WHERE transaction_id IN (SELECT id FROM transactions WHERE organization_id = :org_id)"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM transactions WHERE organization_id = :org_id AND description IN ('CP5 journal collision fixture', 'CP5 complete graph retry')"),
                {"org_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM payment_accounts WHERE id = :payment_account_id"),
                {"payment_account_id": payment_account_id},
            )
            await session.execute(
                text("DELETE FROM chart_of_accounts WHERE id = :account_id"),
                {"account_id": account_id},
            )
