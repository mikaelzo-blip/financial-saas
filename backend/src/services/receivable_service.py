import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.transaction import Transaction
from src.models.enums import TransactionType, WorkflowStatus
from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


class CustomerARService:
    """
    Manages Accounts Receivable sub-ledger, Customer Invoices, Due Dates, and Payment Allocations.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_invoice_code(self, organization_id: uuid.UUID, invoice_date: Optional[date] = None) -> str:
        year = (invoice_date or date.today()).year
        prefix = f"INV-{year}-"

        stmt = select(func.count()).select_from(CustomerInvoice).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.invoice_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def calculate_effective_due_date(
        self,
        organization_id: uuid.UUID,
        invoice_date: date,
        explicit_due_date: Optional[date] = None,
        override_reason: Optional[str] = None
    ) -> Tuple[date, Optional[str]]:
        """
        Determines effective invoice due date following 3-tier priority:
        1. Explicit contractual / user date.
        2. Organization default payment term (e.g. Net 30).
        """
        if explicit_due_date:
            return explicit_due_date, override_reason or "EXPLICIT_CONTRACTUAL_OVERRIDE"

        org_stmt = select(Organization).where(Organization.id == organization_id)
        org = await self.session.scalar(org_stmt)
        term_days = org.default_payment_term_days if org else 30
        computed_date = invoice_date + timedelta(days=term_days)
        return computed_date, None

    async def issue_customer_invoice(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        project_id: uuid.UUID,
        invoice_date: date,
        total_amount: Decimal,
        explicit_due_date: Optional[date] = None,
        override_reason: Optional[str] = None,
        transaction_id: Optional[uuid.UUID] = None,
        invoice_code: Optional[str] = None
    ) -> CustomerInvoice:
        if transaction_id:
            existing = await self.session.scalar(select(CustomerInvoice).where(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.transaction_id == transaction_id,
            ))
            if existing:
                return await self.get_invoice(organization_id, existing.id)
        code = invoice_code or await self.generate_invoice_code(organization_id, invoice_date)
        due_date, reason = await self.calculate_effective_due_date(
            organization_id, invoice_date, explicit_due_date, override_reason
        )

        invoice = CustomerInvoice(
            organization_id=organization_id,
            invoice_code=code,
            customer_id=customer_id,
            project_id=project_id,
            invoice_date=invoice_date,
            due_date=due_date,
            due_date_override_reason=reason,
            total_amount=total_amount,
            transaction_id=transaction_id,
            status="UNPAID"
        )
        self.session.add(invoice)
        await self.session.flush()
        return await self.get_invoice(organization_id, invoice.id)

    async def get_invoice(self, organization_id: uuid.UUID, invoice_id: uuid.UUID) -> CustomerInvoice:
        stmt = (
            select(CustomerInvoice)
            .options(selectinload(CustomerInvoice.allocations))
            .execution_options(populate_existing=True)
            .where(
                and_(
                    CustomerInvoice.organization_id == organization_id,
                    CustomerInvoice.id == invoice_id
                )
            )
        )
        inv = await self.session.scalar(stmt)
        if not inv:
            raise EntityNotFoundException("Customer Invoice", invoice_id)
        return inv

    async def allocate_customer_payment(
        self,
        organization_id: uuid.UUID,
        payment_transaction_id: uuid.UUID,
        invoice_allocations: List[Tuple[uuid.UUID, Decimal]]
    ) -> List[CustomerPaymentAllocation]:
        """
        Allocates customer payment against one or multiple customer invoices.
        If allocated amount exceeds outstanding balance, raises InvariantViolationException (routes to review).
        """
        if not invoice_allocations:
            raise InvariantViolationException("Customer payment requires at least one invoice allocation.")
        payment = await self.session.scalar(select(Transaction).where(
            Transaction.id == payment_transaction_id,
            Transaction.organization_id == organization_id,
        ))
        if not payment:
            raise EntityNotFoundException("Customer Payment Transaction", payment_transaction_id)
        if payment.transaction_type != TransactionType.CUSTOMER_PAYMENT:
            raise InvariantViolationException("Only CUSTOMER_PAYMENT transactions can be allocated to customer invoices.")
        if not payment.counterparty_id:
            raise InvariantViolationException("Customer payment requires a customer counterparty before allocation.")

        allocation_by_invoice: Dict[uuid.UUID, Decimal] = {}
        for invoice_id, amount in invoice_allocations:
            if amount <= Decimal("0.00"):
                raise InvariantViolationException("Customer payment allocations must be greater than zero.")
            allocation_by_invoice[invoice_id] = allocation_by_invoice.get(invoice_id, Decimal("0.00")) + amount
        existing_payment_total = await self.session.scalar(select(
            func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))
        ).where(CustomerPaymentAllocation.payment_transaction_id == payment_transaction_id))
        requested_total = sum(allocation_by_invoice.values(), Decimal("0.00"))
        if Decimal(str(existing_payment_total)) + requested_total > payment.amount:
            raise InvariantViolationException("Customer payment allocations exceed the posted payment amount.")

        invoices: Dict[uuid.UUID, CustomerInvoice] = {}
        for invoice_id, amount in allocation_by_invoice.items():
            invoice = await self.get_invoice(organization_id, invoice_id)
            if invoice.status == "CANCELLED":
                raise InvariantViolationException(f"Cancelled invoice {invoice.invoice_code} cannot receive a payment allocation.")
            if invoice.customer_id != payment.counterparty_id:
                raise InvariantViolationException("Customer payment and invoice must belong to the same customer.")
            outstanding = invoice.calculate_outstanding_amount()
            if outstanding == Decimal("0.00"):
                raise InvariantViolationException(f"Invoice {invoice.invoice_code} is already fully paid.")
            if amount > outstanding:
                raise InvariantViolationException(
                    f"Customer payment amount ({amount}) exceeds outstanding balance ({outstanding}) on {invoice.invoice_code}. Flagged AMOUNT_MISMATCH for review.",
                    details={"invoice_id": str(invoice_id), "allocated_amount": str(amount), "outstanding": str(outstanding), "excess": str(amount - outstanding)},
                )
            invoices[invoice_id] = invoice

        if payment.workflow_status != WorkflowStatus.POSTED:
            raise InvariantViolationException("Customer payment must be posted before allocation.")

        created_allocations = []
        for invoice_id, amount in allocation_by_invoice.items():
            invoice = invoices[invoice_id]
            alloc = CustomerPaymentAllocation(invoice_id=invoice_id, payment_transaction_id=payment_transaction_id, allocated_amount=amount)
            self.session.add(alloc)
            created_allocations.append(alloc)
            existing_invoice_total = sum(
                (allocation.allocated_amount for allocation in invoice.allocations), Decimal("0.00")
            )
            invoice.status = "PAID" if invoice.total_amount - existing_invoice_total - amount == Decimal("0.00") else "PARTIALLY_PAID"

        await self.session.flush()
        return created_allocations
