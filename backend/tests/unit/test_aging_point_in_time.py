import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation, CustomerRetentionRelease
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.transaction import Transaction
from src.models.enums import TransactionType, WorkflowStatus, ProjectStatus
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService


@pytest.mark.asyncio
async def test_ar_aging_point_in_time_leakage(db_session: AsyncSession):
    """
    Invoice created in 2024, paid in 2025.
    AR aging as of 2024-12-31 must show the invoice as fully outstanding (paid_amount=0).
    AR aging as of 2025-01-31 must show the invoice as settled.
    """
    org = Organization(slug="pt-pit-ar-test", legal_name="PT PIT AR Test")
    db_session.add(org)
    await db_session.flush()

    cust = Counterparty(
        organization_id=org.id,
        name="Pelanggan PIT",
        is_customer=True,
        is_vendor=False,
    )
    db_session.add(cust)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-PIT-01",
        project_name="Proyek PIT AR",
        customer_id=cust.id,
        start_date=date(2024, 1, 1),
        original_contract_value=Decimal("100000000.00"),
        project_status=ProjectStatus.ACTIVE,
    )
    db_session.add(proj)
    await db_session.flush()

    # Invoice dated 2024-12-01, due 2024-12-31
    inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=cust.id,
        project_id=proj.id,
        invoice_code="INV-PIT-2024-001",
        invoice_date=date(2024, 12, 1),
        due_date=date(2024, 12, 31),
        total_amount=Decimal("10000000.00"),
        status="PAID",  # Current status in DB is PAID
    )
    db_session.add(inv)
    await db_session.flush()

    # Payment transaction occurred in 2025
    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PIT-PAY-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2025, 1, 15),
        amount=Decimal("10000000.00"),
        description="Pelunasan Januari 2025",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("10000000.00"),
        created_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(alloc)
    await db_session.commit()

    # 1. As of 2024-12-31: Invoice should be outstanding Rp 10.000.000
    report_2024 = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2024, 12, 31),
    )
    assert len(report_2024.invoices) == 1, "Invoice must appear in aging report as of 2024-12-31"
    line = report_2024.invoices[0]
    assert line.invoice_number == "INV-PIT-2024-001"
    assert line.total_amount == Decimal("10000000.00")
    assert line.paid_amount == Decimal("0.00"), "Paid amount as of 2024-12-31 must be 0"
    assert line.outstanding_amount == Decimal("10000000.00"), "Outstanding amount as of 2024-12-31 must be 10M"
    assert report_2024.summary.total == Decimal("10000000.00")

    # 2. As of 2025-01-31: Invoice should be fully settled (outstanding = 0, excluded from aging)
    report_2025 = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2025, 1, 31),
    )
    assert len(report_2025.invoices) == 0, "Invoice must not appear as outstanding as of 2025-01-31"
    assert report_2025.summary.total == Decimal("0.00")


@pytest.mark.asyncio
async def test_ap_aging_point_in_time_leakage(db_session: AsyncSession):
    """
    Bill created in 2024, paid in 2025.
    AP aging as of 2024-12-31 must show the bill as fully outstanding (paid_amount=0).
    AP aging as of 2025-01-31 must show the bill as settled.
    """
    org = Organization(slug="pt-pit-ap-test", legal_name="PT PIT AP Test")
    db_session.add(org)
    await db_session.flush()

    vend = Counterparty(
        organization_id=org.id,
        name="Vendor PIT",
        is_customer=False,
        is_vendor=True,
    )
    db_session.add(vend)
    await db_session.flush()

    # Bill dated 2024-12-01, due 2024-12-31
    bill = VendorBill(
        organization_id=org.id,
        vendor_id=vend.id,
        bill_code="BILL-PIT-2024-001",
        bill_date=date(2024, 12, 1),
        due_date=date(2024, 12, 31),
        total_amount=Decimal("15000000.00"),
        status="PAID",
    )
    db_session.add(bill)
    await db_session.flush()

    # Payment transaction occurred in 2025
    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PIT-VB-01",
        transaction_type=TransactionType.PAY_VENDOR_BILL,
        transaction_date=date(2025, 1, 20),
        amount=Decimal("15000000.00"),
        description="Pelunasan Bill Januari 2025",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = VendorPaymentAllocation(
        bill_id=bill.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("15000000.00"),
        created_at=datetime(2025, 1, 20, 14, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(alloc)
    await db_session.commit()

    # 1. As of 2024-12-31: Bill should be outstanding Rp 15.000.000
    report_2024 = await APAgingService.get_ap_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2024, 12, 31),
    )
    assert len(report_2024.bills) == 1, "Bill must appear in aging report as of 2024-12-31"
    line = report_2024.bills[0]
    assert line.bill_number == "BILL-PIT-2024-001"
    assert line.total_amount == Decimal("15000000.00")
    assert line.paid_amount == Decimal("0.00"), "Paid amount as of 2024-12-31 must be 0"
    assert line.outstanding_amount == Decimal("15000000.00"), "Outstanding amount as of 2024-12-31 must be 15M"
    assert report_2024.summary.total == Decimal("15000000.00")

    # 2. As of 2025-01-31: Bill should be fully settled (outstanding = 0, excluded from aging)
    report_2025 = await APAgingService.get_ap_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2025, 1, 31),
    )
    assert len(report_2025.bills) == 0, "Bill must not appear as outstanding as of 2025-01-31"
    assert report_2025.summary.total == Decimal("0.00")


@pytest.mark.asyncio
async def test_ar_aging_point_in_time_retention_release(db_session: AsyncSession):
    """
    Invoice created in 2024 with retention withheld (base collectible paid in 2024).
    Retention released in 2025.
    AR aging as of 2024-12-31 must not include the future retention release (outstanding = 0).
    AR aging as of 2025-01-15 must include the released retention (outstanding = 1.000.000).
    """
    org = Organization(slug="pt-pit-retention-test", legal_name="PT PIT Retention Test")
    db_session.add(org)
    await db_session.flush()

    cust = Counterparty(
        organization_id=org.id,
        name="Pelanggan Retention PIT",
        is_customer=True,
        is_vendor=False,
    )
    db_session.add(cust)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-PIT-RET",
        project_name="Proyek PIT Retention",
        customer_id=cust.id,
        start_date=date(2024, 1, 1),
        original_contract_value=Decimal("50000000.00"),
        project_status=ProjectStatus.ACTIVE,
    )
    db_session.add(proj)
    await db_session.flush()

    # Invoice dated 2024-12-01: total 10.000.000, retention 1.000.000 -> base collectible 9.000.000
    inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=cust.id,
        project_id=proj.id,
        invoice_code="INV-PIT-RET-001",
        invoice_date=date(2024, 12, 1),
        due_date=date(2024, 12, 31),
        total_amount=Decimal("10000000.00"),
        retention_rate=Decimal("0.1000"),
        retention_amount=Decimal("1000000.00"),
        status="PARTIAL",
    )
    db_session.add(inv)
    await db_session.flush()

    # Base payment in 2024
    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-PIT-RET-PAY-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2024, 12, 15),
        amount=Decimal("9000000.00"),
        description="Pelunasan base invoice 2024",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("9000000.00"),
        created_at=datetime(2024, 12, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(alloc)

    # Retention release occurs in 2025
    ret_rel = CustomerRetentionRelease(
        organization_id=org.id,
        invoice_id=inv.id,
        release_code="REL-PIT-2025-001",
        release_date=date(2025, 1, 10),
        release_amount=Decimal("1000000.00"),
    )
    db_session.add(ret_rel)
    await db_session.commit()

    # 1. As of 2024-12-31: retention not yet released -> collectible = 9M, paid = 9M -> settled (excluded)
    report_2024 = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2024, 12, 31),
    )
    assert len(report_2024.invoices) == 0, "Invoice with unreleased retention paid in full should not appear in 2024"
    assert report_2024.summary.total == Decimal("0.00")

    # 2. As of 2025-01-15: retention released on 2025-01-10 -> collectible = 10M, paid = 9M -> outstanding 1M
    report_2025 = await ARAgingService.get_ar_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2025, 1, 15),
    )
    assert len(report_2025.invoices) == 1, "Invoice must appear in aging report after retention release in 2025"
    assert report_2025.invoices[0].outstanding_amount == Decimal("1000000.00")
    assert report_2025.invoices[0].total_amount == Decimal("10000000.00")
    assert report_2025.invoices[0].paid_amount == Decimal("9000000.00")
    assert report_2025.summary.total == Decimal("10000000.00") or report_2025.summary.total == Decimal("1000000.00")
    assert report_2025.summary.total == Decimal("1000000.00")
