from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType, CostCategory, WorkflowStatus
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.payable_service import VendorAPService
from src.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_vendor_invoice_payment_workflow(db_session: AsyncSession):
    """
    Test End-to-End Vendor AP Lifecycle:
    1. Capital Injection: Rp 50.000.000 (Dr 1101 / Cr 3101)
    2. Vendor Bill: Rp 30.000.000 (Dr 5101 / Cr 2101) -> AP Created
    3. Vendor Payment: Rp 30.000.000 (Dr 2101 / Cr 1101) -> AP Cleared
    4. Verify No Duplicate Project Expense: 5101 is only Rp 30.000.000 total.
    5. Verify AP balance is Rp 0.00.
    """
    org = Organization(slug="org-vendor-flow", legal_name="Org Vendor Flow")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    vendor = Counterparty(organization_id=org.id, name="PT Supplier Baja Utama", is_vendor=True)
    db_session.add(vendor)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-202",
        project_name="Pabrik Baja",
        customer_id=vendor.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    ap_svc = VendorAPService(db_session)
    balance_svc = BalanceService(db_session)

    # 1. Capital Injection: Rp 50.000.000
    t0 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("50000000.00"),
            description="Modal Awal"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t0.id)
    await db_session.commit()

    # 2. Vendor Bill: Rp 30.000.000
    t_bill = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("30000000.00"),
            counterparty_id=vendor.id,
            description="Tagihan Baja 10 Ton",
            project_id=project.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_bill.id)
    await db_session.commit()

    # Register in sub-ledger
    bill = await ap_svc.register_vendor_bill(
        organization_id=org.id,
        vendor_id=vendor.id,
        bill_date=date(2026, 1, 10),
        due_date=date(2026, 2, 10),
        total_amount=Decimal("30000000.00"),
        project_id=project.id,
        transaction_id=t_bill.id
    )
    await db_session.commit()

    # Check AP balance before payment: 2101 should have Credit balance of 30.000.000
    tb1 = await balance_svc.get_trial_balance(org.id)
    balances1 = {r["account_code"]: r["net_balance"] for r in tb1["accounts"]}
    assert balances1["2101"] == Decimal("30000000.00")
    assert balances1["5101"] == Decimal("30000000.00")

    # 3. Vendor Payment: Rp 30.000.000
    t_pay = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("30000000.00"),
            counterparty_id=vendor.id,
            description="Pelunasan Tagihan Baja"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_pay.id)
    await db_session.commit()

    # Allocate payment in sub-ledger
    await ap_svc.allocate_vendor_payment(org.id, t_pay.id, [(bill.id, Decimal("30000000.00"))])
    await db_session.commit()

    # 4. Invariant checks:
    # AP is now cleared (Rp 0.00)
    tb2 = await balance_svc.get_trial_balance(org.id)
    balances2 = {r["account_code"]: r["net_balance"] for r in tb2["accounts"]}
    assert balances2["2101"] == Decimal("0.00")
    # Project Expense 5101 is NOT duplicated (still exactly Rp 30.000.000)
    assert balances2["5101"] == Decimal("30000000.00")
    # Cash 1101 is Rp 20.000.000 (50M - 30M)
    assert balances2["1101"] == Decimal("20000000.00")
