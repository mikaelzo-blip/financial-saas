import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.journal import JournalEntry
from src.models.enums import WorkflowStatus
from src.core.exceptions import InvariantViolationException


class ImmutabilityGuard:
    """
    Guards posted transactions and journal entries against destructive edits or deletions.
    """
    @staticmethod
    def assert_transaction_mutable(transaction: Transaction) -> None:
        """Raises InvariantViolationException if transaction is in a posted or immutable state."""
        if transaction.workflow_status in (WorkflowStatus.POSTED, WorkflowStatus.REVERSED):
            raise InvariantViolationException(
                f"Posted transaction {transaction.transaction_code} is immutable and cannot be modified or deleted. Use the Reversal workflow instead.",
                details={
                    "transaction_id": str(transaction.id),
                    "transaction_code": transaction.transaction_code,
                    "workflow_status": transaction.workflow_status.value
                }
            )

    @staticmethod
    def assert_journal_entry_immutable(entry: JournalEntry) -> None:
        """Journal entries are append-only and cannot be mutated."""
        raise InvariantViolationException(
            f"Journal entry {entry.entry_number} is immutable. Corrections must be made via an offsetting reversal journal entry.",
            details={"journal_entry_id": str(entry.id), "entry_number": entry.entry_number}
        )
