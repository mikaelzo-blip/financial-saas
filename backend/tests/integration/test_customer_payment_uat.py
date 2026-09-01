from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import EntityNotFoundException, InvariantViolationException
from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import ProjectStatus, TransactionType, WorkflowStatus
from src.models.journal import JournalLine
from src.models.organization import Organization
from src.models.project import Project
from src.models.receivable import CustomerInvoice
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.receivable_service import CustomerARService
from src.services.transaction_service import TransactionService


async def create_customer_invoice(
    session: AsyncSession,
    organization_id,
    customer_id,
    project_id,
    invoice_number: str,
    amount: Decimal,
) -> CustomerInvoice:
    transaction = await TransactionService(session).create_transaction(
        organization_id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1),
            amount=amount,
            counterparty_id=customer_id,
            project_id=project_id,
            reference_no=invoice_number,
            description=f"Invoice {invoice_number}",
        ),
    )
    await session.commit()
    await AccountingEngine(session).post_transaction(organization_id, transaction.id)
    await session.commit()
    return await session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == transaction.id))


async def setup_customer_payment_context(session: AsyncSession, slug: str):
    organization = Organization(slug=slug, legal_name=f"Org {slug}")
    session.add(organization)
    await session.flush()
    await seed_standard_coa(session, organization.id)
    await seed_standard_payment_accounts(session, organization.id)
    customer = Counterparty(organization_id=organization.id, name=f"Customer {slug}", is_customer=True)
    other_customer = Counterparty(organization_id=organization.id, name=f"Other customer {slug}", is_customer=True)
    session.add_all([customer, other_customer])
    await session.flush()
    project = Project(
        organization_id=organization.id,
        project_code=f"PRJ-{slug}",
        project_name=f"Project {slug}",
        customer_id=customer.id,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 9, 1),
        project_status=ProjectStatus.ACTIVE,
    )
    session.add(project)
    await session.commit()
    payment_account = await session.scalar(select(PaymentAccount).where(
        PaymentAccount.organization_id == organization.id,
        PaymentAccount.name == "Bank Mandiri",
    ))
    return organization, customer, other_customer, project, payment_account


@pytest.mark.asyncio
async def test_customer_payment_api_posts_and_fully_allocates_without_revenue_recognition(client, db_session: AsyncSession):
    organization, customer, _, project, payment_account = await setup_customer_payment_context(db_session, "customer-payment-api")
    invoice = await create_customer_invoice(
        db_session, organization.id, customer.id, project.id, "INV-PAYMENT-001", Decimal("25000000.00")
    )

    response = await client.post(
        "/api/v1/customer-payments",
        headers={"X-Organization-ID": str(organization.id)},
        json={
            "invoice_id": str(invoice.id),
            "payment_account_id": str(payment_account.id),
            "amount": "25000000.00",
            "payment_date": "2026-09-02",
            "reference_no": "PAY-PAYMENT-001",
            "description": "Pelunasan invoice customer",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["invoice_id"] == str(invoice.id)
    assert payload["amount"] == "25000000.00"
    assert payload["invoice_status"] == "PAID"
    assert payload["outstanding_amount"] == "0.00"

    payment = await TransactionService(db_session).get_transaction(
        organization.id, UUID(payload["payment_transaction_id"])
    )
    assert payment.transaction_type == TransactionType.CUSTOMER_PAYMENT
    assert payment.workflow_status == WorkflowStatus.POSTED
    assert payment.counterparty_id == customer.id
    assert payment.payment_account_id == payment_account.id
    assert payment.reference_no == "PAY-PAYMENT-001"
    assert payment.description == "Pelunasan invoice customer"

    refreshed_invoice = await CustomerARService(db_session).get_invoice(organization.id, invoice.id)
    assert refreshed_invoice.calculate_paid_amount() == Decimal("25000000.00")
    assert refreshed_invoice.calculate_outstanding_amount() == Decimal("0.00")
    assert refreshed_invoice.status == "PAID"

    journal_lines = (await db_session.scalars(
        select(JournalLine).where(
            JournalLine.journal_entry_id == UUID(payload["journal_entry_id"])
        ).order_by(JournalLine.line_number)
    )).all()
    assert [(line.debit_amount, line.credit_amount) for line in journal_lines] == [
        (Decimal("25000000.00"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("25000000.00")),
    ]


@pytest.mark.asyncio
async def test_customer_payment_allocation_rejects_customer_and_tenant_mismatches(db_session: AsyncSession):
    organization, customer, other_customer, project, payment_account = await setup_customer_payment_context(db_session, "customer-payment-safety")
    invoice = await create_customer_invoice(
        db_session, organization.id, customer.id, project.id, "INV-SAFETY-001", Decimal("100.00")
    )
    payment = await TransactionService(db_session).create_transaction(
        organization.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("100.00"),
            counterparty_id=other_customer.id,
            payment_account_id=payment_account.id,
            reference_no="PAY-SAFETY-001",
            description="Wrong customer payment",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(organization.id, payment.id)
    await db_session.commit()

    with pytest.raises(InvariantViolationException, match="same customer"):
        await CustomerARService(db_session).allocate_customer_payment(
            organization.id, payment.id, [(invoice.id, Decimal("100.00"))]
        )

    other_org, other_customer_tenant, _, other_project, _ = await setup_customer_payment_context(db_session, "customer-payment-other-tenant")
    other_invoice = await create_customer_invoice(
        db_session, other_org.id, other_customer_tenant.id, other_project.id, "INV-OTHER-TENANT", Decimal("100.00")
    )
    with pytest.raises(EntityNotFoundException):
        await CustomerARService(db_session).allocate_customer_payment(
            organization.id, payment.id, [(other_invoice.id, Decimal("100.00"))]
        )


@pytest.mark.asyncio
async def test_customer_payment_allocation_rejects_overpayment_and_duplicate_replay(db_session: AsyncSession):
    organization, customer, _, project, payment_account = await setup_customer_payment_context(db_session, "customer-payment-limits")
    invoice = await create_customer_invoice(
        db_session, organization.id, customer.id, project.id, "INV-LIMITS-001", Decimal("100.00")
    )
    payment = await TransactionService(db_session).create_transaction(
        organization.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=date(2026, 9, 2),
            amount=Decimal("200.00"),
            counterparty_id=customer.id,
            payment_account_id=payment_account.id,
            reference_no="PAY-LIMITS-001",
            description="Payment limits",
        ),
    )
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(organization.id, payment.id)
    await db_session.commit()

    service = CustomerARService(db_session)
    with pytest.raises(InvariantViolationException, match="exceeds outstanding"):
        await service.allocate_customer_payment(organization.id, payment.id, [(invoice.id, Decimal("100.01"))])

    allocations = await service.allocate_customer_payment(organization.id, payment.id, [(invoice.id, Decimal("100.00"))])
    await db_session.commit()
    assert allocations[0].allocated_amount == Decimal("100.00")

    with pytest.raises(InvariantViolationException, match="already fully paid"):
        await service.allocate_customer_payment(organization.id, payment.id, [(invoice.id, Decimal("0.01"))])
