import uuid
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalLine, JournalEntry
from src.models.coa import ChartOfAccount
from src.models.enums import NormalBalance, AccountType
from src.core.exceptions import EntityNotFoundException


class BalanceService:
    """
    Calculates derived account balances dynamically from posted journal lines.
    Preserves invariant: Chart of Accounts does NOT store static running balances.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_balance(
        self,
        organization_id: uuid.UUID,
        account_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Decimal:
        """Calculates derived net balance for a specific account."""
        coa_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.id == account_id
            )
        )
        account = await self.session.scalar(coa_stmt)
        if not account:
            raise EntityNotFoundException("Chart of Account", account_id)

        # Sum debits and credits from posted non-reversed journals
        filters = [
            JournalEntry.organization_id == organization_id,
            JournalLine.account_id == account_id
        ]
        if as_of_date:
            filters.append(JournalEntry.posting_date <= as_of_date)

        stmt = (
            select(
                func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .where(and_(*filters))
        )
        total_dr, total_cr = (await self.session.execute(stmt)).one()

        if account.normal_balance == NormalBalance.DEBIT:
            return total_dr - total_cr
        else:
            return total_cr - total_dr

    async def get_trial_balance(
        self,
        organization_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Computes trial balance across all active accounts in the organization.
        Verifies global debit == credit equality.
        """
        accounts_stmt = select(ChartOfAccount).where(
            ChartOfAccount.organization_id == organization_id
        ).order_by(ChartOfAccount.account_code.asc())
        accounts = (await self.session.execute(accounts_stmt)).scalars().all()

        rows = []
        sum_debit = Decimal("0.00")
        sum_credit = Decimal("0.00")

        for acc in accounts:
            filters = [
                JournalEntry.organization_id == organization_id,
                JournalLine.account_id == acc.id
            ]
            if as_of_date:
                filters.append(JournalEntry.posting_date <= as_of_date)

            stmt = (
                select(
                    func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
                    func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
                )
                .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
                .where(and_(*filters))
            )
            total_dr, total_cr = (await self.session.execute(stmt)).one()

            if total_dr > 0 or total_cr > 0:
                net = total_dr - total_cr if acc.normal_balance == NormalBalance.DEBIT else total_cr - total_dr
                rows.append({
                    "account_id": str(acc.id),
                    "account_code": acc.account_code,
                    "account_name": acc.account_name,
                    "account_type": acc.account_type.value,
                    "normal_balance": acc.normal_balance.value,
                    "total_debit": total_dr,
                    "total_credit": total_cr,
                    "net_balance": net
                })
                sum_debit += total_dr
                sum_credit += total_cr

        return {
            "as_of_date": as_of_date or date.today(),
            "total_debit": sum_debit,
            "total_credit": sum_credit,
            "is_balanced": (sum_debit == sum_credit),
            "accounts": rows
        }
