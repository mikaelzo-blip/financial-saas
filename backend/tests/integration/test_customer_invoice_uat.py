from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import EntityNotFoundException, InvariantViolationException
from src.models.audit import AuditLog
from src.models.coa import ChartOfAccount
from src.models.counterparty import Counterparty
from src.models.enums import AccountType, ProjectStatus, ReviewFlag, TransactionType, WorkflowStatus
from src.models.journal import JournalEntry, JournalLine
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.schemas.transaction import TransactionAllocationInput, TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.reversal_service import ReversalService
from src.services.transaction_service import TransactionService


async def setup_invoice_context(db: AsyncSession, slug: str):
    org = Organization(slug=slug, legal_name=f"Org {slug}")
    db.add(org)
    await db.flush()
    await seed_standard_coa(db, org.id)
    await seed_standard_payment_accounts(db, org.id)
    customer = Counterparty(organization_id=org.id, name=f"Customer {slug}", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name=f"Vendor {slug}", is_vendor=True)
    db.add_all([customer, vendor])
    await db.flush()
    project = Project(
        organization_id=org.id,
        project_code=f"PRJ-{slug}",
        project_name=f"Project {slug}",
        customer_id=customer.id,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 9, 1),
        project_status=ProjectStatus.ACTIVE,
    )
    db.add(project)
    await db.commit()
    return org, customer, vendor, project


@pytest.mark.asyncio
async def test_post_customer_invoice_creates_authoritative_ar_without_cash_cost_or_ap(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-uat")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1),
            amount=Decimal("25000000.00"),
            counterparty_id=customer.id,
            project_id=project.id,
            reference_no="INV-DEMO-001",
            description="Termin proyek demo perbaikan panel listrik",
        ),
    )
    await db_session.commit()

    journal = await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    invoice = await db_session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == transaction.id))
    assert invoice is not None
    assert invoice.invoice_code == "INV-DEMO-001"
    assert invoice.organization_id == org.id
    assert invoice.customer_id == customer.id
    assert invoice.project_id == project.id
    assert invoice.invoice_date == date(2026, 9, 1)
    assert invoice.total_amount == Decimal("25000000.00")
    assert invoice.status == "UNPAID"
    assert invoice.calculate_outstanding_amount() == Decimal("25000000.00")

    lines = (await db_session.scalars(
        select(JournalLine).where(JournalLine.journal_entry_id == journal.id).order_by(JournalLine.line_number)
    )).all()
    accounts = {account.id: account.account_code for account in (await db_session.scalars(
        select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id)
    )).all()}
    assert [(accounts[line.account_id], line.debit_amount, line.credit_amount) for line in lines] == [
        ("1201", Decimal("25000000.00"), Decimal("0.00")),
        ("4101", Decimal("0.00"), Decimal("25000000.00")),
    ]
    assert journal.total_debit == journal.total_credit == Decimal("25000000.00")

    cash = await db_session.scalar(
        select(func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), 0))
        .join(JournalEntry).join(ChartOfAccount)
        .where(JournalEntry.organization_id == org.id, ChartOfAccount.account_code.like("1101%"))
    )
    project_cost = await db_session.scalar(
        select(func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), 0))
        .join(JournalEntry).join(ChartOfAccount)
        .where(
            JournalEntry.organization_id == org.id,
            JournalLine.project_id == project.id,
            ChartOfAccount.account_type == AccountType.EXPENSE,
        )
    )
    assert Decimal(str(cash)) == Decimal("0.00")
    assert Decimal(str(project_cost)) == Decimal("0.00")
    assert await db_session.scalar(select(func.count()).select_from(VendorBill).where(VendorBill.organization_id == org.id)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.organization_id == org.id,
        AuditLog.entity_name == "Transaction",
        AuditLog.entity_id == transaction.id,
        AuditLog.action == "POST",
    )) == 1


@pytest.mark.asyncio
async def test_customer_invoice_rejects_invalid_customer_project_relationships(db_session: AsyncSession):
    org, customer, vendor, project = await setup_invoice_context(db_session, "invoice-validation")
    other_customer = Counterparty(organization_id=org.id, name="Other Customer", is_customer=True)
    db_session.add(other_customer)
    await db_session.commit()
    service = TransactionService(db_session)

    with pytest.raises(InvariantViolationException, match="customer assigned to the project"):
        await service.create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("1.00"),
            counterparty_id=other_customer.id, project_id=project.id,
            reference_no="INV-WRONG-CUSTOMER", description="Invalid customer",
        ))
    with pytest.raises(InvariantViolationException, match="must be a customer"):
        await service.create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("1.00"),
            counterparty_id=vendor.id, project_id=project.id,
            reference_no="INV-VENDOR", description="Invalid vendor",
        ))
    with pytest.raises(EntityNotFoundException):
        await service.create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("1.00"),
            counterparty_id=customer.id, project_id=uuid4(),
            reference_no="INV-NO-PROJECT", description="Invalid project",
        ))


@pytest.mark.asyncio
async def test_customer_invoice_validates_project_from_allocations(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-split")
    other_project = Project(
        organization_id=org.id,
        project_code="PRJ-INVOICE-SPLIT-OTHER",
        project_name="Other Project",
        customer_id=customer.id,
        original_contract_value=Decimal("100.00"),
        revised_contract_value=Decimal("100.00"),
        start_date=date(2026, 9, 1),
        project_status=ProjectStatus.ACTIVE,
    )
    db_session.add(other_project)
    await db_session.commit()
    service = TransactionService(db_session)

    transaction = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("10.00"),
        counterparty_id=customer.id,
        reference_no="INV-SPLIT", description="Split invoice",
        allocations=[TransactionAllocationInput(project_id=project.id, amount=Decimal("10.00"))],
    ))
    assert [allocation.project_id for allocation in transaction.allocations] == [project.id]

    with pytest.raises(InvariantViolationException, match="one project"):
        await service.create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("10.00"),
            counterparty_id=customer.id, project_id=project.id,
            reference_no="INV-CONFLICT", description="Conflicting projects",
            allocations=[TransactionAllocationInput(project_id=other_project.id, amount=Decimal("10.00"))],
        ))

    with pytest.raises(InvariantViolationException, match="every allocation"):
        await service.create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("10.00"),
            counterparty_id=customer.id, project_id=project.id,
            reference_no="INV-UNALLOCATED", description="Unallocated invoice",
            allocations=[TransactionAllocationInput(amount=Decimal("10.00"))],
        ))


@pytest.mark.asyncio
async def test_customer_invoice_rejects_invoice_number_over_50_characters(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-code-length")

    with pytest.raises(InvariantViolationException, match="50 characters"):
        await TransactionService(db_session).create_transaction(org.id, TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 9, 1), amount=Decimal("10.00"),
            counterparty_id=customer.id, project_id=project.id,
            reference_no="I" * 51, description="Invoice number too long",
        ))


@pytest.mark.asyncio
async def test_customer_invoice_duplicate_and_tenant_isolation(db_session: AsyncSession):
    org_a, customer_a, _, project_a = await setup_invoice_context(db_session, "invoice-tenant-a")
    org_b, customer_b, _, project_b = await setup_invoice_context(db_session, "invoice-tenant-b")
    service = TransactionService(db_session)

    first = await service.create_transaction(org_a.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer_a.id, project_id=project_a.id,
        reference_no="INV-SHARED", description="First invoice",
    ))
    await db_session.commit()
    duplicate = await service.create_transaction(org_a.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer_a.id, project_id=project_a.id,
        reference_no="INV-SHARED", description="Duplicate invoice",
    ))
    separate_tenant = await service.create_transaction(org_b.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer_b.id, project_id=project_b.id,
        reference_no="INV-SHARED", description="Separate tenant invoice",
    ))

    assert first.workflow_status == WorkflowStatus.STAGED
    assert duplicate.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert [flag.flag for flag in duplicate.review_flags] == [ReviewFlag.DUPLICATE_SUSPECTED]
    assert separate_tenant.workflow_status == WorkflowStatus.STAGED


@pytest.mark.asyncio
async def test_customer_invoice_number_collision_routes_to_review(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-code-collision")
    service = TransactionService(db_session)
    await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("100.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-COLLISION", description="First invoice",
    ))
    await db_session.commit()

    collision = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 5), amount=Decimal("200.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-COLLISION", description="Conflicting invoice number",
    ))

    assert collision.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert [flag.flag for flag in collision.review_flags] == [ReviewFlag.DUPLICATE_SUSPECTED]


@pytest.mark.asyncio
async def test_reversing_customer_invoice_cancels_ar_and_reserves_invoice_number(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-reversal")
    service = TransactionService(db_session)
    transaction = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-REVERSED", description="Invoice to reverse",
    ))
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    await ReversalService(db_session).reverse_transaction(
        org.id, transaction.id, "Customer invoice correction", reversal_date=date(2026, 9, 2)
    )
    await db_session.commit()

    invoice = await db_session.scalar(select(CustomerInvoice).where(CustomerInvoice.transaction_id == transaction.id))
    assert invoice.status == "CANCELLED"
    assert invoice.calculate_outstanding_amount() == Decimal("0.00")

    replacement = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 2), amount=Decimal("25000000.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-REVERSED", description="Attempted number reuse",
    ))
    assert replacement.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert [flag.flag for flag in replacement.review_flags] == [ReviewFlag.DUPLICATE_SUSPECTED]


@pytest.mark.asyncio
async def test_customer_invoice_with_allocated_payment_cannot_be_reversed(db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-paid-reversal")
    service = TransactionService(db_session)
    invoice_transaction = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-PAID", description="Paid invoice",
    ))
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, invoice_transaction.id)
    await db_session.commit()
    invoice = await db_session.scalar(select(CustomerInvoice).where(
        CustomerInvoice.transaction_id == invoice_transaction.id
    ))
    payment = await service.create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 9, 2), amount=Decimal("10000000.00"),
        counterparty_id=customer.id, description="Partial payment",
    ))
    db_session.add(CustomerPaymentAllocation(
        invoice_id=invoice.id,
        payment_transaction_id=payment.id,
        allocated_amount=Decimal("10000000.00"),
    ))
    await db_session.commit()

    with pytest.raises(InvariantViolationException, match="allocated customer payments"):
        await ReversalService(db_session).reverse_transaction(
            org.id, invoice_transaction.id, "Invalid reversal", reversal_date=date(2026, 9, 3)
        )

    await db_session.refresh(invoice_transaction)
    invoice = await db_session.scalar(select(CustomerInvoice).where(
        CustomerInvoice.transaction_id == invoice_transaction.id
    ).options(selectinload(CustomerInvoice.allocations)))
    assert invoice_transaction.workflow_status == WorkflowStatus.POSTED
    assert invoice.calculate_outstanding_amount() == Decimal("15000000.00")


@pytest.mark.asyncio
async def test_customer_invoice_api_exposes_ar_subledger(client, db_session: AsyncSession):
    org, customer, _, project = await setup_invoice_context(db_session, "invoice-api")
    transaction = await TransactionService(db_session).create_transaction(org.id, TransactionCreate(
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 9, 1), amount=Decimal("25000000.00"),
        counterparty_id=customer.id, project_id=project.id,
        reference_no="INV-API-001", description="Invoice API",
    ))
    await db_session.commit()
    await AccountingEngine(db_session).post_transaction(org.id, transaction.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/customer-invoices",
        headers={"X-Organization-ID": str(org.id)},
    )

    assert response.status_code == 200
    assert response.json() == [{
        "id": response.json()[0]["id"],
        "organization_id": str(org.id),
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "project_id": str(project.id),
        "project_name": project.project_name,
        "invoice_number": "INV-API-001",
        "invoice_date": "2026-09-01",
        "due_date": "2026-10-01",
        "total_amount": "25000000.00",
        "paid_amount": "0.00",
        "outstanding_amount": "25000000.00",
        "collection_status": "NOT_DUE",
        "status": "UNPAID",
        "transaction_id": str(transaction.id),
        "created_at": response.json()[0]["created_at"],
    }]
