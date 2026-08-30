import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction, TransactionReviewFlag
from src.models.enums import ReviewFlag, WorkflowStatus, UserRole, TransactionType
from src.services.accounting_engine import AccountingEngine
from src.services.audit_service import AuditService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException, AuthorizationException


class ReviewQueueService:
    """
    Manages the financial Review Queue, multi-flag tracking, resolution workflows,
    and role-based approval escalation.
    """
    SENSITIVE_TYPES = {
        TransactionType.OWNER_WITHDRAWAL,
        TransactionType.OWNER_CONTRIBUTION,
        TransactionType.REVERSAL,
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.accounting_engine = AccountingEngine(session)
        self.audit_service = AuditService(session)

    async def list_review_items(
        self,
        organization_id: uuid.UUID,
        flag_type: Optional[ReviewFlag] = None,
        unresolved_only: bool = True
    ) -> List[Transaction]:
        """Lists transactions currently in the review queue with their flags."""
        filters = [Transaction.organization_id == organization_id]
        if unresolved_only:
            filters.append(Transaction.workflow_status == WorkflowStatus.REVIEW_REQUIRED)

        stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.review_flags),
                selectinload(Transaction.allocations)
            )
            .where(and_(*filters))
            .order_by(Transaction.created_at.desc())
        )
        transactions = (await self.session.execute(stmt)).scalars().all()

        if flag_type:
            transactions = [
                t for t in transactions
                if any(f.flag == flag_type and (not unresolved_only or f.resolved_at is None) for f in t.review_flags)
            ]

        return transactions

    async def add_review_flag(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        flag: ReviewFlag,
        message: str,
        severity: str = "WARNING"
    ) -> TransactionReviewFlag:
        """Adds a review flag to a transaction and routes it to REVIEW_REQUIRED status."""
        trx_stmt = select(Transaction).where(
            and_(
                Transaction.organization_id == organization_id,
                Transaction.id == transaction_id
            )
        )
        trx = await self.session.scalar(trx_stmt)
        if not trx:
            raise EntityNotFoundException("Transaction", transaction_id)

        review_flag = TransactionReviewFlag(
            transaction_id=transaction_id,
            flag=flag,
            severity=severity,
            message=message
        )
        self.session.add(review_flag)
        trx.workflow_status = WorkflowStatus.REVIEW_REQUIRED
        await self.session.flush()

        await self.audit_service.log_event(
            organization_id=organization_id,
            entity_name="transactions",
            entity_id=trx.id,
            action="ADD_REVIEW_FLAG",
            new_values={"flag": flag.value, "message": message, "severity": severity}
        )

        return review_flag

    async def resolve_review_flag(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        flag_id: uuid.UUID,
        resolved_by: uuid.UUID,
        resolution_notes: str
    ) -> TransactionReviewFlag:
        """
        Resolves a specific review flag.
        If all review flags on the transaction are resolved, unblocks the transaction back to STAGED.
        """
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.review_flags))
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

        target_flag = next((f for f in trx.review_flags if f.id == flag_id), None)
        if not target_flag:
            raise EntityNotFoundException("TransactionReviewFlag", flag_id)

        if target_flag.resolved_at is not None:
            raise InvariantViolationException(
                f"Review flag {target_flag.flag.value} has already been resolved.",
                details={"flag_id": str(flag_id), "resolved_at": target_flag.resolved_at.isoformat()}
            )

        target_flag.resolved_at = datetime.now()
        target_flag.resolved_by = resolved_by
        target_flag.resolution_notes = resolution_notes

        # Check if any other unresolved flags remain
        unresolved_count = sum(1 for f in trx.review_flags if f.resolved_at is None and f.id != flag_id)
        if unresolved_count == 0:
            trx.workflow_status = WorkflowStatus.STAGED

        await self.session.flush()

        await self.audit_service.log_event(
            organization_id=organization_id,
            entity_name="transaction_review_flags",
            entity_id=target_flag.id,
            action="RESOLVE_REVIEW_FLAG",
            actor_id=resolved_by,
            new_values={
                "flag": target_flag.flag.value,
                "resolution_notes": resolution_notes,
                "remaining_unresolved_flags": unresolved_count,
                "new_workflow_status": trx.workflow_status.value
            }
        )

        return target_flag

    async def approve_and_post(
        self,
        organization_id: uuid.UUID,
        transaction_id: uuid.UUID,
        approver_id: uuid.UUID,
        approver_role: UserRole
    ):
        """
        Approves and posts transaction to double-entry journal with role-based checks.
        Sensitive transaction types require MANAGER or ADMIN role.
        """
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.review_flags))
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

        # 1. Check for unresolved review flags
        unresolved_flags = [f for f in trx.review_flags if f.resolved_at is None]
        if unresolved_flags:
            flags_str = ", ".join(f.flag.value for f in unresolved_flags)
            raise InvariantViolationException(
                f"Cannot approve transaction {trx.transaction_code}. Unresolved review flags exist: {flags_str}.",
                details={"transaction_id": str(transaction_id), "unresolved_flags": flags_str}
            )

        # 2. Check role authorization for sensitive transactions
        if trx.transaction_type in self.SENSITIVE_TYPES:
            if approver_role not in (UserRole.ADMIN, UserRole.MANAGER):
                raise AuthorizationException(
                    f"Transaction type '{trx.transaction_type.value}' requires Manager approval.",
                    details={"transaction_type": trx.transaction_type.value, "role": approver_role.value}
                )

        # 3. Mark approved
        trx.approved_by = approver_id
        trx.approved_at = datetime.now()
        trx.workflow_status = WorkflowStatus.APPROVED

        # 4. Post via Accounting Engine
        je = await self.accounting_engine.post_transaction(
            organization_id=organization_id,
            transaction_id=transaction_id,
            actor_id=approver_id
        )

        await self.audit_service.log_event(
            organization_id=organization_id,
            entity_name="transactions",
            entity_id=trx.id,
            action="APPROVE_AND_POST",
            actor_id=approver_id,
            new_values={"entry_number": je.entry_number, "total_debit": str(je.total_debit)}
        )

        return trx, je
