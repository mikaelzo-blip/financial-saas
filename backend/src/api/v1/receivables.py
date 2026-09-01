import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_current_org_id
from src.core.database import get_db
from src.core.exceptions import InvariantViolationException
from src.models.enums import TransactionType, WorkflowStatus
from src.models.receivable import CustomerInvoice
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.receivable_service import CustomerARService
from src.services.transaction_service import TransactionService


router = APIRouter(prefix="/customer-invoices", tags=["Accounts Receivable"])
customer_payments_router = APIRouter(prefix="/customer-payments", tags=["Accounts Receivable"])


class CustomerInvoiceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    project_id: uuid.UUID
    project_name: str
    invoice_number: str
    invoice_date: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    collection_status: str
    status: str
    transaction_id: uuid.UUID | None
    created_at: datetime


class CustomerPaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    payment_account_id: uuid.UUID
    amount: Decimal
    payment_date: date
    reference_no: str | None = None
    description: str


class CustomerPaymentResponse(BaseModel):
    payment_transaction_id: uuid.UUID
    allocation_id: uuid.UUID
    journal_entry_id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    invoice_status: str
    outstanding_amount: Decimal


@router.get("", response_model=list[CustomerInvoiceResponse])
async def list_customer_invoices(
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    invoices = (await db.scalars(
        select(CustomerInvoice)
        .options(
            selectinload(CustomerInvoice.customer),
            selectinload(CustomerInvoice.project),
            selectinload(CustomerInvoice.allocations),
        )
        .where(CustomerInvoice.organization_id == organization_id)
        .order_by(CustomerInvoice.invoice_date.desc(), CustomerInvoice.invoice_code.desc())
    )).all()
    today = date.today()
    response = []
    for invoice in invoices:
        paid = invoice.calculate_paid_amount()
        outstanding = invoice.calculate_outstanding_amount()
        if outstanding == 0:
            collection_status = "COLLECTED"
        elif invoice.due_date < today:
            collection_status = "OVERDUE"
        elif invoice.due_date == today:
            collection_status = "DUE"
        else:
            collection_status = "NOT_DUE"
        response.append(CustomerInvoiceResponse(
            id=invoice.id,
            organization_id=invoice.organization_id,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            project_id=invoice.project_id,
            project_name=invoice.project.project_name,
            invoice_number=invoice.invoice_code,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            total_amount=invoice.total_amount,
            paid_amount=paid,
            outstanding_amount=outstanding,
            collection_status=collection_status,
            status=invoice.status,
            transaction_id=invoice.transaction_id,
            created_at=invoice.created_at,
        ))
    return response


@customer_payments_router.post("", response_model=CustomerPaymentResponse, status_code=201)
async def record_customer_payment(
    data: CustomerPaymentCreate,
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    ar_service = CustomerARService(db)
    invoice = await ar_service.get_invoice(organization_id, data.invoice_id)
    if invoice.status == "CANCELLED":
        raise InvariantViolationException(f"Cancelled invoice {invoice.invoice_code} cannot receive a payment allocation.")
    outstanding = invoice.calculate_outstanding_amount()
    if outstanding == Decimal("0.00"):
        raise InvariantViolationException(f"Invoice {invoice.invoice_code} is already fully paid.")
    if data.amount > outstanding:
        raise InvariantViolationException(
            f"Customer payment amount ({data.amount}) exceeds outstanding balance ({outstanding}) on {invoice.invoice_code}."
        )
    payment = await TransactionService(db).create_transaction(
        organization_id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_PAYMENT,
            transaction_date=data.payment_date,
            amount=data.amount,
            counterparty_id=invoice.customer_id,
            payment_account_id=data.payment_account_id,
            reference_no=data.reference_no,
            description=data.description,
            source_channel="WEB",
        ),
    )
    if payment.workflow_status == WorkflowStatus.REVIEW_REQUIRED:
        raise InvariantViolationException(
            "Possible duplicate customer payment is routed to review and will not be posted automatically."
        )
    journal = await AccountingEngine(db).post_transaction(organization_id, payment.id)
    allocations = await ar_service.allocate_customer_payment(
        organization_id, payment.id, [(invoice.id, data.amount)]
    )
    refreshed_invoice = await ar_service.get_invoice(organization_id, invoice.id)
    return CustomerPaymentResponse(
        payment_transaction_id=payment.id,
        allocation_id=allocations[0].id,
        journal_entry_id=journal.id,
        invoice_id=invoice.id,
        amount=data.amount,
        invoice_status=refreshed_invoice.status,
        outstanding_amount=refreshed_invoice.calculate_outstanding_amount(),
    )
