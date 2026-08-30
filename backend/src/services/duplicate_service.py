import uuid
from typing import Optional
from datetime import date
from decimal import Decimal
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction
from src.models.enums import WorkflowStatus


class DuplicateDetectionService:
    """
    Evaluates heuristic duplicates based on:
    (organization_id, transaction_date, amount, counterparty_id, payment_account_id).
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_duplicate_candidate(
        self,
        organization_id: uuid.UUID,
        transaction_date: date,
        amount: Decimal,
        counterparty_id: Optional[uuid.UUID] = None,
        payment_account_id: Optional[uuid.UUID] = None,
        exclude_id: Optional[uuid.UUID] = None
    ) -> Optional[Transaction]:
        filters = [
            Transaction.organization_id == organization_id,
            Transaction.transaction_date == transaction_date,
            Transaction.amount == amount,
            Transaction.workflow_status != WorkflowStatus.REVERSED
        ]
        if counterparty_id:
            filters.append(Transaction.counterparty_id == counterparty_id)
        if payment_account_id:
            filters.append(Transaction.payment_account_id == payment_account_id)
        if exclude_id:
            filters.append(Transaction.id != exclude_id)

        stmt = select(Transaction).where(and_(*filters)).limit(1)
        return await self.session.scalar(stmt)
