import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict, Tuple
from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, NormalBalance
from src.schemas.reporting import (
    ReportLineItem,
    ReportSection,
    BalanceSheetReportResponse
)
from src.services.reporting.base import get_organization_name


def classify_asset_report_group(account_code: str, report_group: str | None) -> str:
    if account_code == "1201":
        return "CURRENT_ASSETS"
    if report_group in {"FIXED_ASSETS", "Aset Tetap"}:
        return "FIXED_ASSETS"
    if report_group in {"CURRENT_ASSETS", "Aset Lancar", "Kas & Bank"}:
        return "CURRENT_ASSETS"
    return "FIXED_ASSETS" if account_code.startswith("15") else "CURRENT_ASSETS"


class BalanceSheetService:
    @staticmethod
    async def get_balance_sheet(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: date | None = None
    ) -> BalanceSheetReportResponse:
        as_of = as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)

        # 1. Fetch all Chart of Accounts
        coa_stmt = select(ChartOfAccount).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.is_active == True
            )
        ).order_by(ChartOfAccount.account_code)
        coa_list = (await session.execute(coa_stmt)).scalars().all()

        start_of_year = date(as_of.year, 1, 1)

        # 2. Aggregate cumulative movements up to as_of
        stmt = select(
            JournalLine.account_id,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00")),
            func.coalesce(
                func.sum(case((JournalEntry.posting_date < start_of_year, JournalLine.debit_amount), else_=Decimal("0.00"))),
                Decimal("0.00")
            ),
            func.coalesce(
                func.sum(case((JournalEntry.posting_date < start_of_year, JournalLine.credit_amount), else_=Decimal("0.00"))),
                Decimal("0.00")
            ),
            func.coalesce(
                func.sum(case((JournalEntry.posting_date >= start_of_year, JournalLine.debit_amount), else_=Decimal("0.00"))),
                Decimal("0.00")
            ),
            func.coalesce(
                func.sum(case((JournalEntry.posting_date >= start_of_year, JournalLine.credit_amount), else_=Decimal("0.00"))),
                Decimal("0.00")
            )
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of
            )
        ).group_by(JournalLine.account_id)

        cum_data = (await session.execute(stmt)).all()
        movements: Dict[uuid.UUID, Tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]] = {
            row[0]: (
                Decimal(str(row[1])), Decimal(str(row[2])),
                Decimal(str(row[3])), Decimal(str(row[4])),
                Decimal(str(row[5])), Decimal(str(row[6]))
            ) for row in cum_data
        }

        # 3. Classify into Balance Sheet categories
        current_assets_lines: List[ReportLineItem] = []
        fixed_assets_lines: List[ReportLineItem] = []
        current_liab_lines: List[ReportLineItem] = []
        long_term_liab_lines: List[ReportLineItem] = []
        equity_lines: List[ReportLineItem] = []

        tot_ca = Decimal("0.00")
        tot_fa = Decimal("0.00")
        tot_cl = Decimal("0.00")
        tot_ll = Decimal("0.00")
        tot_eq = Decimal("0.00")

        prior_rev = Decimal("0.00")
        prior_exp = Decimal("0.00")
        cur_rev = Decimal("0.00")
        cur_exp = Decimal("0.00")

        for acc in coa_list:
            cum_dr, cum_cr, prior_dr, prior_cr, cur_dr, cur_cr = movements.get(
                acc.id,
                (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
            )
            code = acc.account_code

            if acc.account_type == AccountType.ASSET:
                # Normal balance DEBIT
                net = cum_dr - cum_cr
                if net != Decimal("0.00") or code in ["1101", "1102"]:
                    if acc.report_section == "FIXED_ASSET" or classify_asset_report_group(code, acc.report_group) == "FIXED_ASSETS":
                        tot_fa += net
                        fixed_assets_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
                    else:
                        tot_ca += net
                        current_assets_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))

            elif acc.account_type == AccountType.LIABILITY:
                # Normal balance CREDIT
                net = cum_cr - cum_dr
                if net != Decimal("0.00") or code in ["2101"]:
                    if acc.report_section == "LONG_TERM_LIABILITY" or code.startswith("25"):
                        tot_ll += net
                        long_term_liab_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))
                    else:
                        tot_cl += net
                        current_liab_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))

            elif acc.account_type == AccountType.EQUITY:
                # Normal balance CREDIT
                net = cum_cr - cum_dr
                if net != Decimal("0.00") or code in ["3101", "3201"]:
                    tot_eq += net
                    equity_lines.append(ReportLineItem(account_code=code, line_name=acc.account_name, amount=net))

            elif acc.account_type == AccountType.REVENUE:
                prior_rev += (prior_cr - prior_dr)
                cur_rev += (cur_cr - cur_dr)

            elif acc.account_type == AccountType.EXPENSE:
                prior_exp += (prior_dr - prior_cr)
                cur_exp += (cur_dr - cur_cr)

        prior_years_profit = prior_rev - prior_exp
        current_year_earnings = cur_rev - cur_exp

        # Roll prior years profit into Retained Earnings (3201)
        re_line = next((line for line in equity_lines if line.account_code == "3201"), None)
        if re_line:
            re_line.amount += prior_years_profit
            tot_eq += prior_years_profit
        elif prior_years_profit != Decimal("0.00"):
            equity_lines.append(
                ReportLineItem(
                    account_code="3201",
                    line_name="Saldo Laba Ditahan",
                    amount=prior_years_profit
                )
            )
            tot_eq += prior_years_profit

        # Current Year Earnings = Current Year Revenue - Current Year Expense
        if current_year_earnings != Decimal("0.00"):
            equity_lines.append(
                ReportLineItem(
                    account_code="EQ-CY",
                    line_name="Laba / (Rugi) Periode Berjalan",
                    amount=current_year_earnings
                )
            )
            tot_eq += current_year_earnings

        total_assets = tot_ca + tot_fa
        total_liabilities = tot_cl + tot_ll
        total_liab_and_eq = total_liabilities + tot_eq
        diff = abs(total_assets - total_liab_and_eq)
        is_bal = (diff == Decimal("0.00"))

        return BalanceSheetReportResponse(
            organization_name=org_name,
            as_of_date=as_of,
            generated_at=date.today().isoformat(),
            current_assets=ReportSection(
                section_code="CA",
                section_name="Aset Lancar",
                lines=current_assets_lines,
                subtotal=tot_ca
            ),
            fixed_assets=ReportSection(
                section_code="FA",
                section_name="Aset Tetap",
                lines=fixed_assets_lines,
                subtotal=tot_fa
            ),
            total_assets=total_assets,
            current_liabilities=ReportSection(
                section_code="CL",
                section_name="Kewajiban Jangka Pendek",
                lines=current_liab_lines,
                subtotal=tot_cl
            ),
            long_term_liabilities=ReportSection(
                section_code="LL",
                section_name="Kewajiban Jangka Panjang",
                lines=long_term_liab_lines,
                subtotal=tot_ll
            ),
            total_liabilities=total_liabilities,
            equity=ReportSection(
                section_code="EQ",
                section_name="Ekuitas",
                lines=equity_lines,
                subtotal=tot_eq
            ),
            total_equity=tot_eq,
            total_liabilities_and_equity=total_liab_and_eq,
            is_balanced=is_bal,
            balancing_difference=diff,
            integrity_status="VALID" if is_bal else "REPORT_INTEGRITY_ERROR"
        )

