import uuid
from typing import Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.enums import TransactionType, WorkflowStatus
from src.services.accounting_engine import AccountingEngine
from src.services.audit_service import AuditService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


class ReversalService:
    """
    Enforces the 3-Step Financial Correction Pattern:
    Original (POSTED) -> Reversal (REVERSED) -> Correcting (POSTED)
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.engine = AccountingEngine(session)
        self.audit = AuditService(session)

    async def generate_reversal_code(self, organization_id: uuid.UUID, rev_date: Optional[date] = None) -> str:
        year = (rev_date or date.today()).year
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

    async def reverse_transaction(
        self,
        organization_id: uuid.UUID,
        original_transaction_id: uuid.UUID,
        reason: str,
        actor_id: Optional[uuid.UUID] = None,
        reversal_date: Optional[date] = None
    ) -> Tuple[Transaction, JournalEntry]:
        """
        Creates an offsetting reversal transaction and journal entry.
        Guarantees zero net financial impact when aggregated with original entry.
        """
        # 1. Fetch original transaction
        trx_stmt = select(Transaction).where(
            and_(
                Transaction.organization_id == organization_id,
                Transaction.id == original_transaction_id
            )
        )
        original_trx = await self.session.scalar(trx_stmt)
        if not original_trx:
            raise EntityNotFoundException("Transaction", original_transaction_id)

        if original_trx.workflow_status != WorkflowStatus.POSTED:
            raise InvariantViolationException(
                f"Cannot reverse transaction in '{original_trx.workflow_status.value}' state. Only POSTED transactions can be reversed.",
                details={"transaction_id": str(original_transaction_id), "status": original_trx.workflow_status.value}
            )

        # 2. Fetch original journal entry
        je_stmt = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.transaction_id == original_transaction_id
                )
            )
        )
        original_je = await self.session.scalar(je_stmt)
        if not original_je:
            raise InvariantViolationException(
                f"No posted journal entry found for transaction {original_trx.transaction_code}."
            )

        if original_je.is_reversed:
            raise InvariantViolationException(
                f"Transaction {original_trx.transaction_code} has already been reversed by entry {original_je.reversal_entry_id}."
            )

        invoice = None
        if original_trx.transaction_type == TransactionType.CUSTOMER_INVOICE:
            invoice = await self.session.scalar(select(CustomerInvoice).where(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.transaction_id == original_trx.id,
            ))
            if invoice and await self.session.scalar(select(CustomerPaymentAllocation.id).where(
                CustomerPaymentAllocation.invoice_id == invoice.id,
            ).limit(1)):
                raise InvariantViolationException(
                    "Cannot reverse a customer invoice with allocated customer payments. Reverse the payments first."
                )

        r_date = reversal_date or date.today()
        rev_trx_code = await self.generate_reversal_code(organization_id, r_date)

        # 3. Create Reversal Transaction
        rev_trx = Transaction(
            organization_id=organization_id,
            transaction_code=rev_trx_code,
            transaction_type=TransactionType.REVERSAL,
            transaction_date=r_date,
            amount=original_trx.amount,
            currency=original_trx.currency,
            workflow_status=WorkflowStatus.POSTED,
            counterparty_id=original_trx.counterparty_id,
            payment_account_id=original_trx.payment_account_id,
            description=f"REVERSAL OF {original_trx.transaction_code}: {reason}",
            reversal_of_id=original_trx.id,
            created_by=actor_id,
            approved_by=actor_id,
            approved_at=datetime.now(),
            posted_at=datetime.now()
        )
        self.session.add(rev_trx)
        await self.session.flush()

        # 4. Create Reversal Journal Entry (Inverted legs)
        rev_je_number = await self.engine.generate_entry_number(organization_id, r_date)
        rev_je = JournalEntry(
            organization_id=organization_id,
            entry_number=rev_je_number,
            transaction_id=rev_trx.id,
            posting_date=r_date,
            description=f"REVERSAL OF {original_je.entry_number}: {reason}",
            total_debit=original_je.total_credit,
            total_credit=original_je.total_debit,
            is_balanced=True,
            is_reversed=False,
            reversal_entry_id=original_je.id
        )
        self.session.add(rev_je)
        await self.session.flush()

        # Invert all lines
        for idx, line in enumerate(original_je.lines, start=1):
            rev_line = JournalLine(
                journal_entry_id=rev_je.id,
                line_number=idx,
                account_id=line.account_id,
                debit_amount=line.credit_amount,   # Invert: old credit becomes new debit
                credit_amount=line.debit_amount,  # Invert: old debit becomes new credit
                project_id=line.project_id,
                counterparty_id=line.counterparty_id,
                cost_category=line.cost_category,
                expense_category=line.expense_category,
                notes=f"Reversal of line #{line.line_number}"
            )
            self.session.add(rev_line)

        # 5. Link original entry to reversal entry and mark original as REVERSED
        original_je.is_reversed = True
        original_je.reversal_entry_id = rev_je.id
        original_trx.workflow_status = WorkflowStatus.REVERSED

        if invoice:
            invoice.status = "CANCELLED"

        # 6. Audit Trail Logging
        await self.audit.log_event(
            organization_id=organization_id,
            entity_name="transactions",
            entity_id=original_trx.id,
            action="REVERSAL",
            actor_id=actor_id,
            old_values={"workflow_status": "POSTED"},
            new_values={"workflow_status": "REVERSED", "reversal_transaction_id": str(rev_trx.id)},
            reason=reason
        )

        await self.session.flush()
        return rev_trx, rev_je
