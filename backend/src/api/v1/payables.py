import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_current_org_id
from src.core.database import get_db
from src.core.exceptions import EntityNotFoundException, InvariantViolationException
from src.models.enums import TransactionType, WorkflowStatus
from src.models.payable import VendorBill
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.payable_service import VendorAPService
from src.services.transaction_service import TransactionService

router = APIRouter(prefix="/vendor-bills", tags=["Payables"])
vendor_payments_router = APIRouter(prefix="/vendor-payments", tags=["Payables"])


class VendorBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    project_id: Optional[uuid.UUID] = None
    project_name: Optional[str] = None
    bill_number: str
    bill_date: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    status: str
    bill_status: str
    transaction_id: uuid.UUID
    created_at: object


class VendorPaymentCreate(BaseModel):
    bill_id: uuid.UUID
    payment_account_id: uuid.UUID
    amount: Decimal
    payment_date: date
    reference_no: Optional[str] = None
    description: Optional[str] = None


class VendorPaymentResponse(BaseModel):
    payment_transaction_id: uuid.UUID
    allocation_id: uuid.UUID
    journal_entry_id: uuid.UUID
    bill_id: uuid.UUID
    amount: Decimal
    bill_status: str
    outstanding_amount: Decimal


@router.get("", response_model=list[VendorBillResponse])
async def list_vendor_bills(
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    bills = (await db.scalars(
        select(VendorBill)
        .options(
            selectinload(VendorBill.vendor),
            selectinload(VendorBill.project),
            selectinload(VendorBill.allocations),
        )
        .where(VendorBill.organization_id == organization_id)
        .order_by(VendorBill.bill_date.desc(), VendorBill.bill_code.desc())
    )).all()
    today = date.today()
    response = []
    for bill in bills:
        paid = bill.calculate_paid_amount()
        outstanding = bill.calculate_outstanding_amount()
        if outstanding == Decimal("0.00"):
            status = "PAID"
        elif bill.due_date < today:
            status = "OVERDUE"
        elif bill.due_date == today:
            status = "DUE"
        else:
            status = "NOT_DUE"
        response.append(VendorBillResponse(
            id=bill.id,
            organization_id=bill.organization_id,
            vendor_id=bill.vendor_id,
            vendor_name=bill.vendor.name if bill.vendor else "",
            project_id=bill.project_id,
            project_name=bill.project.project_name if bill.project else None,
            bill_number=bill.bill_code,
            bill_date=bill.bill_date,
            due_date=bill.due_date,
            total_amount=bill.total_amount,
            paid_amount=paid,
            outstanding_amount=outstanding,
            status=status,
            bill_status=bill.status,
            transaction_id=bill.transaction_id,
            created_at=bill.created_at,
        ))
    return response


@vendor_payments_router.post("", response_model=VendorPaymentResponse, status_code=201)
async def record_vendor_payment(
    data: VendorPaymentCreate,
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    ap_service = VendorAPService(db)
    bill = await ap_service.get_bill(organization_id, data.bill_id)
    if not bill:
        raise EntityNotFoundException(f"Vendor bill {data.bill_id} not found.")
    if bill.status == "CANCELLED":
        raise InvariantViolationException(f"Cancelled bill {bill.bill_code} cannot receive a payment allocation.")
    outstanding = bill.calculate_outstanding_amount()
    if outstanding == Decimal("0.00"):
        raise InvariantViolationException(f"Vendor bill {bill.bill_code} is already fully paid.")
    if data.amount > outstanding:
        raise InvariantViolationException(
            f"Vendor payment amount ({data.amount}) exceeds outstanding balance ({outstanding}) on {bill.bill_code}."
        )
    payment = await TransactionService(db).create_transaction(
        organization_id,
        TransactionCreate(
            transaction_type=TransactionType.PAY_VENDOR_BILL,
            transaction_date=data.payment_date,
            amount=data.amount,
            counterparty_id=bill.vendor_id,
            project_id=bill.project_id,
            payment_account_id=data.payment_account_id,
            reference_no=data.reference_no,
            description=data.description or f"Pembayaran tagihan {bill.bill_code}",
            source_channel="WEB",
        ),
    )
    if payment.workflow_status == WorkflowStatus.REVIEW_REQUIRED:
        raise InvariantViolationException(
            "Possible duplicate vendor payment is routed to review and will not be posted automatically."
        )
    journal = await AccountingEngine(db).post_transaction(organization_id, payment.id)
    allocations = await ap_service.allocate_vendor_payment(
        organization_id, payment.id, [(bill.id, data.amount)]
    )
    refreshed_bill = await ap_service.get_bill(organization_id, bill.id)
    return VendorPaymentResponse(
        payment_transaction_id=payment.id,
        allocation_id=allocations[0].id,
        journal_entry_id=journal.id,
        bill_id=bill.id,
        amount=data.amount,
        bill_status=refreshed_bill.status,
        outstanding_amount=refreshed_bill.calculate_outstanding_amount(),
    )
