import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import NormalBalance
from src.schemas.reporting import TrialBalanceLine, TrialBalanceResponse
from src.services.reporting.base import get_organization_name
from src.services.reporting.period_helper import resolve_report_dates, ReportPeriodType


class TrialBalanceService:
    @staticmethod
    async def get_trial_balance(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        as_of_date: date | None = None,
    ) -> TrialBalanceResponse:
        s_date, e_date = resolve_report_dates(
            ReportPeriodType.CUSTOM,
            start_date=start_date,
            end_date=end_date,
            as_of_date=as_of_date
        )
        as_of = end_date or as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)

        # 1. Fetch all active Chart of Accounts for organization
        coa_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.is_active == True
            )
        ).order_by(ChartOfAccount.account_code)
        coa_list = (await session.execute(coa_stmt)).scalars().all()

        # 2. Fetch Opening movements (before s_date)
        opening_stmt = select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date < s_date
            )
        ).group_by(JournalLine.account_id)
        opening_res = (await session.execute(opening_stmt)).all()
        opening_map: Dict[uuid.UUID, tuple[Decimal, Decimal]] = {
            row[0]: (Decimal(str(row[1])), Decimal(str(row[2]))) for row in opening_res
        }

        # 3. Fetch Period movements (s_date <= posting_date <= e_date)
        period_stmt = select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date >= s_date,
                JournalEntry.posting_date <= e_date
            )
        ).group_by(JournalLine.account_id)
        period_res = (await session.execute(period_stmt)).all()
        period_map: Dict[uuid.UUID, tuple[Decimal, Decimal]] = {
            row[0]: (Decimal(str(row[1])), Decimal(str(row[2]))) for row in period_res
        }

        lines: List[TrialBalanceLine] = []
        tot_op_dr = Decimal("0.00")
        tot_op_cr = Decimal("0.00")
        tot_per_dr = Decimal("0.00")
        tot_per_cr = Decimal("0.00")
        tot_end_dr = Decimal("0.00")
        tot_end_cr = Decimal("0.00")

        for acc in coa_list:
            op_dr_raw, op_cr_raw = opening_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
            per_dr, per_cr = period_map.get(acc.id, (Decimal("0.00"), Decimal("0.00")))

            # Net Opening balance based on normal balance
            if acc.normal_balance == NormalBalance.DEBIT:
                net_opening = op_dr_raw - op_cr_raw
                op_dr = net_opening if net_opening > 0 else Decimal("0.00")
                op_cr = abs(net_opening) if net_opening < 0 else Decimal("0.00")
            else:
                net_opening = op_cr_raw - op_dr_raw
                op_cr = net_opening if net_opening > 0 else Decimal("0.00")
                op_dr = abs(net_opening) if net_opening < 0 else Decimal("0.00")

            # Cumulative Ending Balance
            cum_dr = op_dr_raw + per_dr
            cum_cr = op_cr_raw + per_cr

            if acc.normal_balance == NormalBalance.DEBIT:
                net_end = cum_dr - cum_cr
                end_dr = net_end if net_end > 0 else Decimal("0.00")
                end_cr = abs(net_end) if net_end < 0 else Decimal("0.00")
            else:
                net_end = cum_cr - cum_dr
                end_cr = net_end if net_end > 0 else Decimal("0.00")
                end_dr = abs(net_end) if net_end < 0 else Decimal("0.00")

            # Include account if there is any balance or activity
            if op_dr_raw > 0 or op_cr_raw > 0 or per_dr > 0 or per_cr > 0:
                line = TrialBalanceLine(
                    account_code=acc.account_code,
                    account_name=acc.account_name,
                    account_type=acc.account_type.value,
                    normal_balance=acc.normal_balance.value,
                    opening_debit=op_dr,
                    opening_credit=op_cr,
                    period_debit=per_dr,
                    period_credit=per_cr,
                    ending_debit=end_dr,
                    ending_credit=end_cr
                )
                lines.append(line)

                tot_op_dr += op_dr
                tot_op_cr += op_cr
                tot_per_dr += per_dr
                tot_per_cr += per_cr
                tot_end_dr += end_dr
                tot_end_cr += end_cr

        diff = abs(tot_end_dr - tot_end_cr)

        return TrialBalanceResponse(
            organization_name=org_name,
            as_of_date=as_of,
            start_date=s_date,
            end_date=e_date,
            lines=lines,
            total_opening_debit=tot_op_dr,
            total_opening_credit=tot_op_cr,
            total_period_debit=tot_per_dr,
            total_period_credit=tot_per_cr,
            total_ending_debit=tot_end_dr,
            total_ending_credit=tot_end_cr,
            is_balanced=diff == Decimal("0.00"),
            difference=diff
        )
