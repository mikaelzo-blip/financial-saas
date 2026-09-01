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
from src.models.receivable import CustomerInvoice


router = APIRouter(prefix="/customer-invoices", tags=["Accounts Receivable"])


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
