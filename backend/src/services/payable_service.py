import uuid
from typing import List, Optional, Tuple, Dict, Any
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.payable import VendorBill, VendorPaymentAllocation, VendorAdvance
from src.models.transaction import Transaction
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import TransactionType, WorkflowStatus
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


class VendorAPService:
    """
    Manages Accounts Payable sub-ledger, Vendor Bills, Payment Allocations, and Advances.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_bill_code(self, organization_id: uuid.UUID, bill_date: Optional[date] = None) -> str:
        year = (bill_date or date.today()).year
        prefix = f"BIL-{year}-"

        stmt = select(func.count()).select_from(VendorBill).where(
            and_(
                VendorBill.organization_id == organization_id,
                VendorBill.bill_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def calculate_effective_due_date(
        self,
        organization_id: uuid.UUID,
        vendor_id: Optional[uuid.UUID] = None,
        bill_date: Optional[date] = None,
        explicit_due_date: Optional[date] = None,
        override_reason: Optional[str] = None
    ) -> Tuple[date, Optional[str]]:
        if explicit_due_date:
            return explicit_due_date, override_reason or "EXPLICIT_CONTRACTUAL_OVERRIDE"

        b_date = bill_date or date.today()
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org = await self.session.scalar(org_stmt)
        term_days = org.default_payment_term_days if org else 30
        computed_date = b_date + timedelta(days=term_days)
        return computed_date, None

    async def generate_advance_code(self, organization_id: uuid.UUID, advance_date: Optional[date] = None) -> str:
        year = (advance_date or date.today()).year
        prefix = f"ADV-{year}-"

        stmt = select(func.count()).select_from(VendorAdvance).where(
            and_(
                VendorAdvance.organization_id == organization_id,
                VendorAdvance.advance_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def register_vendor_bill(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        bill_date: date,
        due_date: date,
        total_amount: Decimal,
        project_id: Optional[uuid.UUID] = None,
        transaction_id: Optional[uuid.UUID] = None
    ) -> VendorBill:
        bill_code = await self.generate_bill_code(organization_id, bill_date)
        bill = VendorBill(
            organization_id=organization_id,
            bill_code=bill_code,
            vendor_id=vendor_id,
            project_id=project_id,
            bill_date=bill_date,
            due_date=due_date,
            total_amount=total_amount,
            transaction_id=transaction_id,
            status="UNPAID"
        )
        self.session.add(bill)
        await self.session.flush()
        return await self.get_bill(organization_id, bill.id)

    async def get_bill(self, organization_id: uuid.UUID, bill_id: uuid.UUID) -> VendorBill:
        stmt = (
            select(VendorBill)
            .options(selectinload(VendorBill.allocations))
            .execution_options(populate_existing=True)
            .where(
                and_(
                    VendorBill.organization_id == organization_id,
                    VendorBill.id == bill_id
                )
            )
        )
        bill = await self.session.scalar(stmt)
        if not bill:
            raise EntityNotFoundException("Vendor Bill", bill_id)
        return bill

    async def allocate_vendor_payment(
        self,
        organization_id: uuid.UUID,
        payment_transaction_id: uuid.UUID,
        bill_allocations: List[Tuple[uuid.UUID, Decimal]]
    ) -> List[VendorPaymentAllocation]:
        """
        Allocates payment transaction against one or multiple vendor bills.
        """
        if not bill_allocations:
            raise InvariantViolationException("Vendor payment requires at least one bill allocation.")
        payment = await self.session.scalar(select(Transaction).where(
            Transaction.id == payment_transaction_id,
            Transaction.organization_id == organization_id,
        ))
        if not payment:
            raise EntityNotFoundException("Vendor Payment Transaction", payment_transaction_id)
        if payment.transaction_type != TransactionType.PAY_VENDOR_BILL:
            raise InvariantViolationException("Only PAY_VENDOR_BILL transactions can be allocated to vendor bills.")
        if payment.workflow_status != WorkflowStatus.POSTED:
            raise InvariantViolationException("Vendor payment must be posted before allocation.")
        if not payment.counterparty_id:
            raise InvariantViolationException("Vendor payment requires a vendor counterparty before allocation.")
        allocation_by_bill: Dict[uuid.UUID, Decimal] = {}
        for bill_id, amount in bill_allocations:
            if amount <= Decimal("0.00"):
                raise InvariantViolationException("Vendor payment allocations must be greater than zero.")
            allocation_by_bill[bill_id] = allocation_by_bill.get(bill_id, Decimal("0.00")) + amount
        existing_payment_total = await self.session.scalar(select(
            func.coalesce(func.sum(VendorPaymentAllocation.allocated_amount), Decimal("0.00"))
        ).where(VendorPaymentAllocation.payment_transaction_id == payment_transaction_id))
        requested_total = sum(allocation_by_bill.values(), Decimal("0.00"))
        if Decimal(str(existing_payment_total)) + requested_total > payment.amount:
            raise InvariantViolationException("Vendor payment allocations exceed the posted payment amount.")

        bills: Dict[uuid.UUID, VendorBill] = {}
        for bill_id, amount in allocation_by_bill.items():
            bill = await self.get_bill(organization_id, bill_id)
            if bill.status == "CANCELLED":
                raise InvariantViolationException(f"Cancelled bill {bill.bill_code} cannot receive a payment allocation.")
            if bill.vendor_id != payment.counterparty_id:
                raise InvariantViolationException("Vendor payment and bill must belong to the same vendor.")
            current_outstanding = bill.calculate_outstanding_amount()
            if current_outstanding == Decimal("0.00"):
                raise InvariantViolationException(f"Bill {bill.bill_code} is already fully paid.")

            if amount > current_outstanding:
                raise InvariantViolationException(
                    f"Allocated payment amount ({amount}) exceeds outstanding bill balance ({current_outstanding}) for {bill.bill_code}.",
                    details={"bill_id": str(bill_id), "allocated_amount": str(amount), "outstanding": str(current_outstanding)}
                )
            bills[bill_id] = bill

        created_allocations = []
        for bill_id, amount in allocation_by_bill.items():
            bill = bills[bill_id]
            current_outstanding = bill.calculate_outstanding_amount()

            alloc = VendorPaymentAllocation(
                bill_id=bill_id,
                payment_transaction_id=payment_transaction_id,
                allocated_amount=amount
            )
            self.session.add(alloc)
            created_allocations.append(alloc)

            # Update bill status
            new_outstanding = current_outstanding - amount
            bill.status = "PAID" if new_outstanding == Decimal("0.00") else "PARTIALLY_PAID"

        await self.session.flush()
        return created_allocations

    async def register_vendor_advance(
        self,
        organization_id: uuid.UUID,
        vendor_id: uuid.UUID,
        advance_date: date,
        amount: Decimal,
        transaction_id: uuid.UUID,
        project_id: Optional[uuid.UUID] = None
    ) -> VendorAdvance:
        code = await self.generate_advance_code(organization_id, advance_date)
        adv = VendorAdvance(
            organization_id=organization_id,
            advance_code=code,
            vendor_id=vendor_id,
            project_id=project_id,
            advance_date=advance_date,
            original_amount=amount,
            settled_amount=Decimal("0.00"),
            remaining_balance=amount,
            transaction_id=transaction_id
        )
        self.session.add(adv)
        await self.session.flush()
        return adv

    async def settle_vendor_advance(
        self,
        organization_id: uuid.UUID,
        advance_id: uuid.UUID,
        settlement_amount: Decimal
    ) -> VendorAdvance:
        stmt = select(VendorAdvance).where(
            and_(
                VendorAdvance.organization_id == organization_id,
                VendorAdvance.id == advance_id
            )
        )
        adv = await self.session.scalar(stmt)
        if not adv:
            raise EntityNotFoundException("Vendor Advance", advance_id)

        if settlement_amount > adv.remaining_balance:
            raise InvariantViolationException(
                f"Settlement amount ({settlement_amount}) exceeds remaining advance balance ({adv.remaining_balance}) on {adv.advance_code}. Flagged AMOUNT_MISMATCH for review.",
                details={
                    "advance_id": str(advance_id),
                    "remaining_balance": str(adv.remaining_balance),
                    "settlement_amount": str(settlement_amount),
                    "excess": str(settlement_amount - adv.remaining_balance)
                }
            )

        adv.settled_amount += settlement_amount
        adv.remaining_balance -= settlement_amount
        await self.session.flush()
        return adv
