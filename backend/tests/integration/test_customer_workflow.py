from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.receivable_service import CustomerARService
from src.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_customer_invoice_payment_workflow(db_session: AsyncSession):
    """
    Test End-to-End Customer AR Lifecycle:
    1. Customer Invoice: Rp 150.000.000 (Dr 1201 Piutang / Cr 4101 Pendapatan) -> AR Created
    2. Customer Payment: Rp 150.000.000 (Dr 1101 Kas / Cr 1201 Piutang) -> AR Cleared
    3. Verify AR balance is Rp 0.00.
    4. Verify Contract Revenue is Rp 150.000.000.
    5. Verify Cash is Rp 150.000.000.
    """
    org = Organization(slug="org-customer-flow", legal_name="Org Customer Flow")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    customer = Counterparty(organization_id=org.id, name="PT Developer Metropolitan", is_customer=True)
    db_session.add(customer)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-302",
        project_name="Apartemen Tower B",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    ar_svc = CustomerARService(db_session)
    balance_svc = BalanceService(db_session)

    # 1. Customer Invoice: Rp 150.000.000
    t_inv = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("150000000.00"),
            counterparty_id=customer.id,
            description="Tagihan Termin 1 Struktur (20%)",
            project_id=project.id
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_inv.id)
    await db_session.commit()

    # Register in AR sub-ledger
    inv = await ar_svc.issue_customer_invoice(
        organization_id=org.id,
        customer_id=customer.id,
        project_id=project.id,
        invoice_date=date(2026, 1, 15),
        total_amount=Decimal("150000000.00"),
        transaction_id=t_inv.id
    )
    await db_session.commit()

    # Check trial balance before payment: 1201 (AR) has Debit Rp 150.000.000, 4101 has Credit Rp 150.000.000
    tb1 = await balance_svc.get_trial_balance(org.id)
    balances1 = {r["account_code"]: r["net_balance"] for r in tb1["accounts"]}
    assert balances1["1201"] == Decimal("150000000.00")
    assert balances1["4101"] == Decimal("150000000.00")

    # 2. Customer Payment: Rp 150.000.000
    t_pay = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 1, 30),
            amount=Decimal("150000000.00"),
            counterparty_id=customer.id,
            description="Pelunasan Tagihan Termin 1"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_pay.id)
    await db_session.commit()

    # Allocate payment in AR sub-ledger
    await ar_svc.allocate_customer_payment(org.id, t_pay.id, [(inv.id, Decimal("150000000.00"))])
    await db_session.commit()

    # 3. Verify final balances:
    tb2 = await balance_svc.get_trial_balance(org.id)
    balances2 = {r["account_code"]: r["net_balance"] for r in tb2["accounts"]}
    # AR 1201 cleared (Rp 0.00)
    assert balances2["1201"] == Decimal("0.00")
    # Revenue 4101 preserved
    assert balances2["4101"] == Decimal("150000000.00")
    # Cash 1101 received
    assert balances2["1101"] == Decimal("150000000.00")
