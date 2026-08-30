import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType
from src.schemas.reporting import (
    ReportLineItem,
    ReportSection,
    ProfitLossReportResponse,
    ReportPeriodType
)
from src.services.reporting.base import get_organization_name
from src.services.reporting.period_helper import resolve_report_dates, format_period_label


class ProfitLossService:
    @staticmethod
    async def get_profit_and_loss(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        compare_with: str | None = None,
    ) -> ProfitLossReportResponse:
        s_date, e_date = resolve_report_dates(
            ReportPeriodType.CUSTOM,
            start_date=start_date,
            end_date=end_date
        )
        org_name = await get_organization_name(session, organization_id)
        period_label = format_period_label(s_date, e_date)

        # 1. Fetch relevant Revenue and Expense Chart of Accounts
        coa_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE]),
                ChartOfAccount.is_active == True
            )
        ).order_by(ChartOfAccount.account_code)
        coa_list = (await session.execute(coa_stmt)).scalars().all()

        # 2. Aggregate period movements per account
        stmt = select(
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

        period_data = (await session.execute(stmt)).all()
        movements: Dict[uuid.UUID, Tuple[Decimal, Decimal]] = {
            row[0]: (Decimal(str(row[1])), Decimal(str(row[2]))) for row in period_data
        }

        # 3. Categorize into report sections
        rev_lines: List[ReportLineItem] = []
        cogs_lines: List[ReportLineItem] = []
        opex_lines: List[ReportLineItem] = []
        other_lines: List[ReportLineItem] = []
        tax_expense = Decimal("0.00")

        tot_rev = Decimal("0.00")
        tot_cogs = Decimal("0.00")
        tot_opex = Decimal("0.00")
        tot_other_net = Decimal("0.00")

        for acc in coa_list:
            dr, cr = movements.get(acc.id, (Decimal("0.00"), Decimal("0.00")))
            code = acc.account_code

            if acc.account_type == AccountType.REVENUE:
                if code.startswith("71"):
                    # Other Income
                    net = cr - dr
                    tot_other_net += net
                    other_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
                else:
                    # Operating Revenue
                    net = cr - dr
                    tot_rev += net
                    rev_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
            elif acc.account_type == AccountType.EXPENSE:
                if code.startswith("51"):
                    # COGS
                    net = dr - cr
                    tot_cogs += net
                    cogs_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
                elif code.startswith("61"):
                    # OPEX
                    net = dr - cr
                    tot_opex += net
                    opex_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
                elif code.startswith("72"):
                    # Other Expense
                    net = dr - cr
                    tot_other_net -= net
                    other_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=-net))
                elif code.startswith("81") or "pajak" in acc.account_name.lower():
                    # Income Tax Expense
                    net = dr - cr
                    tax_expense += net

        gross_profit = tot_rev - tot_cogs
        gross_margin = (gross_profit / tot_rev * 100) if tot_rev > 0 else Decimal("0.00")
        operating_profit = gross_profit - tot_opex
        ebt = operating_profit + tot_other_net
        net_profit = ebt - tax_expense

        return ProfitLossReportResponse(
            organization_name=org_name,
            period_label=period_label,
            start_date=s_date,
            end_date=e_date,
            generated_at=date.today().isoformat(),
            revenue_section=ReportSection(
                section_code="REV",
                section_name="Pendapatan Usaha",
                lines=rev_lines,
                subtotal=tot_rev
            ),
            cogs_section=ReportSection(
                section_code="COGS",
                section_name="Harga Pokok Proyek (HPP)",
                lines=cogs_lines,
                subtotal=tot_cogs
            ),
            gross_profit=gross_profit,
            gross_margin_percentage=gross_margin.quantize(Decimal("0.01")),
            operating_expenses_section=ReportSection(
                section_code="OPEX",
                section_name="Beban Operasional",
                lines=opex_lines,
                subtotal=tot_opex
            ),
            operating_profit=operating_profit,
            other_income_expense_section=ReportSection(
                section_code="OTHER",
                section_name="Pendapatan & Beban Lain-lain",
                lines=other_lines,
                subtotal=tot_other_net
            ),
            earnings_before_tax=ebt,
            tax_expense=tax_expense,
            net_profit=net_profit
        )
