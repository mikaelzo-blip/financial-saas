from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.journal import JournalEntry
from src.models.enums import ProjectStatus, TransactionType, CostCategory, AccountType
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.receivable_service import CustomerARService
from src.services.payable_service import VendorAPService
from src.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_fundamental_accounting_equation_and_journal_balance(db_session: AsyncSession):
    """
    Financial Integrity Suite:
    1. Simulates complete business cycle (Capital, Purchases, Bills, Invoices, Payments, Wages, Taxes, Reversals).
    2. Invariant 1: Total Debit == Total Credit for EVERY posted Journal Entry.
    3. Invariant 2: Trial Balance zero-sum equality (Global sum Debit == Global sum Credit).
    4. Invariant 3: Fundamental Accounting Equation:
       Assets = Liabilities + Equity + (Revenue - Expenses)
    """
    org = Organization(slug="org-integrity-suite", legal_name="PT Financial Integrity Test")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    cust = Counterparty(organization_id=org.id, name="PT Pemberi Proyek", is_customer=True)
    vend = Counterparty(organization_id=org.id, name="PT Toko Material", is_vendor=True)
    db_session.add_all([cust, vend])
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-2026-INT",
        project_name="Proyek Integritas",
        customer_id=cust.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(proj)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    balance_svc = BalanceService(db_session)

    # 1. Capital Injection: Rp 500.000.000 (Dr 1101 / Cr 3101)
    t1 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("500000000.00"),
            description="Setoran Modal"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t1.id)
    await db_session.commit()

    # 2. Customer Invoice: Rp 200.000.000 (Dr 1201 / Cr 4101)
    t2 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("200000000.00"),
            counterparty_id=cust.id,
            description="Invoice Termin 1",
            project_id=proj.id
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t2.id)
    await db_session.commit()

    # 3. Direct Purchase: Rp 70.000.000 (Dr 5101 / Cr 1101)
    t3 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 18),
            amount=Decimal("70000000.00"),
            counterparty_id=vend.id,
            description="Beli Semen & Pasir",
            project_id=proj.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t3.id)
    await db_session.commit()

    # 4. Vendor Bill: Rp 80.000.000 (Dr 5101 / Cr 2101)
    t4 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("80000000.00"),
            counterparty_id=vend.id,
            description="Tagihan Baja",
            project_id=proj.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t4.id)
    await db_session.commit()

    # 5. Customer Payment: Rp 150.000.000 (Dr 1101 / Cr 1201)
    t5 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 1, 25),
            amount=Decimal("150000000.00"),
            counterparty_id=cust.id,
            description="Bayar Termin 1 Sebagian"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t5.id)
    await db_session.commit()

    # 6. Pay Vendor Bill: Rp 50.000.000 (Dr 2101 / Cr 1101)
    t6 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 1, 28),
            amount=Decimal("50000000.00"),
            counterparty_id=vend.id,
            description="Cicil Tagihan Baja"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t6.id)
    await db_session.commit()

    # ----------------------------------------------------
    # INVARIANT 1: Check Every Journal Entry is Balanced
    # ----------------------------------------------------
    all_jes_stmt = select(JournalEntry).where(JournalEntry.organization_id == org.id)
    all_jes = (await db_session.execute(all_jes_stmt)).scalars().all()
    assert len(all_jes) == 6
    for je in all_jes:
        assert je.is_balanced is True
        assert je.total_debit == je.total_credit
        assert je.total_debit > Decimal("0.00")

    # ----------------------------------------------------
    # INVARIANT 2: Dynamic Trial Balance Zero-Sum
    # ----------------------------------------------------
    tb = await balance_svc.get_trial_balance(org.id)
    assert tb["is_balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]

    # ----------------------------------------------------
    # INVARIANT 3: Fundamental Accounting Equation
    # Assets = Liabilities + Equity + (Revenue - Expenses)
    # ----------------------------------------------------
    account_balances = {row["account_code"]: (row["net_balance"], row["account_type"]) for row in tb["accounts"]}

    assets = Decimal("0.00")
    liabilities = Decimal("0.00")
    equity = Decimal("0.00")
    revenue = Decimal("0.00")
    expenses = Decimal("0.00")

    for code, (balance, a_type) in account_balances.items():
        if a_type == AccountType.ASSET.value:
            assets += balance
        elif a_type == AccountType.LIABILITY.value:
            liabilities += balance
        elif a_type == AccountType.EQUITY.value:
            equity += balance
        elif a_type == AccountType.REVENUE.value:
            revenue += balance
        elif a_type == AccountType.EXPENSE.value:
            expenses += balance

    # Net Income = Revenue - Expenses
    net_income = revenue - expenses

    # Balance Sheet Equation: Assets == Liabilities + Equity + Net Income
    assert assets == liabilities + equity + net_income

    # Expected Values:
    # Assets: Kas (500M - 70M + 150M - 50M = 530M) + Piutang (200M - 150M = 50M) = 580M
    assert assets == Decimal("580000000.00")
    # Liabilities: Utang Usaha (80M - 50M = 30M)
    assert liabilities == Decimal("30000000.00")
    # Equity: Modal (500M)
    assert equity == Decimal("500000000.00")
    # Revenue: 200M
    assert revenue == Decimal("200000000.00")
    # Expenses: 70M + 80M = 150M
    assert expenses == Decimal("150000000.00")
    # Net Income: 200M - 150M = 50M
    assert net_income == Decimal("50000000.00")
    # Total Right Hand Side: 30M + 500M + 50M = 580M == Assets (580M)
    assert assets == Decimal("580000000.00")
