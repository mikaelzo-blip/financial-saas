import uuid
from datetime import date
from decimal import Decimal
from typing import List
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, NormalBalance
from src.models.receivable import CustomerInvoice
from src.models.payable import VendorBill
from src.schemas.reporting import IntegrityCheckItem, IntegrityReportResponse
from src.services.reporting.base import get_organization_name


class IntegrityService:
    @staticmethod
    async def run_diagnostics(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: date | None = None
    ) -> IntegrityReportResponse:
        as_of = as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)
        checks: List[IntegrityCheckItem] = []

        # Check 1: All Journal Entries must individually be balanced
        unbalanced_je_stmt = select(
            func.count(JournalEntry.id),
            func.coalesce(func.sum(func.abs(JournalEntry.total_debit - JournalEntry.total_credit)), Decimal("0.00"))
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                JournalEntry.total_debit != JournalEntry.total_credit
            )
        )
        unbalanced_res = await session.execute(unbalanced_je_stmt)
        unbalanced_count, unbalanced_diff = unbalanced_res.one()

        checks.append(
            IntegrityCheckItem(
                check_name="Keseimbangan Jurnal Berpasangan (Total Debit = Total Kredit)",
                status="PASS" if unbalanced_count == 0 else "FAIL",
                left_value=Decimal("0.00"),
                right_value=Decimal(str(unbalanced_diff)),
                discrepancy=Decimal(str(unbalanced_diff)),
                message="Semua jurnal berpasangan seimbang." if unbalanced_count == 0 else f"Ditemukan {unbalanced_count} jurnal tidak seimbang!"
            )
        )

        # Check 2: Total GL Debit == Total GL Credit
        gl_totals_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of
            )
        )
        gl_res = await session.execute(gl_totals_stmt)
        total_dr, total_cr = gl_res.one()
        tb_diff = abs(Decimal(str(total_dr)) - Decimal(str(total_cr)))

        checks.append(
            IntegrityCheckItem(
                check_name="Neraca Saldo Keseluruhan (Total Debet = Total Kredit Buku Besar)",
                status="PASS" if tb_diff == Decimal("0.00") else "FAIL",
                left_value=Decimal(str(total_dr)),
                right_value=Decimal(str(total_cr)),
                discrepancy=tb_diff,
                message="Total mutasi debet dan kredit buku besar tepat seimbang." if tb_diff == Decimal("0.00") else f"Terdapat selisih neraca saldo sebesar Rp {tb_diff}"
            )
        )

        # Check 3: Assets = Liabilities + Equity (Cumulative Accounting Equation)
        # Compute Assets
        assets_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_type == AccountType.ASSET
            )
        )
        total_assets = Decimal(str((await session.execute(assets_stmt)).scalar() or "0.00"))

        # Compute Liabilities
        liab_stmt = select(
            func.coalesce(func.sum(JournalLine.credit_amount - JournalLine.debit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_type == AccountType.LIABILITY
            )
        )
        total_liab = Decimal(str((await session.execute(liab_stmt)).scalar() or "0.00"))

        # Compute Equity + Cumulative Retained Earnings (Revenue - Expenses)
        equity_stmt = select(
            func.coalesce(func.sum(JournalLine.credit_amount - JournalLine.debit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_type.in_([AccountType.EQUITY, AccountType.REVENUE])
            )
        )
        total_equity_and_rev = Decimal(str((await session.execute(equity_stmt)).scalar() or "0.00"))

        exp_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_type == AccountType.EXPENSE
            )
        )
        total_expenses = Decimal(str((await session.execute(exp_stmt)).scalar() or "0.00"))

        total_net_equity = total_equity_and_rev - total_expenses
        total_liab_and_equity = total_liab + total_net_equity
        bs_diff = abs(total_assets - total_liab_and_equity)

        checks.append(
            IntegrityCheckItem(
                check_name="Persamaan Dasar Akuntansi (Aset = Kewajiban + Ekuitas)",
                status="PASS" if bs_diff == Decimal("0.00") else "FAIL",
                left_value=total_assets,
                right_value=total_liab_and_equity,
                discrepancy=bs_diff,
                message="Persamaan dasar akuntansi terpenuhi sempurna." if bs_diff == Decimal("0.00") else f"Selisih persamaan akuntansi: Rp {bs_diff}"
            )
        )

        overall = "VALID" if all(c.status == "PASS" for c in checks) else "INTEGRITY_ERROR"

        return IntegrityReportResponse(
            organization_name=org_name,
            as_of_date=as_of,
            overall_status=overall,
            checks=checks
        )
