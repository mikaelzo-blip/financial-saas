import pytest
import uuid
from datetime import date
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import AccountType, CostCategory, NormalBalance, TransactionType, WorkflowStatus
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.payable_service import VendorAPService
from src.services.transaction_service import TransactionService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


async def setup_test_tenant(db_session: AsyncSession, slug_suffix: str):
    unique_suffix = f"{slug_suffix}-{uuid.uuid4().hex[:6]}"
    org = Organization(
        slug=f"org-{unique_suffix}",
        legal_name=f"PT Organisasi {unique_suffix}",
        default_payment_term_days=30,
        fiscal_year_start_month=1,
    )
    db_session.add(org)
    await db_session.flush()

    # Chart of accounts
    coa_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSET",
        is_active=True,
    )
    coa_2101 = ChartOfAccount(
        organization_id=org.id,
        account_code="2101",
        account_name="Utang Usaha",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="CURRENT_LIABILITY",
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
    db_session.add_all([coa_1101, coa_2101, coa_5101])
    await db_session.flush()

    pmt_acc = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa_1101.id,
        name="Bank Mandiri",
        bank_name="Mandiri",
        account_number="1234567890",
        is_active=True,
    )
    customer = Counterparty(
        organization_id=org.id,
        name="PT Customer Test",
        is_customer=True,
        is_vendor=False,
        is_active=True,
    )
    vendor = Counterparty(
        organization_id=org.id,
        name="PT Vendor Utama",
        is_customer=False,
        is_vendor=True,
        is_active=True,
    )
    db_session.add_all([pmt_acc, customer, vendor])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code=f"PRJ-{unique_suffix.upper()}",
        project_name="Proyek UAT Payment",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31),
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
    )
    db_session.add(project)
    await db_session.flush()
    return org, vendor, project, pmt_acc


@pytest.mark.asyncio
async def test_vendor_payment_full_workflow_safety(client: AsyncClient, db_session: AsyncSession):
    org, vendor, project, pmt_acc = await setup_test_tenant(db_session, "vpay-safety")

    # 1. Post Vendor Bill of Rp12,000,000
    trx_svc = TransactionService(db_session)
    bill_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("12000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-TEST-001",
            description="Test Bill for Safety",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, bill_trx.id)
    await db_session.commit()

    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == bill_trx.id))
    assert bill is not None
    assert bill.status == "UNPAID"
    assert bill.calculate_outstanding_amount() == Decimal("12000000.00")

    headers = {"X-Organization-Id": str(org.id)}

    # 2. Overpayment greater than outstanding AP is rejected via API
    overpay_payload = {
        "bill_id": str(bill.id),
        "payment_account_id": str(pmt_acc.id),
        "amount": "15000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-TEST-001",
        "description": "Overpayment attempt",
    }
    resp = await client.post("/api/v1/vendor-payments", json=overpay_payload, headers=headers)
    assert resp.status_code == 422
    assert "exceeds outstanding balance" in resp.json()["error"]["message"]

    # 3. Valid partial payment of Rp5,000,000
    partial_payload = {
        "bill_id": str(bill.id),
        "payment_account_id": str(pmt_acc.id),
        "amount": "5000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-TEST-001",
        "description": "Partial payment 1",
    }
    resp = await client.post("/api/v1/vendor-payments", json=partial_payload, headers=headers)
    assert resp.status_code == 201
    partial_res = resp.json()
    assert partial_res["bill_status"] == "PARTIALLY_PAID"
    assert Decimal(str(partial_res["outstanding_amount"])) == Decimal("7000000.00")

    # 4. Duplicate / Replay Protection on exact same payment
    dup_resp = await client.post("/api/v1/vendor-payments", json=partial_payload, headers=headers)
    assert dup_resp.status_code == 422
    assert "duplicate" in dup_resp.json()["error"]["message"].lower()

    # 5. Settlement of remaining Rp7,000,000
    settle_payload = {
        "bill_id": str(bill.id),
        "payment_account_id": str(pmt_acc.id),
        "amount": "7000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-TEST-002",
        "description": "Final settlement",
    }
    resp = await client.post("/api/v1/vendor-payments", json=settle_payload, headers=headers)
    assert resp.status_code == 201
    settle_res = resp.json()
    assert settle_res["bill_status"] == "PAID"
    assert Decimal(str(settle_res["outstanding_amount"])) == Decimal("0.00")

    # 6. Paid bill cannot be paid again
    again_payload = {
        "bill_id": str(bill.id),
        "payment_account_id": str(pmt_acc.id),
        "amount": "1000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-TEST-003",
        "description": "Payment on fully paid bill",
    }
    resp = await client.post("/api/v1/vendor-payments", json=again_payload, headers=headers)
    assert resp.status_code == 422
    assert "already fully paid" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_vendor_payment_cross_tenant_and_invalid_account(client: AsyncClient, db_session: AsyncSession):
    org_a, vendor_a, project_a, pmt_acc_a = await setup_test_tenant(db_session, "tenant-a-safety")
    org_b, vendor_b, project_b, pmt_acc_b = await setup_test_tenant(db_session, "tenant-b-safety")

    # Org A bill
    trx_svc = TransactionService(db_session)
    bill_trx = await trx_svc.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("8000000.00"),
            counterparty_id=vendor_a.id,
            project_id=project_a.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-ORG-A-001",
            description="Org A Bill",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org_a.id, bill_trx.id)
    await db_session.commit()

    bill_a = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == bill_trx.id))

    # Cross tenant: Org B tries to pay Org A's bill with Org B's account
    headers_b = {"X-Organization-Id": str(org_b.id)}
    payload_cross = {
        "bill_id": str(bill_a.id),
        "payment_account_id": str(pmt_acc_b.id),
        "amount": "8000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-CROSS-001",
        "description": "Cross tenant payment",
    }
    resp = await client.post("/api/v1/vendor-payments", json=payload_cross, headers=headers_b)
    assert resp.status_code == 404

    # Org A tries to pay with Org B's payment account
    headers_a = {"X-Organization-Id": str(org_a.id)}
    payload_invalid_acc = {
        "bill_id": str(bill_a.id),
        "payment_account_id": str(pmt_acc_b.id),
        "amount": "8000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-INV-ACC",
        "description": "Invalid payment account",
    }
    resp = await client.post("/api/v1/vendor-payments", json=payload_invalid_acc, headers=headers_a)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vendor_allocation_rejects_wrong_vendor_payment(db_session: AsyncSession):
    org, vendor_a, project, payment_account = await setup_test_tenant(db_session, "vendor-match")
    vendor_b = Counterparty(organization_id=org.id, name="PT Vendor Kedua", is_vendor=True, is_customer=False)
    db_session.add(vendor_b); await db_session.flush()
    bill_transaction = await TransactionService(db_session).create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.VENDOR_BILL, transaction_date=date(2026, 9, 2),
        amount=Decimal("1000.00"), counterparty_id=vendor_b.id, project_id=project.id,
        cost_category=CostCategory.MAT, reference_no="VINV-WRONG-VENDOR", description="Vendor B bill",
    ))
    await AccountingEngine(db_session).post_transaction(org.id, bill_transaction.id)
    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == bill_transaction.id))
    payment = await TransactionService(db_session).create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.PAY_VENDOR_BILL, transaction_date=date(2026, 9, 2),
        amount=Decimal("1000.00"), counterparty_id=vendor_a.id, payment_account_id=payment_account.id,
        reference_no="VPAY-WRONG-VENDOR", description="Vendor A payment",
    ))
    await AccountingEngine(db_session).post_transaction(org.id, payment.id)

    with pytest.raises(InvariantViolationException, match="same vendor"):
        await VendorAPService(db_session).allocate_vendor_payment(org.id, payment.id, [(bill.id, Decimal("1000.00"))])
