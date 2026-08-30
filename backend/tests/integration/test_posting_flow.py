from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.project import Project
from src.models.enums import (
    AccountType,
    NormalBalance,
    ProjectStatus,
    TransactionType,
    WorkflowStatus,
    CostCategory,
)
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_end_to_end_posting_and_trial_balance(db_session: AsyncSession):
    """
    Test End-to-End Accounting Engine posting flow:
    1. Capital Injection (Owner Contribution): Rp 100.000.000 (Dr 1101 / Cr 3101)
    2. Direct Project Purchase: Rp 25.000.000 (Dr 5101 / Cr 1101)
    3. Verify Dynamic Trial Balance: Total Debit == Total Credit == Rp 125.000.000
    4. Verify Cash Balance: Rp 75.000.000
    """
    org = Organization(slug="org-posting-flow", legal_name="Org Posting Flow")
    db_session.add(org)
    await db_session.flush()

    # Seed standard COA
    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    customer = Counterparty(organization_id=org.id, name="PT Pemberi Proyek", is_customer=True)
    db_session.add(customer)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-101",
        project_name="Pembangunan Gudang Logistik",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    trx_service = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    balance_svc = BalanceService(db_session)

    # 1. Capital Injection: Rp 100.000.000
    t1 = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("100000000.00"),
            description="Setoran Modal Awal Pemilik"
        )
    )
    await db_session.commit()
    je1 = await engine.post_transaction(org.id, t1.id)
    await db_session.commit()

    assert je1.entry_number == "JE-2026-000001"
    assert je1.total_debit == Decimal("100000000.00")
    assert je1.total_credit == Decimal("100000000.00")

    # 2. Direct Purchase: Rp 25.000.000
    t2 = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("25000000.00"),
            description="Pembelian Material Pasir & Batu",
            project_id=project.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    je2 = await engine.post_transaction(org.id, t2.id)
    await db_session.commit()

    assert je2.entry_number == "JE-2026-000002"
    assert je2.total_debit == Decimal("25000000.00")

    # 3. Verify Trial Balance
    tb = await balance_svc.get_trial_balance(org.id)
    assert tb["is_balanced"] is True
    assert tb["total_debit"] == Decimal("125000000.00")
    assert tb["total_credit"] == Decimal("125000000.00")

    # 4. Verify Derived Account Balances
    accounts = {row["account_code"]: row["net_balance"] for row in tb["accounts"]}
    assert accounts["1101"] == Decimal("75000000.00")   # Kas dan Bank (100M - 25M)
    assert accounts["3101"] == Decimal("100000000.00")  # Modal Pemilik
    assert accounts["5101"] == Decimal("25000000.00")   # Biaya Proyek
