"""RECON-001 PostgreSQL migration and concurrent constraint regressions."""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.bank_reconciliation import BankReconciliation, BankStatementImport, BankStatementLine
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    AccountType,
    NormalBalance,
    ReconciliationStatus,
    StatementImportStatus,
    TransactionType,
    WorkflowStatus,
)
from src.models.organization import Organization
from src.models.transaction import Transaction

POSTGRES_URL_ENV = "RECON_001_TEST_DATABASE_URL"
EXPECTED_ALEMBIC_HEAD = "028_document_posting_linkage"

pytestmark = pytest.mark.postgresql


def require_recon_postgres_url() -> str:
    url = os.environ.get(POSTGRES_URL_ENV)
    if not url:
        pytest.skip(f"{POSTGRES_URL_ENV} is required for RECON-001 PostgreSQL integration tests")

    parsed = urlsplit(url)
    database_name = (parsed.path or "").lstrip("/").lower()
    if parsed.scheme != "postgresql+asyncpg" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        pytest.fail(f"Refusing {POSTGRES_URL_ENV}: use a local postgresql+asyncpg disposable database")
    if not any(token in database_name for token in ("recon", "test", "disposable")):
        pytest.fail(f"Refusing {POSTGRES_URL_ENV}: database name must identify a disposable test database")
    return url


@pytest.fixture
async def pg_session_factory():
    engine = create_async_engine(require_recon_postgres_url(), pool_size=25, max_overflow=5)
    try:
        async with engine.connect() as connection:
            version = int(await connection.scalar(text("SHOW server_version_num")) or 0)
            assert version >= 160000
            assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == EXPECTED_ALEMBIC_HEAD
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def recon_seed(pg_session_factory: async_sessionmaker[AsyncSession]):
    organization_id = uuid4()
    transaction_ids = [uuid4() for _ in range(20)]

    async with pg_session_factory() as session:
        organization = Organization(
            id=organization_id,
            slug=f"recon-pg-{organization_id.hex[:12]}",
            legal_name="RECON-001 PostgreSQL Test Organization",
        )
        cash_coa = ChartOfAccount(
            id=uuid4(),
            organization_id=organization_id,
            account_code=f"1101-{organization_id.hex[:6]}",
            account_name="Kas dan Bank",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="Aset Lancar",
            is_active=True,
        )
        payment_account = PaymentAccount(
            id=uuid4(),
            organization_id=organization_id,
            coa_account_id=cash_coa.id,
            name="RECON-001 Test Bank",
            is_active=True,
        )
        statement_import = BankStatementImport(
            id=uuid4(),
            organization_id=organization_id,
            payment_account_id=payment_account.id,
            file_hash=f"recon-{organization_id.hex}",
            source_file="recon-001-postgresql.csv",
            status=StatementImportStatus.COMPLETED,
        )
        statement_line_ids = [uuid4() for _ in range(20)]
        statement_lines = [
            BankStatementLine(
                id=statement_line_id,
                import_id=statement_import.id,
                organization_id=organization_id,
                line_number=index,
                transaction_date=date(2026, 9, 13),
                description="RECON-001 concurrent match target",
                debit=Decimal("0.00"),
                credit=Decimal("1000.00"),
                reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
            )
            for index, statement_line_id in enumerate(statement_line_ids, start=1)
        ]
        transactions = [
            Transaction(
                id=transaction_id,
                organization_id=organization_id,
                transaction_code=f"RECON-{transaction_id.hex[:12]}",
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2026, 9, 13),
                amount=Decimal("1000.00"),
                workflow_status=WorkflowStatus.APPROVED,
                description="RECON-001 concurrent target",
            )
            for transaction_id in transaction_ids
        ]
        session.add(organization)
        await session.flush()
        session.add(cash_coa)
        await session.flush()
        session.add(payment_account)
        await session.flush()
        session.add(statement_import)
        await session.flush()
        session.add_all(statement_lines)
        session.add_all(transactions)
        await session.commit()

    try:
        yield organization_id, statement_line_ids, transaction_ids
    finally:
        async with pg_session_factory() as session:
            await session.execute(
                text("DELETE FROM bank_reconciliations WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await session.execute(
                text(
                    "DELETE FROM bank_statement_lines WHERE organization_id = :organization_id"
                ),
                {"organization_id": organization_id},
            )
            await session.execute(
                text(
                    "DELETE FROM bank_statement_imports WHERE organization_id = :organization_id"
                ),
                {"organization_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM transactions WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM payment_accounts WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM chart_of_accounts WHERE organization_id = :organization_id"),
                {"organization_id": organization_id},
            )
            await session.execute(
                text("DELETE FROM organizations WHERE id = :organization_id"),
                {"organization_id": organization_id},
            )
            await session.commit()


async def test_postgresql_recon_constraints_and_partial_indexes_are_applied(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expected_indexes = {
        "uq_bank_reconciliations_statement_line": "WHERE ((status)::text = 'MATCHED'::text)",
        "uq_bank_reconciliations_journal_line": "WHERE ((journal_line_id IS NOT NULL) AND ((status)::text = 'MATCHED'::text))",
        "uq_bank_reconciliations_money_movement": "WHERE ((money_movement_id IS NOT NULL) AND ((status)::text = 'MATCHED'::text))",
        "uq_bank_reconciliations_transaction": "WHERE ((transaction_id IS NOT NULL) AND ((status)::text = 'MATCHED'::text))",
    }

    async with pg_session_factory() as session:
        indexes = dict(
            (
                await session.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname = 'public' "
                        "AND tablename = 'bank_reconciliations' "
                        "AND indexname = ANY(:names)"
                    ),
                    {"names": list(expected_indexes)},
                )
            ).all()
        )
        assert indexes.keys() == expected_indexes.keys()
        for index_name, predicate in expected_indexes.items():
            assert "CREATE UNIQUE INDEX" in indexes[index_name]
            assert predicate in indexes[index_name]

        constraints = dict(
            (
                await session.execute(
                    text(
                        "SELECT conname, pg_get_constraintdef(oid) "
                        "FROM pg_constraint "
                        "WHERE conrelid = 'public.bank_reconciliations'::regclass "
                        "AND conname = ANY(:names)"
                    ),
                    {
                        "names": [
                            "ck_bank_recon_exactly_one_target",
                            "ck_bank_recon_matched_amount_positive",
                        ]
                    },
                )
            ).all()
        )
        exactly_one_target = " ".join(
            constraints["ck_bank_recon_exactly_one_target"].split()
        )
        assert "journal_line_id IS NOT NULL" in exactly_one_target
        assert "money_movement_id IS NOT NULL" in exactly_one_target
        assert "transaction_id IS NOT NULL" in exactly_one_target
        assert "= 1" in exactly_one_target
        assert "matched_amount >" in constraints["ck_bank_recon_matched_amount_positive"]

        workflow_status_labels = set(
            (
                await session.execute(
                    text(
                        "SELECT enumlabel FROM pg_enum "
                        "WHERE enumtypid = 'workflow_status'::regtype"
                    )
                )
            ).scalars()
        )
        assert "REJECTED" in workflow_status_labels


async def test_postgresql_concurrent_duplicate_statement_match_fails_closed(
    pg_session_factory: async_sessionmaker[AsyncSession],
    recon_seed: tuple[UUID, list[UUID], list[UUID]],
) -> None:
    organization_id, statement_line_ids, transaction_ids = recon_seed
    statement_line_id = statement_line_ids[0]
    barrier = asyncio.Barrier(len(transaction_ids))

    async def worker(transaction_id: UUID) -> bool:
        async with pg_session_factory() as session:
            await barrier.wait()
            session.add(
                BankReconciliation(
                    id=uuid4(),
                    organization_id=organization_id,
                    statement_line_id=statement_line_id,
                    transaction_id=transaction_id,
                    status=ReconciliationStatus.MATCHED,
                    matched_amount=Decimal("1000.00"),
                    match_rule="POSTGRESQL_RACE_TEST",
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(*(worker(transaction_id) for transaction_id in transaction_ids))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == len(transaction_ids) - 1

    async with pg_session_factory() as session:
        persisted = await session.scalar(
            select(func.count(BankReconciliation.id)).where(
                BankReconciliation.organization_id == organization_id,
                BankReconciliation.statement_line_id == statement_line_id,
                BankReconciliation.status == ReconciliationStatus.MATCHED,
            )
        )
        assert persisted == 1


async def test_postgresql_concurrent_duplicate_target_match_fails_closed(
    pg_session_factory: async_sessionmaker[AsyncSession],
    recon_seed: tuple[UUID, list[UUID], list[UUID]],
) -> None:
    organization_id, statement_line_ids, transaction_ids = recon_seed
    transaction_id = transaction_ids[0]
    barrier = asyncio.Barrier(len(statement_line_ids))

    async def worker(statement_line_id: UUID) -> bool:
        async with pg_session_factory() as session:
            await barrier.wait()
            session.add(
                BankReconciliation(
                    id=uuid4(),
                    organization_id=organization_id,
                    statement_line_id=statement_line_id,
                    transaction_id=transaction_id,
                    status=ReconciliationStatus.MATCHED,
                    matched_amount=Decimal("1000.00"),
                    match_rule="POSTGRESQL_TARGET_RACE_TEST",
                )
            )
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(*(worker(statement_line_id) for statement_line_id in statement_line_ids))
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == len(statement_line_ids) - 1

    async with pg_session_factory() as session:
        persisted = await session.scalar(
            select(func.count(BankReconciliation.id)).where(
                BankReconciliation.organization_id == organization_id,
                BankReconciliation.transaction_id == transaction_id,
                BankReconciliation.status == ReconciliationStatus.MATCHED,
            )
        )
        assert persisted == 1
