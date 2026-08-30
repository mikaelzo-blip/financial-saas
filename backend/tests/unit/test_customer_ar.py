import uuid
from decimal import Decimal
from datetime import date, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType
from src.models.transaction import Transaction
from src.services.receivable_service import CustomerARService
from src.core.exceptions import InvariantViolationException


@pytest.mark.asyncio
async def test_due_date_priority_and_overpayment_rejection(db_session: AsyncSession):
    """Test 3-tier due date calculation and overpayment review routing."""
    org = Organization(slug="org-ar-unit", legal_name="Org AR Unit", default_payment_term_days=45)
    db_session.add(org)
    await db_session.flush()

    customer = Counterparty(organization_id=org.id, name="PT Properti Jaya", is_customer=True)
    db_session.add(customer)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-301",
        project_name="Mall Kota",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    ar_svc = CustomerARService(db_session)

    # 1. Invoice with Org Default (45 days)
    inv1 = await ar_svc.issue_customer_invoice(
        organization_id=org.id,
        customer_id=customer.id,
        project_id=project.id,
        invoice_date=date(2026, 3, 1),
        total_amount=Decimal("100000000.00")
    )
    await db_session.commit()
    assert inv1.due_date == date(2026, 3, 1) + timedelta(days=45)
    assert inv1.due_date_override_reason is None

    # 2. Invoice with Explicit Due Date Override
    inv2 = await ar_svc.issue_customer_invoice(
        organization_id=org.id,
        customer_id=customer.id,
        project_id=project.id,
        invoice_date=date(2026, 3, 1),
        total_amount=Decimal("50000000.00"),
        explicit_due_date=date(2026, 3, 15),
        override_reason="Termin Khusus SPK Addendum"
    )
    await db_session.commit()
    assert inv2.due_date == date(2026, 3, 15)
    assert inv2.due_date_override_reason == "Termin Khusus SPK Addendum"

    # 3. Overpayment rejection: Trying to allocate Rp 120.000.000 against Rp 100.000.000 invoice
    pay_trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000030",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 3, 20),
        amount=Decimal("120000000.00"),
        description="Pembayaran Berlebih"
    )
    db_session.add(pay_trx)
    await db_session.commit()

    with pytest.raises(InvariantViolationException) as exc:
        await ar_svc.allocate_customer_payment(org.id, pay_trx.id, [(inv1.id, Decimal("120000000.00"))])
    assert "Customer payment amount (120000000.00) exceeds outstanding balance" in str(exc.value)
