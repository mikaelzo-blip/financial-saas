import uuid
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import TransactionType, WorkflowStatus
from src.models.payable import VendorBill
from src.services.audit_service import AuditService
from src.services.payable_service import VendorAPService
from src.services.receivable_service import CustomerARService
from src.services.posting_rules import PostingRuleRegistry, GeneratedJournalLeg
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


class AccountingEngine:
    """
    Deterministic Double-Entry Posting Engine.
    Guarantees Total Debit == Total Credit and immutable posted history.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_entry_number(self, organization_id: uuid.UUID, posting_date: Optional[date] = None) -> str:
        """Generates sequential journal entry number: JE-YYYY-###### (e.g. JE-2026-000001)."""
        year = (posting_date or date.today()).year
        prefix = f"JE-{year}-"

        stmt = select(func.count()).select_from(JournalEntry).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.entry_number.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def post_transaction(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        posting_date: Optional[date] = None,
        actor_id: Optional[uuid.UUID] = None
    ) -> JournalEntry:
        """
        Posts a candidate financial transaction into immutable double-entry journal.
        Atomic operation: updates transaction status to POSTED, creates balanced JournalEntry and JournalLines.
        """
        # Fetch transaction with allocations
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.allocations))
            .where(
                and_(
                    Transaction.organization_id == organization_id,
                    Transaction.id == transaction_id
                )
            )
        )
        transaction = await self.session.scalar(stmt)
        if not transaction:
            raise EntityNotFoundException("Transaction", transaction_id)

        if transaction.workflow_status == WorkflowStatus.POSTED:
            raise InvariantViolationException(
                f"Transaction {transaction.transaction_code} is already posted.",
                details={"transaction_id": str(transaction_id), "status": transaction.workflow_status.value}
            )

        if transaction.workflow_status in (WorkflowStatus.REVIEW_REQUIRED, WorkflowStatus.REVERSED):
            raise InvariantViolationException(
                f"Cannot post transaction in '{transaction.workflow_status.value}' state. Resolve review flags first.",
                details={"transaction_id": str(transaction_id), "status": transaction.workflow_status.value}
            )

        # Generate double-entry legs from rules
        legs = PostingRuleRegistry.generate_journal_legs(transaction)

        # Cache COA lookup for this org
        coa_stmt = select(ChartOfAccount).where(ChartOfAccount.organization_id == organization_id)
        coa_res = await self.session.execute(coa_stmt)
        accounts_by_code = {a.account_code: a for a in coa_res.scalars().all()}

        # Verify all accounts exist
        for leg in legs:
            if leg.account_code not in accounts_by_code:
                raise InvariantViolationException(
                    f"COA account code '{leg.account_code}' not found in organization.",
                    details={"account_code": leg.account_code, "organization_id": str(organization_id)}
                )

        p_date = posting_date or transaction.transaction_date
        entry_number = await self.generate_entry_number(organization_id, p_date)

        total_dr = sum(l.debit_amount for l in legs)
        total_cr = sum(l.credit_amount for l in legs)

        journal_entry = JournalEntry(
            organization_id=organization_id,
            entry_number=entry_number,
            transaction_id=transaction.id,
            posting_date=p_date,
            description=transaction.description,
            total_debit=total_dr,
            total_credit=total_cr,
            is_balanced=True,
            is_reversed=False
        )
        self.session.add(journal_entry)
        await self.session.flush()

        for idx, leg in enumerate(legs, start=1):
            acc = accounts_by_code[leg.account_code]
            line = JournalLine(
                journal_entry_id=journal_entry.id,
                line_number=idx,
                account_id=acc.id,
                debit_amount=leg.debit_amount,
                credit_amount=leg.credit_amount,
                project_id=leg.project_id,
                counterparty_id=leg.counterparty_id,
                cost_category=leg.cost_category,
                expense_category=leg.expense_category,
                notes=leg.notes
            )
            self.session.add(line)

        if transaction.transaction_type == TransactionType.CUSTOMER_INVOICE:
            project_ids = {allocation.project_id for allocation in transaction.allocations if allocation.project_id}
            if len(project_ids) != 1 or not transaction.counterparty_id:
                raise InvariantViolationException(
                    "Customer invoice posting requires one project and customer."
                )
            await CustomerARService(self.session).issue_customer_invoice(
                organization_id=organization_id,
                customer_id=transaction.counterparty_id,
                project_id=project_ids.pop(),
                invoice_date=transaction.transaction_date,
                total_amount=transaction.amount,
                transaction_id=transaction.id,
                invoice_code=transaction.reference_no,
                retention_rate=getattr(transaction, "retention_rate", Decimal("0.0000")) or Decimal("0.0000"),
                retention_amount=getattr(transaction, "retention_amount", Decimal("0.00")) or Decimal("0.00"),
            )

        if transaction.transaction_type == TransactionType.VENDOR_BILL:
            project_ids = {allocation.project_id for allocation in transaction.allocations if allocation.project_id}
            if not transaction.counterparty_id:
                raise InvariantViolationException(
                    "Vendor bill posting requires a counterparty."
                )
            project_id = project_ids.pop() if len(project_ids) == 1 else None
            effective_due_date, _ = await VendorAPService(self.session).calculate_effective_due_date(
                organization_id=organization_id,
                vendor_id=transaction.counterparty_id,
                bill_date=transaction.transaction_date,
            )
            bill_code = transaction.reference_no or await VendorAPService(self.session).generate_bill_code(
                organization_id, transaction.transaction_date
            )
            bill = VendorBill(
                organization_id=organization_id,
                bill_code=bill_code,
                vendor_id=transaction.counterparty_id,
                project_id=project_id,
                bill_date=transaction.transaction_date,
                due_date=effective_due_date,
                total_amount=transaction.amount,
                transaction_id=transaction.id,
                status="UNPAID",
            )
            self.session.add(bill)

        # Mark transaction as POSTED
        old_status = transaction.workflow_status.value
        transaction.workflow_status = WorkflowStatus.POSTED
        transaction.posted_at = datetime.now()

        await AuditService(self.session).log_event(
            organization_id,
            "Transaction",
            transaction.id,
            "POST",
            actor_id,
            old_values={"workflow_status": old_status},
            new_values={
                "workflow_status": WorkflowStatus.POSTED.value,
                "journal_entry_id": str(journal_entry.id),
            },
        )

        await self.session.flush()

        # Re-fetch entry with lines loaded
        entry_stmt = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.lines).selectinload(JournalLine.account),
                selectinload(JournalEntry.lines).selectinload(JournalLine.project),
                selectinload(JournalEntry.lines).selectinload(JournalLine.counterparty),
            )
            .where(JournalEntry.id == journal_entry.id)
        )
        return await self.session.scalar(entry_stmt)
