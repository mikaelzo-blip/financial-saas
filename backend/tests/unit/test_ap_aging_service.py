import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.payable import VendorBill, VendorAdvance
from src.models.transaction import Transaction
from src.models.enums import TransactionType, WorkflowStatus
from src.services.reporting.ap_aging_service import APAgingService


@pytest.mark.asyncio
async def test_ap_aging_buckets(db_session: AsyncSession):
    org = Organization(slug="pt-ap-test", legal_name="PT AP Test")
    db_session.add(org)
    await db_session.flush()

    vend = Counterparty(
        organization_id=org.id,
        name="PT Supplier Baja",
        is_customer=False,
        is_vendor=True
    )
    db_session.add(vend)
    await db_session.flush()

    today = date(2026, 6, 1)

    # 1. Current Bill
    bill1 = VendorBill(
        organization_id=org.id,
        vendor_id=vend.id,
        bill_code="BILL-001",
        bill_date=date(2026, 5, 25),
        due_date=date(2026, 6, 25),
        total_amount=Decimal("15000000.00"),
        status="UNPAID"
    )
    # 2. 75 days overdue (bucket 61_90)
    bill2 = VendorBill(
        organization_id=org.id,
        vendor_id=vend.id,
        bill_code="BILL-002",
        bill_date=date(2026, 2, 10),
        due_date=date(2026, 3, 18),
        total_amount=Decimal("25000000.00"),
        status="UNPAID"
    )

    trx_adv = Transaction(
        organization_id=org.id,
        transaction_code="TRX-ADV-01",
        transaction_type=TransactionType.VENDOR_ADVANCE,
        transaction_date=date(2026, 5, 1),
        amount=Decimal("10000000.00"),
        description="Kasbon vendor",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_adv)
    await db_session.flush()

    # 3. Vendor advance unsettled: 5M
    adv = VendorAdvance(
        organization_id=org.id,
        vendor_id=vend.id,
        advance_code="ADV-001",
        advance_date=date(2026, 5, 1),
        original_amount=Decimal("10000000.00"),
        settled_amount=Decimal("5000000.00"),
        remaining_balance=Decimal("5000000.00"),
        transaction_id=trx_adv.id
    )
    db_session.add_all([bill1, bill2, adv])
    await db_session.commit()

    ap_report = await APAgingService.get_ap_aging(
        session=db_session,
        organization_id=org.id,
        as_of_date=today
    )

    assert ap_report.summary.current == Decimal("15000000.00")
    assert ap_report.summary.days_61_90 == Decimal("25000000.00")
    assert ap_report.summary.total == Decimal("40000000.00")
    assert ap_report.unsettled_advances_total == Decimal("5000000.00")
    assert len(ap_report.bills) == 2
