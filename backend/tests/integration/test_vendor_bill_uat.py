import uuid
from uuid import UUID, uuid4
from datetime import date
from decimal import Decimal
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import EntityNotFoundException, InvariantViolationException
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import CostCategory, ProjectStatus, TransactionType, WorkflowStatus
from src.models.journal import JournalEntry, JournalLine
from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.project import Project
from src.models.transaction import Transaction
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.payable_service import VendorAPService
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService


async def setup_vendor_context(db_session: AsyncSession, org_slug: str):
    org = Organization(
        slug=f"org-{org_slug}-{uuid4().hex[:6]}",
        legal_name=f"Org {org_slug}",
    )
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)

    customer = Counterparty(
        organization_id=org.id,
        name=f"Customer for {org_slug}",
        is_customer=True,
        is_active=True,
    )
    vendor = Counterparty(
        organization_id=org.id,
        name="PT Nusa Enginering",
        is_vendor=True,
        is_active=True,
    )
    other_vendor = Counterparty(
        organization_id=org.id,
        name="PT Vendor Lain",
        is_vendor=True,
        is_active=True,
    )
    db_session.add_all([customer, vendor, other_vendor])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code=f"PRJ-{uuid4().hex[:4].upper()}",
        project_name="Demo Perbaikan Panel Listrik",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("25000000.00"),
        revised_contract_value=Decimal("25000000.00"),
    )
    db_session.add(project)

    payment_account = await db_session.scalar(
        select(PaymentAccount).where(PaymentAccount.organization_id == org.id).limit(1)
    )

    await db_session.commit()
    return org, vendor, other_vendor, project, payment_account


@pytest.mark.asyncio
async def test_post_vendor_bill_creates_authoritative_ap_and_project_cost(db_session: AsyncSession):
    org, vendor, _, project, _ = await setup_vendor_context(db_session, "vendor-bill-uat")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("12000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-DEMO-001",
            description="Pembelian material panel listrik secara kredit untuk proyek demo",
        ),
    )
    await db_session.commit()

    journal = await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    assert journal is not None
    assert journal.total_debit == Decimal("12000000.00")
    assert journal.total_credit == Decimal("12000000.00")
    assert journal.is_balanced is True

    # Check journal lines: Dr 5101 (Biaya Material Langsung) Cr 2101 (Utang Usaha)
    stmt = (
        select(JournalLine)
        .options(selectinload(JournalLine.account))
        .where(JournalLine.journal_entry_id == journal.id)
    )
    res = await db_session.execute(stmt)
    lines = res.scalars().all()
    assert len(lines) == 2

    debit_line = next(l for l in lines if l.debit_amount > 0)
    credit_line = next(l for l in lines if l.credit_amount > 0)

    assert debit_line.account.account_code == "5101"
    assert debit_line.debit_amount == Decimal("12000000.00")
    assert debit_line.project_id == project.id
    assert debit_line.cost_category == CostCategory.MAT

    assert credit_line.account.account_code == "2101"
    assert credit_line.credit_amount == Decimal("12000000.00")

    # Check sub-ledger VendorBill record
    bill_stmt = select(VendorBill).where(
        VendorBill.organization_id == org.id,
        VendorBill.transaction_id == transaction.id,
    )
    bill = await db_session.scalar(bill_stmt)
    assert bill is not None
    assert bill.bill_code == "VINV-DEMO-001"
    assert bill.vendor_id == vendor.id
    assert bill.project_id == project.id
    assert bill.total_amount == Decimal("12000000.00")
    assert bill.status == "UNPAID"
    assert bill.calculate_outstanding_amount() == Decimal("12000000.00")


@pytest.mark.asyncio
async def test_vendor_bill_safety_and_reversal(db_session: AsyncSession):
    org, vendor, _, project, _ = await setup_vendor_context(db_session, "vendor-bill-rev")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("12000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-REV-001",
            description="Bill to be reversed",
        ),
    )
    await db_session.commit()

    journal = await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == transaction.id))
    assert bill.status == "UNPAID"

    # Reverse transaction
    reversal_service = ReversalService(db_session)
    rev_trx, rev_je = await reversal_service.reverse_transaction(
        org.id,
        transaction.id,
        reason="Entered in error",
    )
    await db_session.commit()

    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_je.total_debit == Decimal("12000000.00")
    assert rev_je.total_credit == Decimal("12000000.00")

    await db_session.refresh(bill)
    assert bill.status == "CANCELLED"


@pytest.mark.asyncio
async def test_vendor_bills_list_api_returns_persisted_bills(client: AsyncClient, db_session: AsyncSession):
    org, vendor, _, project, _ = await setup_vendor_context(db_session, "vendor-bills-api")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("12000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-DEMO-001",
            description="Pembelian material panel listrik secara kredit untuk proyek demo",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    headers = {"X-Organization-Id": str(org.id)}
    response = await client.get("/api/v1/vendor-bills", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["bill_number"] == "VINV-DEMO-001"
    assert Decimal(str(data[0]["total_amount"])) == Decimal("12000000.00")
    assert Decimal(str(data[0]["outstanding_amount"])) == Decimal("12000000.00")
    assert data[0]["bill_status"] == "UNPAID"
    assert data[0]["status"] == "NOT_DUE"


@pytest.mark.asyncio
async def test_vendor_payment_api_workflow_and_allocations(client: AsyncClient, db_session: AsyncSession):
    org, vendor, other_vendor, project, payment_account = await setup_vendor_context(db_session, "vendor-pmt-flow")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("12000000.00"),
            counterparty_id=vendor.id,
            project_id=project.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-DEMO-002",
            description="Bill to test vendor payment API",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    bill = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == transaction.id))
    assert bill is not None

    headers = {"X-Organization-Id": str(org.id)}
    payload = {
        "bill_id": str(bill.id),
        "payment_account_id": str(payment_account.id),
        "amount": "12000000.00",
        "payment_date": "2026-09-02",
        "reference_no": "VPAY-DEMO-001",
        "description": "Pelunasan vendor bill",
    }
    response = await client.post("/api/v1/vendor-payments", json=payload, headers=headers)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["bill_id"] == str(bill.id)
    assert Decimal(str(res_data["amount"])) == Decimal("12000000.00")
    assert res_data["bill_status"] == "PAID"
    assert Decimal(str(res_data["outstanding_amount"])) == Decimal("0.00")

    # Verify Journal: Dr 2101 Cr 1101 (Payment Account COA)
    je = await db_session.scalar(
        select(JournalEntry).where(JournalEntry.id == uuid.UUID(res_data["journal_entry_id"]))
    )
    assert je.total_debit == Decimal("12000000.00")
    assert je.total_credit == Decimal("12000000.00")


@pytest.mark.asyncio
async def test_vendor_bill_and_payment_tenant_isolation(db_session: AsyncSession):
    org_a, vendor_a, _, project_a, payment_account_a = await setup_vendor_context(db_session, "tenant-a")
    org_b, vendor_b, _, project_b, payment_account_b = await setup_vendor_context(db_session, "tenant-b")

    # Org A bill
    service_a = TransactionService(db_session)
    trx_a = await service_a.create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("5000000.00"),
            counterparty_id=vendor_a.id,
            project_id=project_a.id,
            cost_category=CostCategory.MAT,
            reference_no="VINV-ORG-A",
            description="Org A Bill",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org_a.id, trx_a.id)
    await db_session.commit()

    bill_a = await db_session.scalar(select(VendorBill).where(VendorBill.transaction_id == trx_a.id))

    # Cross-tenant payment attempt: Org B tries to pay Org A's bill
    ap_service_b = VendorAPService(db_session)
    pmt_b = await TransactionService(db_session).create_transaction(
        org_b.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("5000000.00"),
            counterparty_id=vendor_b.id,
            payment_account_id=payment_account_b.id,
            reference_no="VPAY-ATTEMPT-B",
            description="Cross tenant attempt",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org_b.id, pmt_b.id)
    await db_session.commit()

    with pytest.raises(EntityNotFoundException):
        await ap_service_b.allocate_vendor_payment(
            org_b.id,
            pmt_b.id,
            [(bill_a.id, Decimal("5000000.00"))],
        )

    # Overpayment safety check
    pmt_a = await TransactionService(db_session).create_transaction(
        org_a.id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("10000000.00"),
            counterparty_id=vendor_a.id,
            payment_account_id=payment_account_a.id,
            reference_no="VPAY-OVER-A",
            description="Overpayment attempt",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org_a.id, pmt_a.id)
    await db_session.commit()

    ap_service_a = VendorAPService(db_session)
    with pytest.raises(InvariantViolationException, match="exceeds outstanding"):
        await ap_service_a.allocate_vendor_payment(
            org_a.id,
            pmt_a.id,
            [(bill_a.id, Decimal("10000000.00"))],
        )
