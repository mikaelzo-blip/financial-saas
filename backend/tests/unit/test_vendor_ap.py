import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType
from src.models.transaction import Transaction
from src.services.payable_service import VendorAPService
from src.core.exceptions import InvariantViolationException


@pytest.mark.asyncio
async def test_vendor_bill_and_payment_allocations(db_session: AsyncSession):
    """Test partial payments, multiple allocations, and derived AP balances."""
    org = Organization(slug="org-ap-unit", legal_name="Org AP Unit")
    db_session.add(org)
    await db_session.flush()

    vendor = Counterparty(organization_id=org.id, name="PT Supplier Besi", is_vendor=True)
    db_session.add(vendor)
    await db_session.flush()

    ap_svc = VendorAPService(db_session)

    # 1. Register Bill: Rp 50.000.000
    bill = await ap_svc.register_vendor_bill(
        organization_id=org.id,
        vendor_id=vendor.id,
        bill_date=date(2026, 2, 1),
        due_date=date(2026, 3, 1),
        total_amount=Decimal("50000000.00")
    )
    await db_session.commit()
    assert bill.status == "UNPAID"
    assert bill.calculate_outstanding_amount() == Decimal("50000000.00")

    # Payment transaction 1: Rp 20.000.000
    pay_trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000010",
        transaction_type=TransactionType.PAY_VENDOR_BILL,
        transaction_date=date(2026, 2, 15),
        amount=Decimal("20000000.00"),
        description="Cicilan 1 Besi"
    )
    db_session.add(pay_trx1)
    await db_session.commit()

    # Allocate Payment 1
    await ap_svc.allocate_vendor_payment(org.id, pay_trx1.id, [(bill.id, Decimal("20000000.00"))])
    await db_session.commit()

    reloaded_bill = await ap_svc.get_bill(org.id, bill.id)
    assert reloaded_bill.status == "PARTIALLY_PAID"
    assert reloaded_bill.calculate_outstanding_amount() == Decimal("30000000.00")

    # Overpayment attempt: Trying to allocate Rp 35.000.000 against Rp 30.000.000 remaining -> MUST FAIL
    pay_trx_excess = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000011",
        transaction_type=TransactionType.PAY_VENDOR_BILL,
        transaction_date=date(2026, 2, 20),
        amount=Decimal("35000000.00"),
        description="Excess Payment"
    )
    db_session.add(pay_trx_excess)
    await db_session.commit()

    with pytest.raises(InvariantViolationException):
        await ap_svc.allocate_vendor_payment(org.id, pay_trx_excess.id, [(bill.id, Decimal("35000000.00"))])


@pytest.mark.asyncio
async def test_vendor_advance_and_settlement_excess_rejection(db_session: AsyncSession):
    """Test vendor advance tracking and excess settlement rejection."""
    org = Organization(slug="org-adv-unit", legal_name="Org Advance Unit")
    db_session.add(org)
    await db_session.flush()

    vendor = Counterparty(organization_id=org.id, name="Mandor Tukang", is_vendor=True)
    trx_adv = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000020",
        transaction_type=TransactionType.VENDOR_ADVANCE,
        transaction_date=date(2026, 2, 1),
        amount=Decimal("15000000.00"),
        description="Kasbon Mandor"
    )
    db_session.add_all([vendor, trx_adv])
    await db_session.commit()

    ap_svc = VendorAPService(db_session)
    adv = await ap_svc.register_vendor_advance(
        organization_id=org.id,
        vendor_id=vendor.id,
        advance_date=date(2026, 2, 1),
        amount=Decimal("15000000.00"),
        transaction_id=trx_adv.id
    )
    await db_session.commit()

    assert adv.remaining_balance == Decimal("15000000.00")

    # Settle partial: Rp 10.000.000
    adv_settled = await ap_svc.settle_vendor_advance(org.id, adv.id, Decimal("10000000.00"))
    await db_session.commit()
    assert adv_settled.remaining_balance == Decimal("5000000.00")

    # Settle excess: Attempt to settle Rp 8.000.000 against Rp 5.000.000 remaining -> MUST RAISE InvariantViolationException
    with pytest.raises(InvariantViolationException) as exc:
        await ap_svc.settle_vendor_advance(org.id, adv.id, Decimal("8000000.00"))
    assert "Settlement amount (8000000.00) exceeds remaining advance balance" in str(exc.value)
