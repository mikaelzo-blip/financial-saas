import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
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
        transaction_id: Optional[uuid.UUID] = None
    ) -> CustomerInvoice:
        code = await self.generate_invoice_code(organization_id, invoice_date)
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
        created_allocations = []
        for inv_id, amount in invoice_allocations:
            inv = await self.get_invoice(organization_id, inv_id)
            current_outstanding = inv.calculate_outstanding_amount()

            if amount > current_outstanding:
                raise InvariantViolationException(
                    f"Customer payment amount ({amount}) exceeds outstanding balance ({current_outstanding}) on {inv.invoice_code}. Flagged AMOUNT_MISMATCH for review.",
                    details={
                        "invoice_id": str(inv_id),
                        "allocated_amount": str(amount),
                        "outstanding": str(current_outstanding),
                        "excess": str(amount - current_outstanding)
                    }
                )

            alloc = CustomerPaymentAllocation(
                invoice_id=inv_id,
                payment_transaction_id=payment_transaction_id,
                allocated_amount=amount
            )
            self.session.add(alloc)
            created_allocations.append(alloc)

            new_outstanding = current_outstanding - amount
            inv.status = "PAID" if new_outstanding == Decimal("0.00") else "PARTIALLY_PAID"

        await self.session.flush()
        return created_allocations
