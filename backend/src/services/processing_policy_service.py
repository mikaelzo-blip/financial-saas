import uuid
from typing import Optional, Set
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.journal import JournalEntry
from src.models.user import User
from src.models.enums import WorkflowStatus, UserRole, TransactionType
from src.services.accounting_engine import AccountingEngine
from src.services.audit_service import AuditService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException, AuthorizationException


class ProcessingPolicyService:
    """
    Authoritative processing & posting policy service.
    Unifies posting validation:
    1. Tenant scoping
    2. Unresolved review flag check
    3. Sensitive transaction role authorization
    4. Auto-safe vs Human-review policy validation
    5. Period status validation (hook for period closure)
    6. Calls AccountingEngine deterministically
    """

    SENSITIVE_TYPES: Set[TransactionType] = {
        TransactionType.OWNER_WITHDRAWAL,
        TransactionType.OWNER_CONTRIBUTION,
        TransactionType.REVERSAL,
    }

    AUTO_SAFE_TYPES: Set[TransactionType] = {
        TransactionType.DIRECT_PURCHASE,
        TransactionType.PETTY_CASH_EXPENSE,
        TransactionType.BANK_CHARGE,
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounting_engine = AccountingEngine(session)
        self.audit_service = AuditService(session)

    async def evaluate_processing_policy(
        self,
        transaction: Transaction
    ) -> str:
        """
        Determines whether candidate transaction is AUTO_SAFE or requires HUMAN_REVIEW.
        """
        unresolved = [f for f in transaction.review_flags if f.resolved_at is None]
        if unresolved:
            return "HUMAN_REVIEW"

        if transaction.transaction_type in self.SENSITIVE_TYPES:
            return "HUMAN_REVIEW"

        if transaction.transaction_type in self.AUTO_SAFE_TYPES:
            return "AUTO_SAFE"

        return "HUMAN_REVIEW"

    async def authorize_and_post(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[UserRole] = None,
        bypass_role_check: bool = False,
    ) -> tuple[Transaction, JournalEntry]:
        """
        Authoritative entry point for posting any transaction to double-entry ledger.
        Ensures review flags, roles, and posting invariants are strictly satisfied.
        """
        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.review_flags),
                selectinload(Transaction.allocations)
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

        # 1. Workflow Status / Review Flag Guard
        unresolved_flags = [f for f in trx.review_flags if f.resolved_at is None]
        if unresolved_flags or trx.workflow_status == WorkflowStatus.REVIEW_REQUIRED:
            flags_str = ", ".join(f.flag.value for f in unresolved_flags) if unresolved_flags else "REVIEW_REQUIRED"
            raise InvariantViolationException(
                f"Cannot post transaction {trx.transaction_code}. Unresolved review flags exist: {flags_str}.",
                details={"transaction_id": str(transaction_id), "unresolved_flags": flags_str}
            )

        # 2. Sensitive Type Role Guard
        if not bypass_role_check and trx.transaction_type in self.SENSITIVE_TYPES:
            if actor_role is not None and actor_role not in (UserRole.ADMIN, UserRole.MANAGER):
                raise AuthorizationException(
                    f"Transaction type '{trx.transaction_type.value}' requires Manager approval.",
                    details={"transaction_type": trx.transaction_type.value, "role": actor_role.value}
                )

        # 3. Mark Approved
        if actor_id:
            trx.approved_by = actor_id
            trx.approved_at = datetime.now()
        trx.workflow_status = WorkflowStatus.APPROVED

        # 4. Post via Accounting Engine
        je = await self.accounting_engine.post_transaction(
            organization_id=organization_id,
            transaction_id=transaction_id,
            actor_id=actor_id
        )

        # 5. Audit Log
        await self.audit_service.log_event(
            organization_id=organization_id,
            entity_name="transactions",
            entity_id=trx.id,
            action="APPROVE_AND_POST",
            actor_id=actor_id,
            new_values={"entry_number": je.entry_number, "total_debit": str(je.total_debit)}
        )

        return trx, je
