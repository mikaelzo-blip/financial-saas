import uuid
from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction, TransactionAllocation, TransactionReviewFlag
from src.models.document import TransactionDocumentLink
from src.models.counterparty import Counterparty
from src.models.coa import PaymentAccount
from src.models.project import Project
from src.models.enums import (
    TransactionType,
    WorkflowStatus,
    ReviewFlag,
    CostCategory,
    ExpenseCategory
)
from src.schemas.transaction import (
    TransactionCreate,
    TransactionAllocationInput,
)
from src.services.duplicate_service import DuplicateDetectionService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


def validate_transaction_allocations(
    total_amount: Decimal,
    allocations: List[TransactionAllocationInput]
) -> bool:
    """
    Validates that the sum of allocation line amounts exactly equals the transaction total amount.
    """
    if not allocations:
        return True

    allocation_sum = sum(a.amount for a in allocations)
    if allocation_sum != total_amount:
        raise InvariantViolationException(
            f"Sum of allocations ({allocation_sum}) does not match transaction total ({total_amount}).",
            details={
                "transaction_total": str(total_amount),
                "allocation_sum": str(allocation_sum),
                "difference": str(total_amount - allocation_sum)
            }
        )
    return True


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.duplicate_service = DuplicateDetectionService(session)

    async def generate_transaction_code(
        self,
        organization_id: uuid.UUID,
        trx_date: Optional[date] = None
    ) -> str:
        """Generates sequential transaction code in format TRX-YYYY-###### (e.g. TRX-2026-000001)."""
        year = (trx_date or date.today()).year
        prefix = f"TRX-{year}-"

        stmt = select(func.count()).select_from(Transaction).where(
            and_(
                Transaction.organization_id == organization_id,
                Transaction.transaction_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def get_transaction(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID
    ) -> Transaction:
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.allocations),
                selectinload(Transaction.review_flags)
            )
            .where(
                and_(
                    Transaction.organization_id == organization_id,
                    Transaction.id == transaction_id
                )
            )
        )
        trx = await self.session.scalar(stmt)
        if not trx:
            raise EntityNotFoundException("Transaction", transaction_id)
        return trx

    async def list_transactions(
        self,
        organization_id: uuid.UUID,
        workflow_status: Optional[WorkflowStatus] = None,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        filters = [Transaction.organization_id == organization_id]
        if workflow_status:
            filters.append(Transaction.workflow_status == workflow_status)
        if transaction_type:
            filters.append(Transaction.transaction_type == transaction_type)

        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.allocations),
                selectinload(Transaction.review_flags)
            )
            .where(and_(*filters))
            .order_by(Transaction.transaction_date.desc(), Transaction.transaction_code.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_transaction(
        self,
        organization_id: uuid.UUID,
        data: TransactionCreate,
        created_by: Optional[uuid.UUID] = None
    ) -> Transaction:
        """
        Creates candidate financial transaction, validates allocations, checks heuristic duplicates,
        and links evidentiary documents.
        """
        # Resolve allocations
        resolved_allocations: List[TransactionAllocationInput] = []
        if data.allocations:
            validate_transaction_allocations(data.amount, data.allocations)
            resolved_allocations = data.allocations
        elif data.project_id or data.cost_category or data.expense_category:
            # Single-project convenience
            resolved_allocations = [
                TransactionAllocationInput(
                    project_id=data.project_id,
                    cost_category=data.cost_category,
                    expense_category=data.expense_category,
                    amount=data.amount,
                    notes=data.description
                )
            ]

        if data.transaction_type == TransactionType.CUSTOMER_INVOICE:
            if data.reference_no and len(data.reference_no) > 50:
                raise InvariantViolationException("Customer invoice number must not exceed 50 characters.")
            if data.allocations and any(allocation.project_id is None for allocation in resolved_allocations):
                raise InvariantViolationException(
                    "Customer invoice requires every allocation to reference one project."
                )
            project_ids = {allocation.project_id for allocation in resolved_allocations if allocation.project_id}
            if data.project_id:
                project_ids.add(data.project_id)
            if not data.counterparty_id or len(project_ids) != 1:
                raise InvariantViolationException(
                    "Customer invoice requires customer and one project."
                )
            customer = await self.session.scalar(select(Counterparty).where(
                Counterparty.id == data.counterparty_id,
                Counterparty.organization_id == organization_id,
            ))
            if not customer:
                raise EntityNotFoundException("Customer Counterparty", data.counterparty_id)
            if not customer.is_customer:
                raise InvariantViolationException("Customer invoice counterparty must be a customer.")
            project_id = project_ids.pop()
            project = await self.session.scalar(select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            ))
            if not project:
                raise EntityNotFoundException("Project", project_id)
            if project.customer_id != customer.id:
                raise InvariantViolationException("Customer invoice customer must match the customer assigned to the project.")

        if data.transaction_type == TransactionType.CUSTOMER_PAYMENT:
            if not data.counterparty_id:
                raise InvariantViolationException("Customer payment requires a customer.")
            customer = await self.session.scalar(select(Counterparty).where(
                Counterparty.id == data.counterparty_id,
                Counterparty.organization_id == organization_id,
            ))
            if not customer:
                raise EntityNotFoundException("Customer Counterparty", data.counterparty_id)
            if not customer.is_customer:
                raise InvariantViolationException("Customer payment counterparty must be a customer.")
            if data.payment_account_id:
                payment_account = await self.session.scalar(select(PaymentAccount).where(
                    PaymentAccount.id == data.payment_account_id,
                    PaymentAccount.organization_id == organization_id,
                    PaymentAccount.is_active == True,
                ))
                if not payment_account:
                    raise EntityNotFoundException("Active Payment Account", data.payment_account_id)

        # Invoice numbers are tenant-unique regardless of date or amount.
        duplicate_candidate = None
        if data.transaction_type == TransactionType.CUSTOMER_INVOICE and data.reference_no:
            duplicate_candidate = await self.session.scalar(select(Transaction).where(
                Transaction.organization_id == organization_id,
                Transaction.transaction_type == TransactionType.CUSTOMER_INVOICE,
                Transaction.reference_no == data.reference_no,
            ).limit(1))
        if not duplicate_candidate:
            duplicate_candidate = await self.duplicate_service.check_duplicate_candidate(
                organization_id=organization_id,
                transaction_date=data.transaction_date,
                amount=data.amount,
                counterparty_id=data.counterparty_id,
                payment_account_id=data.payment_account_id,
                reference_no=data.reference_no,
            )

        initial_status = WorkflowStatus.STAGED
        review_flags_to_add: List[TransactionReviewFlag] = []

        if duplicate_candidate:
            initial_status = WorkflowStatus.REVIEW_REQUIRED
            review_flags_to_add.append(
                TransactionReviewFlag(
                    flag=ReviewFlag.DUPLICATE_SUSPECTED,
                    severity="WARNING",
                    message=f"Possible duplicate of existing transaction {duplicate_candidate.transaction_code} on {duplicate_candidate.transaction_date} for amount {duplicate_candidate.amount}."
                )
            )

        # Generate code
        trx_code = await self.generate_transaction_code(organization_id, data.transaction_date)

        transaction = Transaction(
            organization_id=organization_id,
            transaction_code=trx_code,
            transaction_type=data.transaction_type,
            transaction_date=data.transaction_date,
            amount=data.amount,
            currency=data.currency,
            workflow_status=initial_status,
            counterparty_id=data.counterparty_id,
            payment_account_id=data.payment_account_id,
            reference_no=data.reference_no,
            description=data.description,
            source_channel=data.source_channel,
            created_by=created_by
        )
        self.session.add(transaction)
        await self.session.flush()

        # Add allocations
        for alloc in resolved_allocations:
            allocation_record = TransactionAllocation(
                transaction_id=transaction.id,
                project_id=alloc.project_id,
                cost_category=alloc.cost_category,
                expense_category=alloc.expense_category,
                amount=alloc.amount,
                notes=alloc.notes
            )
            self.session.add(allocation_record)

        # Add review flags if any
        for flag in review_flags_to_add:
            flag.transaction_id = transaction.id
            self.session.add(flag)

        # Link documents
        for doc_id in data.document_ids:
            doc_link = TransactionDocumentLink(
                transaction_id=transaction.id,
                document_id=doc_id
            )
            self.session.add(doc_link)

        await self.session.flush()
        return await self.get_transaction(organization_id, transaction.id)
