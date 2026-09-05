import uuid
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import TransactionType, WorkflowStatus
from src.models.transaction import Transaction, TransactionAllocation
from src.models.coa import ChartOfAccount
from src.services.processing_policy_service import ProcessingPolicyService
from src.core.exceptions import InvariantViolationException


class OpeningBalanceService:
    """
    Imports and establishes opening balances from consultant financial reports.
    Creates audit-grounded double-entry journal entries rather than synthetic dashboard numbers.
    Preserves invariant: Assets = Liabilities + Equity (Total Debit == Total Credit).
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.policy_service = ProcessingPolicyService(session)

    async def post_opening_balances(
        self,
        organization_id: uuid.UUID,
        as_of_date: date,
        balance_entries: List[Dict[str, Any]],
        notes: str = "Opening Balances Migration"
    ) -> Transaction:
        """
        Takes a list of {account_code: str, debit: Decimal, credit: Decimal}
        Validates Total Debit == Total Credit.
        Posts through standard Transaction -> AccountingEngine.
        """
        total_dr = Decimal("0.00")
        total_cr = Decimal("0.00")

        for entry in balance_entries:
            dr = Decimal(str(entry.get("debit", "0.00")))
            cr = Decimal(str(entry.get("credit", "0.00")))
            total_dr += dr
            total_cr += cr

        if total_dr != total_cr:
            raise InvariantViolationException(
                f"Opening balance must balance: Total Debit ({total_dr}) != Total Credit ({total_cr}).",
                details={"total_debit": str(total_dr), "total_credit": str(total_cr)}
            )

        if total_dr <= Decimal("0.00"):
            raise InvariantViolationException("Opening balance total must be positive.")

        # Create master opening balance transaction
        trx = Transaction(
            organization_id=organization_id,
            transaction_code=f"OPB-{as_of_date.year}-{uuid.uuid4().hex[:6].upper()}",
            transaction_type=TransactionType.JOURNAL_ADJUSTMENT,
            transaction_date=as_of_date,
            amount=total_dr,
            description=notes,
            source_channel="MANUAL",
            workflow_status=WorkflowStatus.STAGED
        )
        self.session.add(trx)
        await self.session.flush()

        # Add transaction allocations for each account leg
        for entry in balance_entries:
            code = entry["account_code"]
            dr = Decimal(str(entry.get("debit", "0.00")))
            cr = Decimal(str(entry.get("credit", "0.00")))
            if dr > Decimal("0.00"):
                alloc = TransactionAllocation(
                    transaction_id=trx.id,
                    amount=dr,
                    notes=f"DR:{code}"
                )
                self.session.add(alloc)
            elif cr > Decimal("0.00"):
                alloc = TransactionAllocation(
                    transaction_id=trx.id,
                    amount=cr,
                    notes=f"CR:{code}"
                )
                self.session.add(alloc)
        await self.session.flush()

        # Approve and Post via ProcessingPolicyService
        posted_trx, _ = await self.policy_service.authorize_and_post(
            organization_id=organization_id,
            transaction_id=trx.id,
            bypass_role_check=True
        )
        return posted_trx
