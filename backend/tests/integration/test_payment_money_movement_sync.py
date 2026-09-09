from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import AccountType, CostCategory, MovementDirection, NormalBalance, ProjectStatus, SettlementType, TransactionType
from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.project import Project
from src.models.receivable import CustomerInvoice
from src.models.user import User
from src.models.enums import UserRole
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.payable_service import VendorAPService
from src.services.receivable_service import CustomerARService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService


async def setup_payment_mm_test_tenant(session: AsyncSession, slug: str):
    org = Organization(slug=slug, legal_name=f"Org {slug}")
    session.add(org)
    await session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
        is_active=True,
    )
    coa_1201 = ChartOfAccount(
        organization_id=org.id,
        account_code="1201",
        account_name="Piutang Usaha",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
        is_active=True,
    )
    coa_2101 = ChartOfAccount(
        organization_id=org.id,
        account_code="2101",
        account_name="Utang Usaha",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="CURRENT_LIABILITIES",
        is_active=True,
    )
    coa_4101 = ChartOfAccount(
        organization_id=org.id,
        account_code="4101",
        account_name="Pendapatan Proyek",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE",
        is_active=True,
    )
    coa_5101 = ChartOfAccount(
        organization_id=org.id,
        account_code="5101",
        account_name="Harga Pokok Proyek",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="COGS",
        is_active=True,
    )
    session.add_all([coa_1101, coa_1201, coa_2101, coa_4101, coa_5101])
    await session.flush()

    payment_account = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="Bank Mandiri",
        bank_name="Mandiri",
        account_number="1234567890",
        is_active=True,
    )
    customer = Counterparty(
        organization_id=org.id,
        name="PT Pelanggan",
        is_customer=True,
        is_vendor=False,
    )
    vendor = Counterparty(
        organization_id=org.id,
        name="PT Pemasok",
        is_customer=False,
        is_vendor=True,
    )
    session.add_all([payment_account, customer, vendor])
    await session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-MM-001",
        project_name="Proyek MM Sync",
        customer_id=customer.id,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 9, 1),
        project_status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    user = User(
        organization_id=org.id,
        email=f"operator-{slug}@example.com",
        full_name="Payment Operator",
        password_hash="test-only",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return org, customer, vendor, project, payment_account, user


@pytest.mark.asyncio
async def test_customer_payment_creates_and_synchronizes_money_movement(client, db_session: AsyncSession):
    org, customer, _, project, payment_account, user = await setup_payment_mm_test_tenant(db_session, "test-cp-mm-sync")

    # 1. Issue customer invoice
    inv_trx = await TransactionService(db_session).create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("30000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            reference_no="INV-MM-001",
            description="Invoice Proyek MM",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, inv_trx.id)
    await db_session.commit()

    invoice = await db_session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == inv_trx.id))

    # 2. Record customer payment via API
    resp = await client.post(
        "/api/v1/customer-payments",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
        json={
            "invoice_id": str(invoice.id),
            "payment_account_id": str(payment_account.id),
            "amount": "15000000.00",
            "payment_date": "2026-09-02",
            "reference_no": "PAY-CUST-MM-001",
            "description": "Pembayaran termin 1",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    payment_trx_id = UUID(data["payment_transaction_id"])

    # 3. Assert MoneyMovement and Settlement were created and synchronized
    mm = await db_session.scalar(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org.id,
            MoneyMovement.payment_account_id == payment_account.id,
            MoneyMovement.reference_no == "PAY-CUST-MM-001",
        )
    )
    assert mm is not None, "MoneyMovement record was not created for customer payment"
    assert mm.direction == MovementDirection.IN
    assert mm.amount == Decimal("15000000.00")
    assert mm.movement_date == date(2026, 9, 2)

    settlement = await db_session.scalar(
        select(Settlement).where(
            Settlement.organization_id == org.id,
            Settlement.money_movement_id == mm.id,
            Settlement.transaction_id == payment_trx_id,
        )
    )
    assert settlement is not None, "Settlement record was not linked to payment transaction"
    assert settlement.settlement_type == SettlementType.INVOICE_PAYMENT
    assert settlement.amount == Decimal("15000000.00")

    alloc = await db_session.scalar(
        select(SettlementAllocation).where(
            SettlementAllocation.settlement_id == settlement.id,
            SettlementAllocation.invoice_id == payment_trx_id,
        )
    )
    assert alloc is not None, "SettlementAllocation record was not created"
    assert alloc.amount == Decimal("15000000.00")
    assert alloc.project_id == project.id

    # 4. Reversal safety: reversing customer payment de-synchronizes / deletes settlement & movement
    rev_svc = ReversalService(db_session)
    await rev_svc.reverse_transaction(org.id, payment_trx_id, reason="Customer payment cancellation")
    await db_session.commit()

    # Verify settlement linked to reversed payment is removed or marked
    settlement_after = await db_session.scalar(
        select(Settlement).where(Settlement.id == settlement.id)
    )
    assert settlement_after is None, "Settlement record should be removed upon payment reversal"


@pytest.mark.asyncio
async def test_vendor_payment_creates_and_synchronizes_money_movement(client, db_session: AsyncSession):
    org, _, vendor, project, payment_account, user = await setup_payment_mm_test_tenant(db_session, "test-vp-mm-sync")

    # 1. Post Vendor Bill
    bill_trx = await TransactionService(db_session).create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("20000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-MM-001",
            description="Material tagihan",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, bill_trx.id)
    await db_session.commit()

    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == bill_trx.id))

    # 2. Record vendor payment via API
    resp = await client.post(
        "/api/v1/vendor-payments",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
        json={
            "bill_id": str(bill.id),
            "payment_account_id": str(payment_account.id),
            "amount": "20000000.00",
            "payment_date": "2026-09-02",
            "reference_no": "VPAY-MM-001",
            "description": "Pelunasan material",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    payment_trx_id = UUID(data["payment_transaction_id"])

    # 3. Assert MoneyMovement and Settlement were created and synchronized
    mm = await db_session.scalar(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org.id,
            MoneyMovement.payment_account_id == payment_account.id,
            MoneyMovement.reference_no == "VPAY-MM-001",
        )
    )
    assert mm is not None, "MoneyMovement record was not created for vendor payment"
    assert mm.direction == MovementDirection.OUT
    assert mm.amount == Decimal("20000000.00")
    assert mm.movement_date == date(2026, 9, 2)

    settlement = await db_session.scalar(
        select(Settlement).where(
            Settlement.organization_id == org.id,
            Settlement.money_movement_id == mm.id,
            Settlement.transaction_id == payment_trx_id,
        )
    )
    assert settlement is not None, "Settlement record was not linked to vendor payment transaction"
    assert settlement.settlement_type == SettlementType.INVOICE_PAYMENT
    assert settlement.amount == Decimal("20000000.00")

    alloc = await db_session.scalar(
        select(SettlementAllocation).where(
            SettlementAllocation.settlement_id == settlement.id,
            SettlementAllocation.invoice_id == bill_trx.id,
        )
    )
    assert alloc is not None, "SettlementAllocation record was not created"
    assert alloc.amount == Decimal("20000000.00")
    assert alloc.project_id == project.id
    assert alloc.cost_category == CostCategory.MAT

    # 4. Reversal safety: reversing vendor payment cleans up money movement settlement
    rev_svc = ReversalService(db_session)
    await rev_svc.reverse_transaction(org.id, payment_trx_id, reason="Vendor payment cancellation")
    await db_session.commit()

    settlement_after = await db_session.scalar(
        select(Settlement).where(Settlement.id == settlement.id)
    )
    assert settlement_after is None, "Settlement record should be removed upon vendor payment reversal"
