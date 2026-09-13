"""RECON-001 Database Constraint & Invariant Regression Suite.

Verifies schema-level defense-in-depth:
1. ck_bank_recon_exactly_one_target (rejects zero-target and multi-target records)
2. ck_bank_recon_matched_amount_positive (rejects <= 0 matched_amount)
3. uq_bank_reconciliations_statement_line (rejects duplicate active statement lines)
4. uq_bank_reconciliations_journal_line (rejects duplicate active journal lines)
5. uq_bank_reconciliations_money_movement (rejects duplicate active money movements)
6. uq_bank_reconciliations_transaction (rejects duplicate active transactions)
7. Allows distinct targets and non-MATCHED historical records
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator, Dict, Any

import pytest
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.models.bank_reconciliation import (
    BankStatementImport,
    BankStatementLine,
    BankReconciliation,
)
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    AccountType,
    MovementDirection,
    MovementSourceType,
    NormalBalance,
    ReconciliationStatus,
    StatementImportStatus,
    TransactionType,
    WorkflowStatus,
)
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement
from src.models.organization import Organization
from src.models.transaction import Transaction


@pytest.fixture
async def db_fixture() -> AsyncGenerator[Dict[str, Any], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        org = Organization(
            id=uuid.uuid4(),
            slug=f"db-test-org-{uuid.uuid4().hex[:6]}",
            legal_name="DB Constraint Test PT",
        )
        session.add(org)
        await session.flush()

        coa = ChartOfAccount(
            id=uuid.uuid4(),
            organization_id=org.id,
            account_code="1101",
            account_name="Kas dan Bank",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="Aset Lancar",
            is_active=True,
        )
        session.add(coa)
        await session.flush()

        pay_acc = PaymentAccount(
            id=uuid.uuid4(),
            organization_id=org.id,
            coa_account_id=coa.id,
            name="Bank Test",
            is_active=True,
        )
        session.add(pay_acc)
        await session.flush()

        stmt_import = BankStatementImport(
            id=uuid.uuid4(),
            organization_id=org.id,
            payment_account_id=pay_acc.id,
            file_hash=f"hash-{uuid.uuid4().hex}",
            source_file="test.csv",
            status=StatementImportStatus.COMPLETED,
        )
        session.add(stmt_import)
        await session.flush()

        line1 = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import.id,
            organization_id=org.id,
            line_number=1,
            transaction_date=date(2026, 9, 1),
            description="Test line 1",
            debit=Decimal("1000.00"),
            credit=Decimal("0.00"),
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        line2 = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import.id,
            organization_id=org.id,
            line_number=2,
            transaction_date=date(2026, 9, 1),
            description="Test line 2",
            debit=Decimal("2000.00"),
            credit=Decimal("0.00"),
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        line3 = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import.id,
            organization_id=org.id,
            line_number=3,
            transaction_date=date(2026, 9, 1),
            description="Test line 3",
            debit=Decimal("3000.00"),
            credit=Decimal("0.00"),
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        session.add_all([line1, line2, line3])
        await session.flush()

        tx1 = Transaction(
            id=uuid.uuid4(),
            organization_id=org.id,
            transaction_code=f"TX-{uuid.uuid4().hex[:8]}",
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("1000.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description="Tx 1",
        )
        tx2 = Transaction(
            id=uuid.uuid4(),
            organization_id=org.id,
            transaction_code=f"TX-{uuid.uuid4().hex[:8]}",
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("2000.00"),
            workflow_status=WorkflowStatus.APPROVED,
            description="Tx 2",
        )
        session.add_all([tx1, tx2])
        await session.flush()

        je = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org.id,
            entry_number=f"JE-{uuid.uuid4().hex[:8]}",
            transaction_id=tx1.id,
            posting_date=date(2026, 9, 1),
            description="JE 1",
            total_debit=Decimal("1000.00"),
            total_credit=Decimal("1000.00"),
            is_balanced=True,
        )
        session.add(je)
        await session.flush()

        jl1 = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je.id,
            line_number=1,
            account_id=coa.id,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("1000.00"),
            payment_account_id=pay_acc.id,
        )
        jl2 = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je.id,
            line_number=2,
            account_id=coa.id,
            debit_amount=Decimal("1000.00"),
            credit_amount=Decimal("0.00"),
        )
        session.add_all([jl1, jl2])
        await session.flush()

        mm1 = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org.id,
            movement_code=f"MM-{uuid.uuid4().hex[:8]}",
            payment_account_id=pay_acc.id,
            direction=MovementDirection.OUT,
            amount=Decimal("1000.00"),
            movement_date=date(2026, 9, 1),
            source_type=MovementSourceType.MANUAL,
        )
        mm2 = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org.id,
            movement_code=f"MM-{uuid.uuid4().hex[:8]}",
            payment_account_id=pay_acc.id,
            direction=MovementDirection.OUT,
            amount=Decimal("2000.00"),
            movement_date=date(2026, 9, 1),
            source_type=MovementSourceType.MANUAL,
        )
        session.add_all([mm1, mm2])
        await session.commit()

    yield {
        "session_factory": session_factory,
        "org_id": org.id,
        "lines": [line1, line2, line3],
        "jl": jl1,
        "mm": [mm1, mm2],
        "tx": [tx1, tx2],
    }
    await engine.dispose()


@pytest.mark.asyncio
async def test_db_check_zero_targets_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with 0 targets MUST fail ck_bank_recon_exactly_one_target."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=None,
            money_movement_id=None,
            transaction_id=None,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST",
        )
        session.add(recon)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "ck_bank_recon_exactly_one_target" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_check_multiple_targets_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with >1 target MUST fail ck_bank_recon_exactly_one_target."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=db_fixture["jl"].id,
            money_movement_id=db_fixture["mm"][0].id,
            transaction_id=None,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST",
        )
        session.add(recon)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "ck_bank_recon_exactly_one_target" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_check_matched_amount_positive_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with matched_amount <= 0 MUST fail ck_bank_recon_matched_amount_positive."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=db_fixture["jl"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("0.00"),
            match_rule="DIRECT_TEST",
        )
        session.add(recon)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "ck_bank_recon_matched_amount_positive" in str(exc_info.value).lower() or "check" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_unique_statement_line_duplicate_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with duplicate active statement_line_id MUST fail uq_bank_reconciliations_statement_line."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=db_fixture["jl"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_1",
        )
        session.add(recon1)
        await session.commit()

    async with session_factory() as session:
        recon2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            money_movement_id=db_fixture["mm"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_2",
        )
        session.add(recon2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "unique" in str(exc_info.value).lower() or "uq_bank_reconciliations_statement_line" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_unique_journal_line_duplicate_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with duplicate active journal_line_id MUST fail uq_bank_reconciliations_journal_line."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=db_fixture["jl"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_1",
        )
        session.add(recon1)
        await session.commit()

    async with session_factory() as session:
        recon2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][1].id,
            journal_line_id=db_fixture["jl"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_2",
        )
        session.add(recon2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "unique" in str(exc_info.value).lower() or "uq_bank_reconciliations_journal_line" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_unique_money_movement_duplicate_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with duplicate active money_movement_id MUST fail uq_bank_reconciliations_money_movement."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            money_movement_id=db_fixture["mm"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_1",
        )
        session.add(recon1)
        await session.commit()

    async with session_factory() as session:
        recon2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][1].id,
            money_movement_id=db_fixture["mm"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_2",
        )
        session.add(recon2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "unique" in str(exc_info.value).lower() or "uq_bank_reconciliations_money_movement" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_unique_transaction_duplicate_rejected(db_fixture: Dict[str, Any]):
    """Direct database insert with duplicate active transaction_id MUST fail uq_bank_reconciliations_transaction."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            transaction_id=db_fixture["tx"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_1",
        )
        session.add(recon1)
        await session.commit()

    async with session_factory() as session:
        recon2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][1].id,
            transaction_id=db_fixture["tx"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_2",
        )
        session.add(recon2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "unique" in str(exc_info.value).lower() or "uq_bank_reconciliations_transaction" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_db_different_targets_and_lines_succeeds(db_fixture: Dict[str, Any]):
    """Distinct statement lines and distinct targets must persist successfully."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        recon1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][0].id,
            journal_line_id=db_fixture["jl"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("1000.00"),
            match_rule="DIRECT_TEST_1",
        )
        recon2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][1].id,
            money_movement_id=db_fixture["mm"][0].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("2000.00"),
            match_rule="DIRECT_TEST_2",
        )
        recon3 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=db_fixture["org_id"],
            statement_line_id=db_fixture["lines"][2].id,
            transaction_id=db_fixture["tx"][1].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("2000.00"),
            match_rule="DIRECT_TEST_3",
        )
        session.add_all([recon1, recon2, recon3])
        await session.commit()

        count = await session.scalar(select(func.count(BankReconciliation.id)))
        assert count == 3


@pytest.mark.asyncio
async def test_db_partial_unique_indexes_allow_inactive_history(db_fixture: Dict[str, Any]):
    """Historical non-MATCHED records do not claim active statement lines or targets."""
    session_factory = db_fixture["session_factory"]
    async with session_factory() as session:
        session.add_all(
            [
                BankReconciliation(
                    id=uuid.uuid4(),
                    organization_id=db_fixture["org_id"],
                    statement_line_id=db_fixture["lines"][0].id,
                    journal_line_id=db_fixture["jl"].id,
                    status=ReconciliationStatus.PARTIAL_MATCH,
                    matched_amount=Decimal("1000.00"),
                    match_rule="HISTORICAL_TEST_1",
                ),
                BankReconciliation(
                    id=uuid.uuid4(),
                    organization_id=db_fixture["org_id"],
                    statement_line_id=db_fixture["lines"][0].id,
                    journal_line_id=db_fixture["jl"].id,
                    status=ReconciliationStatus.PARTIAL_MATCH,
                    matched_amount=Decimal("1000.00"),
                    match_rule="HISTORICAL_TEST_2",
                ),
            ]
        )
        await session.commit()

        count = await session.scalar(select(func.count(BankReconciliation.id)))
        assert count == 2
