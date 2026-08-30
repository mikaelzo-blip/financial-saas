import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.models.project import Project
from src.models.enums import TransactionType, WorkflowStatus, ProjectStatus
from src.services.reporting.ar_aging_service import ARAgingService


@pytest.mark.asyncio
async def test_ar_aging_buckets(db_session: AsyncSession):
    org = Organization(slug="pt-ar-test", legal_name="PT AR Test")
    db_session.add(org)
    await db_session.flush()

    cust = Counterparty(
        organization_id=org.id,
        name="PT Customer Utama",
        is_customer=True,
        is_vendor=False
    )
    db_session.add(cust)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-AR-01",
        project_name="Proyek AR",
        customer_id=cust.id,
        start_date=date(2026, 1, 1),
        original_contract_value=Decimal("100000000.00"),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(proj)
    await db_session.flush()

    today = date(2026, 6, 1)

    # 1. Current invoice
    inv1 = CustomerInvoice(
        organization_id=org.id,
        customer_id=cust.id,
        project_id=proj.id,
        invoice_code="INV-001",
        invoice_date=date(2026, 5, 20),
        due_date=date(2026, 6, 20),
        total_amount=Decimal("10000000.00"),
        status="UNPAID"
    )
    # 2. 15 days overdue (bucket 1_30)
    inv2 = CustomerInvoice(
        organization_id=org.id,
        customer_id=cust.id,
        project_id=proj.id,
        invoice_code="INV-002",
        invoice_date=date(2026, 4, 15),
        due_date=date(2026, 5, 17),
        total_amount=Decimal("20000000.00"),
        status="PARTIAL"
    )
    # 3. 45 days overdue (bucket 31_60)
    inv3 = CustomerInvoice(
        organization_id=org.id,
        customer_id=cust.id,
        project_id=proj.id,
        invoice_code="INV-003",
        invoice_date=date(2026, 3, 1),
        due_date=date(2026, 4, 17),
        total_amount=Decimal("30000000.00"),
        status="UNPAID"
    )
    db_session.add_all([inv1, inv2, inv3])
    await db_session.flush()

    # Partial allocation for inv2: 5M paid
    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PAY-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 5, 1),
        amount=Decimal("5000000.00"),
        description="Pembayaran sebagian",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv2.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("5000000.00")
    )
    db_session.add(alloc)
    await db_session.commit()

    ar_report = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=today
    )

    assert ar_report.summary.current == Decimal("10000000.00")
    assert ar_report.summary.days_1_30 == Decimal("15000000.00")
    assert ar_report.summary.days_31_60 == Decimal("30000000.00")
    assert ar_report.summary.total == Decimal("55000000.00")
    assert len(ar_report.invoices) == 3
