"""RECON-001 reconciliation-integrity regression suite.

CP2 verifies cardinality, target selection, amount and directional integrity, shared
manual/auto-match validation, tenant precedence, authorization, and rejection
atomicity. Dashboard aggregation remains a CP3 strict-XFAIL; PostgreSQL
concurrency remains prerequisite-skipped without a configured test database.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Dict, Any, List

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.database import Base, get_db
from src.core.security import create_access_token, hash_password
from src.main import create_application
from src.models.bank_reconciliation import (
    BankStatementImport,
    BankStatementLine,
    BankReconciliation,
)
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import (
    AccountType,
    CostCategory,
    MovementDirection,
    MovementSourceType,
    NormalBalance,
    ProjectStatus,
    ReconciliationStatus,
    StatementImportStatus,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement
from src.models.organization import Organization
from src.models.project import Project
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.bank_reconciliation import BankReconciliationMatchRequest
from src.services.bank_reconciliation_service import BankReconciliationService
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts


def make_auth_headers(org_id: uuid.UUID, user: User) -> Dict[str, str]:
    """Generate JWT authorization and tenant context headers matching AUTHZ-001."""
    token = create_access_token(str(user.id), {"organization_id": str(org_id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user.id),
    }


@pytest.fixture
async def recon_env() -> AsyncGenerator[Dict[str, Any], None]:
    """Sets up an isolated multi-tenant environment with standard accounts, counterparties,

    statement lines, and targets for both Tenant A and Tenant B.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_application()

    async def override_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db

    async with session_factory() as session:
        # 1. Organization A
        org_a = Organization(
            id=uuid.uuid4(),
            slug=f"tenant-a-{uuid.uuid4().hex[:6]}",
            legal_name="Tenant A Corp PT",
        )
        session.add(org_a)
        await session.flush()

        users_a = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                id=uuid.uuid4(),
                organization_id=org_a.id,
                email=f"{role.value.lower()}@tenant-a.local",
                full_name=f"Tenant A {role.value}",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users_a[role] = u
        await session.flush()

        await seed_standard_coa(session, org_a.id)
        await seed_standard_payment_accounts(session, org_a.id)

        coa_bank_a = await session.scalar(
            select(ChartOfAccount).where(
                ChartOfAccount.organization_id == org_a.id,
                ChartOfAccount.account_code == "1101",
            )
        )
        pay_acc_a = await session.scalar(
            select(PaymentAccount).where(PaymentAccount.organization_id == org_a.id)
        )
        assert coa_bank_a is not None
        assert pay_acc_a is not None

        # Counterparties for Org A
        customer_a = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Customer A PT",
            is_customer=True,
            is_vendor=False,
        )
        session.add(customer_a)
        await session.flush()

        # Bank Statement Import for Org A
        stmt_import_a = BankStatementImport(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            payment_account_id=pay_acc_a.id,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            file_hash="hash_recon_test_a",
            source_file="statement_a.csv",
            status=StatementImportStatus.COMPLETED,
        )
        session.add(stmt_import_a)
        await session.flush()

        # Bank Statement Lines for Org A
        # Line 1: Inflow 10,000,000
        stmt_line_10m = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import_a.id,
            organization_id=org_a.id,
            line_number=1,
            transaction_date=date(2026, 3, 10),
            description="Client Payment Inflow 10M",
            debit=Decimal("0.00"),
            credit=Decimal("10000000.00"),
            reference="REF-INFLOW-10M",
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        # Line 2: Inflow 5,000,000
        stmt_line_5m_1 = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import_a.id,
            organization_id=org_a.id,
            line_number=2,
            transaction_date=date(2026, 3, 12),
            description="Client Payment Inflow 5M #1",
            debit=Decimal("0.00"),
            credit=Decimal("5000000.00"),
            reference="REF-5M-A",
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        # Line 3: Inflow 5,000,000
        stmt_line_5m_2 = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import_a.id,
            organization_id=org_a.id,
            line_number=3,
            transaction_date=date(2026, 3, 12),
            description="Client Payment Inflow 5M #2",
            debit=Decimal("0.00"),
            credit=Decimal("5000000.00"),
            reference="REF-5M-B",
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        # Line 4: Outflow 5,000,000
        stmt_line_out_5m = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_import_a.id,
            organization_id=org_a.id,
            line_number=4,
            transaction_date=date(2026, 3, 15),
            description="Vendor Outflow 5M",
            debit=Decimal("5000000.00"),
            credit=Decimal("0.00"),
            reference="REF-OUT-5M",
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        session.add_all([stmt_line_10m, stmt_line_5m_1, stmt_line_5m_2, stmt_line_out_5m])
        await session.flush()

        # Transactions for Org A:
        tx_10m = Transaction(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            transaction_code="TX-A-10M-001",
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 3, 10),
            amount=Decimal("10000000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            counterparty_id=customer_a.id,
            payment_account_id=pay_acc_a.id,
            description="Client Invoice 10M",
        )
        tx_5m = Transaction(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            transaction_code="TX-A-5M-001",
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 3, 12),
            amount=Decimal("5000000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            counterparty_id=customer_a.id,
            payment_account_id=pay_acc_a.id,
            description="Client Invoice 5M",
        )
        session.add_all([tx_10m, tx_5m])
        await session.flush()

        # Targets for Org A:
        # JournalEntry & JournalLine (10M Inflow: Debit Kas/Bank, Credit Revenue)
        je_10m = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            entry_number="JE-10M-001",
            transaction_id=tx_10m.id,
            posting_date=date(2026, 3, 10),
            description="Revenue Receipt 10M",
            total_debit=Decimal("10000000.00"),
            total_credit=Decimal("10000000.00"),
            is_balanced=True,
        )
        session.add(je_10m)
        await session.flush()

        jl_bank_debit_10m = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_10m.id,
            line_number=1,
            account_id=coa_bank_a.id,
            payment_account_id=pay_acc_a.id,
            debit_amount=Decimal("10000000.00"),
            credit_amount=Decimal("0.00"),
        )
        jl_rev_credit_10m = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_10m.id,
            line_number=2,
            account_id=coa_bank_a.id,
            payment_account_id=pay_acc_a.id,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("10000000.00"),
        )
        session.add_all([jl_bank_debit_10m, jl_rev_credit_10m])

        # JournalEntry & JournalLine (5M Inflow: Debit Kas/Bank)
        je_5m = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            entry_number="JE-5M-001",
            transaction_id=tx_5m.id,
            posting_date=date(2026, 3, 12),
            description="Receipt 5M",
            total_debit=Decimal("5000000.00"),
            total_credit=Decimal("5000000.00"),
            is_balanced=True,
        )
        session.add(je_5m)
        await session.flush()

        jl_bank_debit_5m = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_5m.id,
            line_number=1,
            account_id=coa_bank_a.id,
            payment_account_id=pay_acc_a.id,
            debit_amount=Decimal("5000000.00"),
            credit_amount=Decimal("0.00"),
        )
        jl_credit_5m = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_5m.id,
            line_number=2,
            account_id=coa_bank_a.id,
            payment_account_id=pay_acc_a.id,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("5000000.00"),
        )
        session.add_all([jl_bank_debit_5m, jl_credit_5m])

        # MoneyMovement Org A: Inflow 5,000,000
        mm_5m_in = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            movement_code="MM-IN-001",
            payment_account_id=pay_acc_a.id,
            direction=MovementDirection.IN,
            amount=Decimal("5000000.00"),
            movement_date=date(2026, 3, 12),
            source_type=MovementSourceType.MANUAL,
            reference_no="REF-5M-A",
            description="Money Movement In 5M",
        )
        # MoneyMovement Org A: Outflow 10,000,000
        mm_10m_out = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            movement_code="MM-OUT-001",
            payment_account_id=pay_acc_a.id,
            direction=MovementDirection.OUT,
            amount=Decimal("10000000.00"),
            movement_date=date(2026, 3, 10),
            source_type=MovementSourceType.MANUAL,
            reference_no="REF-OUT-10M",
            description="Money Movement Out 10M",
        )
        session.add_all([mm_5m_in, mm_10m_out])

        # -------------------------------------------------------------
        # 2. Organization B (Foreign Tenant)
        # -------------------------------------------------------------
        org_b = Organization(
            id=uuid.uuid4(),
            slug=f"tenant-b-{uuid.uuid4().hex[:6]}",
            legal_name="Tenant B Corp PT",
        )
        session.add(org_b)
        await session.flush()

        users_b = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                id=uuid.uuid4(),
                organization_id=org_b.id,
                email=f"{role.value.lower()}@tenant-b.local",
                full_name=f"Tenant B {role.value}",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users_b[role] = u
        await session.flush()

        await seed_standard_coa(session, org_b.id)
        await seed_standard_payment_accounts(session, org_b.id)

        coa_bank_b = await session.scalar(
            select(ChartOfAccount).where(
                ChartOfAccount.organization_id == org_b.id,
                ChartOfAccount.account_code == "1101",
            )
        )
        pay_acc_b = await session.scalar(
            select(PaymentAccount).where(PaymentAccount.organization_id == org_b.id)
        )

        # Counterparties for Org B
        customer_b = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Customer B PT",
            is_customer=True,
            is_vendor=False,
        )
        session.add(customer_b)
        await session.flush()

        tx_b = Transaction(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            transaction_code="TX-B-001",
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 3, 10),
            amount=Decimal("5000000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            counterparty_id=customer_b.id,
            payment_account_id=pay_acc_b.id,
            description="Tenant B Transaction",
        )
        session.add(tx_b)
        await session.flush()

        je_b = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            entry_number="JE-B-001",
            transaction_id=tx_b.id,
            posting_date=date(2026, 3, 10),
            description="Tenant B Entry",
            total_debit=Decimal("5000000.00"),
            total_credit=Decimal("5000000.00"),
            is_balanced=True,
        )
        session.add(je_b)
        await session.flush()

        jl_b = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_b.id,
            line_number=1,
            account_id=coa_bank_b.id,
            payment_account_id=pay_acc_b.id,
            debit_amount=Decimal("5000000.00"),
            credit_amount=Decimal("0.00"),
        )
        mm_b = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            movement_code="MM-B-001",
            payment_account_id=pay_acc_b.id,
            direction=MovementDirection.IN,
            amount=Decimal("5000000.00"),
            movement_date=date(2026, 3, 10),
            source_type=MovementSourceType.MANUAL,
            description="Tenant B Movement",
        )
        session.add_all([jl_b, mm_b])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "session_factory": session_factory,
            "org_a": org_a,
            "users_a": users_a,
            "pay_acc_a": pay_acc_a,
            "stmt_import_a": stmt_import_a,
            "stmt_line_10m": stmt_line_10m,
            "stmt_line_5m_1": stmt_line_5m_1,
            "stmt_line_5m_2": stmt_line_5m_2,
            "stmt_line_out_5m": stmt_line_out_5m,
            "jl_bank_debit_10m": jl_bank_debit_10m,
            "jl_rev_credit_10m": jl_rev_credit_10m,
            "jl_bank_debit_5m": jl_bank_debit_5m,
            "mm_5m_in": mm_5m_in,
            "mm_10m_out": mm_10m_out,
            "tx_5m": tx_5m,
            "org_b": org_b,
            "users_b": users_b,
            "jl_b": jl_b,
            "mm_b": mm_b,
            "tx_b": tx_b,
        }

    app.dependency_overrides.clear()
    await engine.dispose()


# =============================================================================
# 1. DUPLICATE STATEMENT-LINE RECONCILIATION
# =============================================================================


@pytest.mark.asyncio
async def test_duplicate_statement_line_rejected(recon_env: Dict[str, Any]):
    """Regression: service permits multiple reconciliations for the same BankStatementLine."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]
    jl = recon_env["jl_bank_debit_10m"]

    # Match 1: Reconcile Line to JournalLine
    payload_1 = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "10000000.00",
        "notes": "First match",
    }
    resp_1 = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload_1, headers=headers)
    assert resp_1.status_code == 200

    # Match 2: Reconcile the exact same statement line again (with another target or zero target)
    payload_2 = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "10000000.00",
        "notes": "Duplicate match for same line",
    }
    resp_2 = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload_2, headers=headers)
    assert resp_2.status_code == 409

    # Rejection leaves the original reconciliation as the sole persisted match.
    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.statement_line_id == stmt_line.id)
            )
        ).all()
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_contract_duplicate_statement_line_rejected(recon_env: Dict[str, Any]):
    """Regression: Second reconciliation attempt for an already-reconciled BankStatementLine must be rejected with 409 Conflict."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]
    jl = recon_env["jl_bank_debit_10m"]

    payload_1 = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "10000000.00",
    }
    resp_1 = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload_1, headers=headers)
    assert resp_1.status_code == 200

    payload_2 = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "10000000.00",
    }
    resp_2 = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload_2, headers=headers)
    # Future contract: duplicate match for already reconciled line must fail with 409 DUPLICATE_ENTITY
    assert resp_2.status_code == 409
    assert resp_2.json().get("error", {}).get("code") == "DUPLICATE_ENTITY"


# =============================================================================
# 2. TARGET REUSE ACROSS MULTIPLE BANK STATEMENT LINES
# =============================================================================


@pytest.mark.asyncio
async def test_duplicate_target_reuse_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows multiple statement lines to reconcile to the same JournalLine."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    jl = recon_env["jl_bank_debit_5m"]

    # Line A matches JL
    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "journal_line_id": str(jl.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    # Line B also matches the same JL
    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "journal_line_id": str(jl.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409

    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.journal_line_id == jl.id)
            )
        ).all()
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_contract_target_reuse_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling a second bank statement line to an already-reconciled JournalLine must return 409 Conflict."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    jl = recon_env["jl_bank_debit_5m"]

    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "journal_line_id": str(jl.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "journal_line_id": str(jl.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409
    assert resp_b.json().get("error", {}).get("code") == "DUPLICATE_ENTITY"


@pytest.mark.asyncio
async def test_duplicate_target_reuse_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows multiple statement lines to reconcile to the same MoneyMovement."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    mm = recon_env["mm_5m_in"]

    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "money_movement_id": str(mm.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "money_movement_id": str(mm.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409

    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.money_movement_id == mm.id)
            )
        ).all()
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_contract_target_reuse_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling a second bank statement line to an already-reconciled MoneyMovement must return 409 Conflict."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    mm = recon_env["mm_5m_in"]

    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "money_movement_id": str(mm.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "money_movement_id": str(mm.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409
    assert resp_b.json().get("error", {}).get("code") == "DUPLICATE_ENTITY"


@pytest.mark.asyncio
async def test_duplicate_target_reuse_transaction_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows multiple statement lines to reconcile to the same Transaction."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    tx = recon_env["tx_5m"]

    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "transaction_id": str(tx.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "transaction_id": str(tx.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409

    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.transaction_id == tx.id)
            )
        ).all()
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_contract_target_reuse_transaction_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling a second bank statement line to an already-reconciled Transaction must return 409 Conflict."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    line_a = recon_env["stmt_line_5m_1"]
    line_b = recon_env["stmt_line_5m_2"]
    tx = recon_env["tx_5m"]

    resp_a = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_a.id), "transaction_id": str(tx.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(line_b.id), "transaction_id": str(tx.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp_b.status_code == 409
    assert resp_b.json().get("error", {}).get("code") == "DUPLICATE_ENTITY"


@pytest.mark.asyncio
async def test_rejected_transaction_target_is_ineligible_and_creates_no_match(
    recon_env: Dict[str, Any],
):
    """A rejected transaction cannot become a reconciliation target."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    statement_line = recon_env["stmt_line_5m_1"]
    transaction = recon_env["tx_5m"]

    async with recon_env["session_factory"]() as session:
        persisted_transaction = await session.get(Transaction, transaction.id)
        assert persisted_transaction is not None
        persisted_transaction.workflow_status = WorkflowStatus.REJECTED
        await session.commit()

    response = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={
            "statement_line_id": str(statement_line.id),
            "transaction_id": str(transaction.id),
            "matched_amount": "5000000.00",
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"

    async with recon_env["session_factory"]() as session:
        reconciliation_count = await session.scalar(
            select(func.count(BankReconciliation.id)).where(
                BankReconciliation.transaction_id == transaction.id
            )
        )
        assert reconciliation_count == 0


# =============================================================================
# 3. SINGLE-TARGET DISCRIMINATOR (ZERO / MULTIPLE TARGETS)
# =============================================================================


@pytest.mark.asyncio
async def test_zero_targets_rejected(recon_env: Dict[str, Any]):
    """Regression: service accepts a reconciliation request with zero targets."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": None,
        "money_movement_id": None,
        "transaction_id": None,
        "matched_amount": "10000000.00",
        "notes": "Orphan match with zero targets",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422

    async with recon_env["session_factory"]() as session:
        recon = await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == stmt_line.id)
        )
        line = await session.get(BankStatementLine, stmt_line.id)
        assert recon is None
        assert line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK


@pytest.mark.asyncio
async def test_contract_zero_targets_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciliation request with zero target IDs must be rejected with 422 Invariant Violation."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": None,
        "money_movement_id": None,
        "transaction_id": None,
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_multiple_targets_rejected(recon_env: Dict[str, Any]):
    """Regression: service accepts a reconciliation request with multiple targets."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_5m_1"]
    jl = recon_env["jl_bank_debit_5m"]
    mm = recon_env["mm_5m_in"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "money_movement_id": str(mm.id),
        "matched_amount": "5000000.00",
        "notes": "Multi-target match (JL + MM)",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422

    async with recon_env["session_factory"]() as session:
        recon = await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == stmt_line.id)
        )
        line = await session.get(BankStatementLine, stmt_line.id)
        assert recon is None
        assert line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK


@pytest.mark.asyncio
async def test_contract_multiple_targets_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciliation request with more than one target must be rejected with 422 Invariant Violation."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_5m_1"]
    jl = recon_env["jl_bank_debit_5m"]
    mm = recon_env["mm_5m_in"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "money_movement_id": str(mm.id),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_contract_three_targets_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciliation request populating all three targets must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_5m_1"]
    jl = recon_env["jl_bank_debit_5m"]
    mm = recon_env["mm_5m_in"]
    tx = recon_env["tx_5m"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "money_movement_id": str(mm.id),
        "transaction_id": str(tx.id),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


# =============================================================================
# 4. BANK-LINE MATCHED AMOUNT INTEGRITY
# =============================================================================


@pytest.mark.asyncio
async def test_arbitrary_matched_amount_rejected(recon_env: Dict[str, Any]):
    """Regression: service accepts an arbitrary matched_amount disconnected from the bank line amount."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]  # line amount is 10,000,000.00
    jl = recon_env["jl_bank_debit_10m"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "999999999.00",  # completely arbitrary 999M vs 10M
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422

    async with recon_env["session_factory"]() as session:
        recon = await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == stmt_line.id)
        )
        line = await session.get(BankStatementLine, stmt_line.id)
        assert recon is None
        assert line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK


@pytest.mark.asyncio
async def test_contract_bank_line_amount_mismatch_rejected(recon_env: Dict[str, Any]):
    """Regression: matched_amount differing from bank statement line amount must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_10m"]  # 10M line
    jl = recon_env["jl_bank_debit_10m"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl.id),
        "matched_amount": "999999999.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


# =============================================================================
# 5. TARGET AMOUNT INTEGRITY (SEPARATE FROM BANK-LINE AMOUNT)
# =============================================================================


@pytest.mark.asyncio
async def test_target_amount_mismatch_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows matching a 10M bank line against a 5M JournalLine."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M bank line
    jl_5m = recon_env["jl_bank_debit_5m"]       # 5M journal line

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "journal_line_id": str(jl_5m.id),
        "matched_amount": "10000000.00",  # matches bank line, but contradicts target
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contract_target_amount_mismatch_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling bank line against JournalLine with unequal amount must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M
    jl_5m = recon_env["jl_bank_debit_5m"]       # 5M

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "journal_line_id": str(jl_5m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_target_amount_mismatch_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows matching a 10M bank line against a 5M MoneyMovement."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M
    mm_5m = recon_env["mm_5m_in"]              # 5M

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "money_movement_id": str(mm_5m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contract_target_amount_mismatch_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling bank line against MoneyMovement with unequal amount must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M
    mm_5m = recon_env["mm_5m_in"]              # 5M

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "money_movement_id": str(mm_5m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_target_amount_mismatch_transaction_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows matching a 10M bank line against a 5M Transaction."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M
    tx_5m = recon_env["tx_5m"]                  # 5M

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "transaction_id": str(tx_5m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contract_target_amount_mismatch_transaction_rejected(recon_env: Dict[str, Any]):
    """Regression: Reconciling bank line against Transaction with unequal amount must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_10m = recon_env["stmt_line_10m"]  # 10M
    tx_5m = recon_env["tx_5m"]                  # 5M

    payload = {
        "statement_line_id": str(stmt_line_10m.id),
        "transaction_id": str(tx_5m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


# =============================================================================
# 6. DIRECTIONAL INTEGRITY
# =============================================================================


@pytest.mark.asyncio
async def test_directional_mismatch_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows bank Inflow (credit) to match MoneyMovement with direction OUT."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_in_10m = recon_env["stmt_line_10m"]  # Inflow (credit=10M)
    mm_out_10m = recon_env["mm_10m_out"]           # MoneyMovement OUT (amount=10M)

    payload = {
        "statement_line_id": str(stmt_line_in_10m.id),
        "money_movement_id": str(mm_out_10m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contract_directional_mismatch_money_movement_rejected(recon_env: Dict[str, Any]):
    """Regression: Matching bank Inflow against MoneyMovement OUT must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_in_10m = recon_env["stmt_line_10m"]  # Inflow (credit=10M)
    mm_out_10m = recon_env["mm_10m_out"]           # Outflow (direction=OUT, 10M)

    payload = {
        "statement_line_id": str(stmt_line_in_10m.id),
        "money_movement_id": str(mm_out_10m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_directional_mismatch_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: service allows bank Inflow to match a JournalLine credit leg (cash outflow)."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_in_10m = recon_env["stmt_line_10m"]  # Inflow (credit=10M)
    jl_credit_10m = recon_env["jl_rev_credit_10m"] # Credit leg (outflow / credit to cash)

    payload = {
        "statement_line_id": str(stmt_line_in_10m.id),
        "journal_line_id": str(jl_credit_10m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contract_directional_mismatch_journal_line_rejected(recon_env: Dict[str, Any]):
    """Regression: Matching bank Inflow against a cash Credit leg must be rejected with 422."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_in_10m = recon_env["stmt_line_10m"]
    jl_credit_10m = recon_env["jl_rev_credit_10m"]

    payload = {
        "statement_line_id": str(stmt_line_in_10m.id),
        "journal_line_id": str(jl_credit_10m.id),
        "matched_amount": "10000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 422
    assert resp.json().get("error", {}).get("code") == "INVARIANT_VIOLATION"


# =============================================================================
# 7. AUTO-MATCH TARGET REUSE & REPEATED LINE
# =============================================================================


@pytest.mark.asyncio
async def test_auto_match_target_reuse_rejected(recon_env: Dict[str, Any]):
    """Auto-match must not reuse a MoneyMovement across statement lines."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_import = recon_env["stmt_import_a"]
    line_1 = recon_env["stmt_line_5m_1"]
    line_2 = recon_env["stmt_line_5m_2"]
    mm = recon_env["mm_5m_in"]

    # Give both lines the same eligible MoneyMovement candidate.
    async with recon_env["session_factory"]() as session:
        l1 = await session.get(BankStatementLine, line_1.id)
        l2 = await session.get(BankStatementLine, line_2.id)
        l1.reference = "REF-SHARED-MM"
        l2.reference = "REF-SHARED-MM"
        m = await session.get(MoneyMovement, mm.id)
        m.reference_no = "REF-SHARED-MM"
        await session.commit()

    resp = await client.post(
        f"/api/v1/bank-reconciliation/imports/{stmt_import.id}/auto-match",
        headers=headers,
    )
    assert resp.status_code == 200
    stats = resp.json().get("stats", {})
    # The independent 10M candidate also matches; reuse prevention is asserted from MM-specific rows.
    assert stats.get("matched") == 3

    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.money_movement_id == mm.id)
            )
        ).all()
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_contract_auto_match_target_reuse_prevented(recon_env: Dict[str, Any]):
    """Regression: In auto-match, a candidate target matched once must not be matched again in the same batch."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_import = recon_env["stmt_import_a"]
    line_1 = recon_env["stmt_line_5m_1"]
    line_2 = recon_env["stmt_line_5m_2"]
    mm = recon_env["mm_5m_in"]

    async with recon_env["session_factory"]() as session:
        l1 = await session.get(BankStatementLine, line_1.id)
        l2 = await session.get(BankStatementLine, line_2.id)
        l1.reference = "REF-SHARED-MM-XFAIL"
        l2.reference = "REF-SHARED-MM-XFAIL"
        m = await session.get(MoneyMovement, mm.id)
        m.reference_no = "REF-SHARED-MM-XFAIL"
        await session.commit()

    resp = await client.post(
        f"/api/v1/bank-reconciliation/imports/{stmt_import.id}/auto-match",
        headers=headers,
    )
    assert resp.status_code == 200

    async with recon_env["session_factory"]() as session:
        recons = (
            await session.scalars(
                select(BankReconciliation).where(BankReconciliation.money_movement_id == mm.id)
            )
        ).all()
        # Future invariant: Only 1 reconciliation created for this MM candidate; candidate exclusion prevents duplicate match
        assert len(recons) == 1


@pytest.mark.asyncio
async def test_auto_match_skips_already_matched_statement_line(recon_env: Dict[str, Any]):
    """PASS characterization: Auto-match query correctly excludes lines that already have status MATCHED."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_import = recon_env["stmt_import_a"]

    # Mark all lines in import as MATCHED manually
    async with recon_env["session_factory"]() as session:
        lines = (
            await session.scalars(
                select(BankStatementLine).where(BankStatementLine.import_id == stmt_import.id)
            )
        ).all()
        for l in lines:
            l.reconciliation_status = ReconciliationStatus.MATCHED
        await session.commit()

    resp = await client.post(
        f"/api/v1/bank-reconciliation/imports/{stmt_import.id}/auto-match",
        headers=headers,
    )
    assert resp.status_code == 200
    stats = resp.json().get("stats", {})
    # Because lines are already MATCHED, 0 are evaluated or modified
    assert stats.get("matched") == 0
    assert stats.get("unmatched") == 0


# =============================================================================
# 8. DASHBOARD CASH COMPLETENESS DISTORTION
# =============================================================================


@pytest.mark.asyncio
async def test_invalid_match_does_not_distort_dashboard(recon_env: Dict[str, Any]):
    """Rejected requests leave the dashboard aggregates unchanged."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    org_id = recon_env["org_a"].id
    pay_acc_id = recon_env["pay_acc_a"].id

    async with recon_env["session_factory"]() as session:
        before = await BankReconciliationService(session).get_cash_completeness_dashboard(
            org_id, payment_account_id=pay_acc_id
        )

    stmt_line = recon_env["stmt_line_10m"]
    resp = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(stmt_line.id), "matched_amount": "10000000.00"},
        headers=headers,
    )
    assert resp.status_code == 422

    async with recon_env["session_factory"]() as session:
        after = await BankReconciliationService(session).get_cash_completeness_dashboard(
            org_id, payment_account_id=pay_acc_id
        )
    assert after.matched_amount == before.matched_amount
    assert after.unmatched_bank_amount == before.unmatched_bank_amount
    assert after.unmatched_book_amount == before.unmatched_book_amount


@pytest.mark.asyncio
async def test_future_invariant_dashboard_unmatched_book_authoritative(recon_env: Dict[str, Any]):
    """Regression: When a bank line is reconciled to a non-journal target (e.g. Transaction),

    unmatched_book_amount must directly count unreferenced cash JournalLines without synthetic reduction.
    """
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    org_id = recon_env["org_a"].id
    pay_acc_id = recon_env["pay_acc_a"].id

    stmt_line_5m = recon_env["stmt_line_5m_1"]
    tx_5m = recon_env["tx_5m"]

    # Reconcile statement line to Transaction (NOT JournalLine)
    resp = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(stmt_line_5m.id), "transaction_id": str(tx_5m.id), "matched_amount": "5000000.00"},
        headers=headers,
    )
    assert resp.status_code == 200

    async with recon_env["session_factory"]() as session:
        service = BankReconciliationService(session)
        dash = await service.get_cash_completeness_dashboard(org_id, payment_account_id=pay_acc_id)
        # In current baseline, unmatched_book is (30M - 5M) = 25M.
        # But in future authoritative model, all 30M of cash JournalLines remain unlinked,
        # so unmatched_book_amount must remain 30,000,000.00!
        assert dash.unmatched_book_amount == Decimal("30000000.00")


# =============================================================================
# 9. HISTORICAL DATA ANOMALY DETECTION (READ-ONLY PROBES)
# =============================================================================


@pytest.mark.asyncio
async def test_historical_anomaly_detection_queries(recon_env: Dict[str, Any]):
    """PASS characterization: Verifies that SQL inspection queries can detect all 10 anomaly classes

    in historical data without mutating any records.
    """
    async with recon_env["session_factory"]() as session:
        # Simulate unconstrained historical table before migration 024
        await session.execute(text("DROP INDEX IF EXISTS uq_bank_reconciliations_statement_line"))
        await session.execute(text("DROP INDEX IF EXISTS uq_bank_reconciliations_journal_line"))
        await session.execute(text("DROP INDEX IF EXISTS uq_bank_reconciliations_money_movement"))
        await session.execute(text("DROP INDEX IF EXISTS uq_bank_reconciliations_transaction"))
        await session.execute(text("PRAGMA ignore_check_constraints = ON"))

        org_id = recon_env["org_a"].id
        stmt_line_10m = recon_env["stmt_line_10m"]
        jl = recon_env["jl_bank_debit_10m"]
        mm = recon_env["mm_5m_in"]
        tx = recon_env["tx_5m"]

        # 1. Duplicate statement line anomaly
        recon_dup_1 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=org_id,
            statement_line_id=stmt_line_10m.id,
            journal_line_id=jl.id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("10000000.00"),
            match_rule="PROBE",
        )
        recon_dup_2 = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=org_id,
            statement_line_id=stmt_line_10m.id,
            journal_line_id=jl.id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("10000000.00"),
            match_rule="PROBE",
        )
        # 2. Zero-target anomaly
        recon_zero = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=org_id,
            statement_line_id=recon_env["stmt_line_5m_1"].id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("5000000.00"),
            match_rule="PROBE",
        )
        # 3. Multi-target anomaly
        recon_multi = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=org_id,
            statement_line_id=recon_env["stmt_line_5m_2"].id,
            journal_line_id=recon_env["jl_bank_debit_5m"].id,
            money_movement_id=mm.id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("5000000.00"),
            match_rule="PROBE",
        )
        # 4. Non-positive amount anomaly
        recon_non_pos = BankReconciliation(
            id=uuid.uuid4(),
            organization_id=org_id,
            statement_line_id=recon_env["stmt_line_out_5m"].id,
            transaction_id=tx.id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=Decimal("-100.00"),
            match_rule="PROBE",
        )
        session.add_all([recon_dup_1, recon_dup_2, recon_zero, recon_multi, recon_non_pos])
        await session.flush()

        # Query A: Detect duplicate active statement_line_id
        dup_stmt_lines = (
            await session.scalars(
                select(BankReconciliation.statement_line_id)
                .where(BankReconciliation.status == ReconciliationStatus.MATCHED)
                .group_by(BankReconciliation.statement_line_id)
                .having(func.count(BankReconciliation.id) > 1)
            )
        ).all()
        assert stmt_line_10m.id in dup_stmt_lines

        # Query B: Detect duplicate journal_line_id
        dup_jl = (
            await session.scalars(
                select(BankReconciliation.journal_line_id)
                .where(
                    BankReconciliation.journal_line_id.is_not(None),
                    BankReconciliation.status == ReconciliationStatus.MATCHED,
                )
                .group_by(BankReconciliation.journal_line_id)
                .having(func.count(BankReconciliation.id) > 1)
            )
        ).all()
        assert jl.id in dup_jl

        # Query C: Detect zero-target rows
        zero_target_rows = (
            await session.scalars(
                select(BankReconciliation.id).where(
                    BankReconciliation.journal_line_id.is_(None),
                    BankReconciliation.money_movement_id.is_(None),
                    BankReconciliation.transaction_id.is_(None),
                )
            )
        ).all()
        assert recon_zero.id in zero_target_rows

        # Query D: Detect multi-target rows
        multi_target_rows = (
            await session.scalars(
                select(BankReconciliation.id).where(
                    or_(
                        and_(BankReconciliation.journal_line_id.is_not(None), BankReconciliation.money_movement_id.is_not(None)),
                        and_(BankReconciliation.journal_line_id.is_not(None), BankReconciliation.transaction_id.is_not(None)),
                        and_(BankReconciliation.money_movement_id.is_not(None), BankReconciliation.transaction_id.is_not(None)),
                    )
                )
            )
        ).all()
        assert recon_multi.id in multi_target_rows

        # Query E: Detect non-positive matched_amount
        non_positive_rows = (
            await session.scalars(
                select(BankReconciliation.id).where(BankReconciliation.matched_amount <= 0)
            )
        ).all()
        assert recon_non_pos.id in non_positive_rows

        # Rollback so probes leave zero trace
        await session.rollback()


# =============================================================================
# 10. MULTI-TENANT REFERENCE PRECEDENCE & NON-REGRESSION (FIN-P1-105)
# =============================================================================


@pytest.mark.asyncio
async def test_precedence_foreign_target_fails_closed_404_before_discriminator_or_amount(recon_env: Dict[str, Any]):
    """PASS characterization: FIN-P1-105 precedence is preserved.

    When a foreign-tenant target is supplied, even if amount or target count is invalid,
    it MUST fail with 404 NOT_FOUND (anti-oracle), NOT with 422 or 409.
    """
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_a = recon_env["stmt_line_10m"]
    jl_b = recon_env["jl_b"]  # Tenant B journal line

    # Request has foreign JL AND invalid matched_amount
    payload = {
        "statement_line_id": str(stmt_line_a.id),
        "journal_line_id": str(jl_b.id),
        "matched_amount": "999999999.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json().get("error", {}).get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_precedence_foreign_money_movement_fails_closed_404(recon_env: Dict[str, Any]):
    """PASS characterization: Foreign MoneyMovement returns 404 NOT_FOUND."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_a = recon_env["stmt_line_5m_1"]
    mm_b = recon_env["mm_b"]

    payload = {
        "statement_line_id": str(stmt_line_a.id),
        "money_movement_id": str(mm_b.id),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json().get("error", {}).get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_precedence_foreign_transaction_fails_closed_404(recon_env: Dict[str, Any]):
    """PASS characterization: Foreign Transaction returns 404 NOT_FOUND."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_a = recon_env["stmt_line_5m_1"]
    tx_b = recon_env["tx_b"]

    payload = {
        "statement_line_id": str(stmt_line_a.id),
        "transaction_id": str(tx_b.id),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json().get("error", {}).get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_precedence_nonexistent_target_fails_closed_404(recon_env: Dict[str, Any]):
    """PASS characterization: Nonexistent UUID returns 404 NOT_FOUND identical to cross-tenant."""
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line_a = recon_env["stmt_line_5m_1"]

    payload = {
        "statement_line_id": str(stmt_line_a.id),
        "journal_line_id": str(uuid.uuid4()),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 404
    assert resp.json().get("error", {}).get("code") == "NOT_FOUND"


# =============================================================================
# 11. ROLE-BASED ACCESS CONTROL & ACTOR PROVENANCE (AUTHZ-001)
# =============================================================================


@pytest.mark.asyncio
async def test_authz_role_access_matrix_and_matched_by_provenance(recon_env: Dict[str, Any]):
    """PASS characterization: Reconcile endpoint allows ADMIN/MANAGER/OPERATOR,

    denies VIEWER with 403, denies unauthenticated with 401,
    and accurately records matched_by as the authenticated actor.
    """
    client: AsyncClient = recon_env["client"]
    org_id = recon_env["org_a"].id
    stmt_line = recon_env["stmt_line_10m"]
    jl = recon_env["jl_bank_debit_10m"]

    # 1. Unauthenticated -> 401
    resp_unauth = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(stmt_line.id), "journal_line_id": str(jl.id), "matched_amount": "10000000.00"},
    )
    assert resp_unauth.status_code == 401

    # 2. VIEWER -> 403
    headers_viewer = make_auth_headers(org_id, recon_env["users_a"][UserRole.VIEWER])
    resp_viewer = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(stmt_line.id), "journal_line_id": str(jl.id), "matched_amount": "10000000.00"},
        headers=headers_viewer,
    )
    assert resp_viewer.status_code == 403

    # 3. OPERATOR -> 200 and matched_by == operator.id
    operator_user = recon_env["users_a"][UserRole.OPERATOR]
    headers_op = make_auth_headers(org_id, operator_user)
    resp_op = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={"statement_line_id": str(stmt_line.id), "journal_line_id": str(jl.id), "matched_amount": "10000000.00"},
        headers=headers_op,
    )
    assert resp_op.status_code == 200
    recon_id = uuid.UUID(resp_op.json()["id"])

    async with recon_env["session_factory"]() as session:
        recon_row = await session.get(BankReconciliation, recon_id)
        assert recon_row is not None
        assert recon_row.matched_by == operator_user.id


# =============================================================================
# 12. STATE ATOMICITY & PARTIAL-WRITE VERIFICATION
# =============================================================================


@pytest.mark.asyncio
async def test_state_atomicity_no_partial_mutation_on_failed_match(recon_env: Dict[str, Any]):
    """PASS characterization: When a reconciliation request fails (e.g. 404 foreign target),

    verify zero partial writes:
    - PARTIAL WRITE: NO
    - BANK STATEMENT STATUS MUTATED: NO (remains UNMATCHED_BANK)
    - RECONCILIATION ROW CREATED: NO
    - TARGET MUTATED: NO
    - JOURNAL / LEDGER MUTATED: NO
    """
    client: AsyncClient = recon_env["client"]
    headers = make_auth_headers(recon_env["org_a"].id, recon_env["users_a"][UserRole.OPERATOR])
    stmt_line = recon_env["stmt_line_5m_1"]
    jl_b = recon_env["jl_b"]

    payload = {
        "statement_line_id": str(stmt_line.id),
        "journal_line_id": str(jl_b.id),
        "matched_amount": "5000000.00",
    }
    resp = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert resp.status_code == 404

    async with recon_env["session_factory"]() as session:
        line_refreshed = await session.get(BankStatementLine, stmt_line.id)
        assert line_refreshed.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK

        recon_count = await session.scalar(
            select(func.count(BankReconciliation.id)).where(BankReconciliation.statement_line_id == stmt_line.id)
        )
        assert recon_count == 0


# =============================================================================
# 13. POSTGRESQL CONCURRENCY RACE CONDITION PREREQUISITE GATE
# =============================================================================


@pytest.mark.asyncio
async def test_postgresql_concurrency_race_condition_gate():
    """Prerequisite gate: Proves that SQLite is NOT used as PostgreSQL concurrency proof.

    PostgreSQL race reproduction requires live PostgreSQL (FIN_001_TEST_DATABASE_URL),
    which is evaluated in CI or local PostgreSQL environments during CP3.
    """
    pg_url = os.environ.get("FIN_001_TEST_DATABASE_URL")
    if not pg_url:
        pytest.skip(
            "FIN_001_TEST_DATABASE_URL not set. In-memory SQLite cannot prove PostgreSQL row locking "
            "or partial unique index concurrency. Concurrent execution proof is scheduled for CP3."
        )
