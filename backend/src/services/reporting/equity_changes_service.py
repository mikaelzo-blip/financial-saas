import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType
from src.schemas.reporting import (
    EquityChangeItem,
    EquityChangesReportResponse,
    CALKPolicyItem,
    CALKReportResponse
)
from src.services.reporting.base import get_organization_name
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.cash_flow_service import CashFlowService


class EquityChangesService:
    """
    Authoritative Statement of Changes in Equity (Laporan Perubahan Ekuitas).
    Tracks:
    - Opening Paid-in Capital (3101) & Retained Earnings (3201)
    - Capital Contributions during period (3101 credits)
    - Net Profit / (Loss) from ProfitLossService
    - Owner Draws / Prive (3301 debits)
    - Closing balances preserving: Total Equity = Paid-in + Retained Earnings + CY Profit - Prive
    """

    @staticmethod
    async def get_equity_changes(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: date,
        end_date: date
    ) -> EquityChangesReportResponse:
        org_name = await get_organization_name(session, organization_id)
        period_label = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"

        # 1. Opening balances up to start_date
        stmt_opening = select(
            ChartOfAccount.account_code,
            func.coalesce(func.sum(JournalLine.credit_amount - JournalLine.debit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date < start_date,
                ChartOfAccount.account_type == AccountType.EQUITY
            )
        ).group_by(ChartOfAccount.account_code)

        opening_res = (await session.execute(stmt_opening)).all()
        opening_map = {row[0]: Decimal(str(row[1])) for row in opening_res}

        opening_paid_in = opening_map.get("3101", Decimal("0.00"))
        opening_retained = opening_map.get("3201", Decimal("0.00"))
        # Any prior prive/earnings rolled into opening
        opening_other = sum((amt for code, amt in opening_map.items() if code not in ("3101", "3201")), Decimal("0.00"))
        opening_total = opening_paid_in + opening_retained + opening_other

        # 2. Period movements for Equity accounts
        stmt_period = select(
            ChartOfAccount.account_code,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date >= start_date,
                JournalEntry.posting_date <= end_date,
                ChartOfAccount.account_type == AccountType.EQUITY
            )
        ).group_by(ChartOfAccount.account_code)

        period_res = (await session.execute(stmt_period)).all()
        period_map = {row[0]: (Decimal(str(row[1])), Decimal(str(row[2]))) for row in period_res}

        # 3101 Capital Contribution = Credit - Debit during period
        dr_3101, cr_3101 = period_map.get("3101", (Decimal("0.00"), Decimal("0.00")))
        capital_contributions = cr_3101 - dr_3101

        # 3301 Owner draws (Prive) = Debit - Credit during period
        dr_3301, cr_3301 = period_map.get("3301", (Decimal("0.00"), Decimal("0.00")))
        owner_draws_prive = dr_3301 - cr_3301

        # 3. Current period net profit from authoritative ProfitLossService
        pl_report = await ProfitLossService.get_profit_and_loss(session, organization_id, start_date, end_date)
        net_profit = pl_report.net_profit

        # 4. Other equity movements (e.g. adjustments to 3201 directly)
        dr_3201, cr_3201 = period_map.get("3201", (Decimal("0.00"), Decimal("0.00")))
        other_equity = (cr_3201 - dr_3201)

        closing_paid_in = opening_paid_in + capital_contributions
        closing_retained = opening_retained + net_profit + other_equity - owner_draws_prive
        closing_total = closing_paid_in + closing_retained

        items: List[EquityChangeItem] = [
            EquityChangeItem(account_code="3101", line_name="Saldo Awal Modal Disetor", amount=opening_paid_in),
            EquityChangeItem(account_code="3201", line_name="Saldo Awal Laba Ditahan", amount=opening_retained),
            EquityChangeItem(account_code="3101", line_name="Tambahan Setoran Modal Periode Berjalan", amount=capital_contributions),
            EquityChangeItem(account_code="EQ-CY", line_name="Laba / (Rugi) Bersih Periode Berjalan", amount=net_profit),
            EquityChangeItem(account_code="3301", line_name="Penarikan Pemilik (Prive)", amount=-owner_draws_prive),
            EquityChangeItem(account_code=None, line_name="Saldo Akhir Ekuitas", amount=closing_total),
        ]

        return EquityChangesReportResponse(
            organization_name=org_name,
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            generated_at=date.today().isoformat(),
            opening_paid_in_capital=opening_paid_in,
            opening_retained_earnings=opening_retained,
            opening_total_equity=opening_total,
            capital_contributions=capital_contributions,
            current_period_net_profit=net_profit,
            owner_draws_prive=owner_draws_prive,
            other_equity_changes=other_equity,
            closing_paid_in_capital=closing_paid_in,
            closing_retained_earnings=closing_retained,
            closing_total_equity=closing_total,
            items=items
        )


class CALKService:
    """
    Authoritative Catatan Atas Laporan Keuangan (CALK) Framework.
    Presents deterministic organization information, standard accounting bases,
    locked policy declarations, and cross-statement reconcile summaries.
    """

    @staticmethod
    async def get_calk_report(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: date | None = None
    ) -> CALKReportResponse:
        as_of = as_of_date or date.today()
        org_name = await get_organization_name(session, organization_id)
        start_date = date(as_of.year, 1, 1)

        # Pull statements for deterministic summary tie-outs
        bs = await BalanceSheetService.get_balance_sheet(session, organization_id, as_of)
        pl = await ProfitLossService.get_profit_and_loss(session, organization_id, start_date, as_of)
        cf = await CashFlowService.get_cash_flow(session, organization_id, start_date, as_of)

        policies = [
            CALKPolicyItem(
                section="DASAR_PENYUSUNAN",
                title="Dasar Penyusunan Laporan Keuangan",
                description="Laporan keuangan disusun dengan orientasi Standar Akuntansi Keuangan Entitas Privat (SAK EP) menggunakan prinsip biaya historis dan akrual (kecuali arus kas)."
            ),
            CALKPolicyItem(
                section="KAS_DAN_SETARA_KAS",
                title="Kas dan Setara Kas",
                description="Kas dan setara kas mencakup kas kecil, kas di bank, dan mutasi kas operasional yang diverifikasi secara deterministik melalui pencatatan MoneyMovement."
            ),
            CALKPolicyItem(
                section="PENGAKUAN_PENDAPATAN",
                title="Pengakuan Pendapatan Kontrak Konstruksi",
                description="Pendapatan diakui berdasarkan invoice penagihan termin proyek (Customer Invoice) yang sah dan didukung oleh Berita Acara Kemajuan Pekerjaan / BAST."
            ),
            CALKPolicyItem(
                section="BIAYA_PROYEK",
                title="Biaya Pokok Proyek (HPP)",
                description="Biaya proyek diklasifikasikan secara langsung per proyek ke dalam Material Langsung, Upah Tenaga Kerja Langsung, Subkontraktor, dan Sewa Alat."
            ),
            CALKPolicyItem(
                section="PIUTANG_RETENSI",
                title="Piutang Retensi",
                description="Retensi jaminan pemeliharaan dipisahkan ke akun Piutang Retensi (1202) dan diakui pelunasannya setelah serah terima akhir (BAST-2)."
            ),
        ]

        return CALKReportResponse(
            organization_name=org_name,
            period_label=f"Per {as_of.strftime('%d/%m/%Y')}",
            as_of_date=as_of,
            generated_at=date.today().isoformat(),
            general_information={
                "entity_name": org_name,
                "reporting_currency": "IDR (Rupiah)",
                "as_of_date": as_of.isoformat(),
                "operational_scope": "Jasa Konstruksi dan Kontraktor",
            },
            accounting_standards_basis="SAK EP-Oriented",
            accounting_policies=policies,
            balance_sheet_summary={
                "total_assets": bs.total_assets,
                "total_liabilities": bs.total_liabilities,
                "total_equity": bs.total_equity,
                "balancing_difference": bs.balancing_difference
            },
            profit_loss_summary={
                "revenue": pl.gross_profit + pl.cogs_section.subtotal,
                "cogs": pl.cogs_section.subtotal,
                "gross_profit": pl.gross_profit,
                "operating_profit": pl.operating_profit,
                "net_profit": pl.net_profit
            },
            cash_flow_summary={
                "opening_cash": cf.opening_cash_balance,
                "operating_cash": cf.net_operating_cash,
                "investing_cash": cf.net_investing_cash,
                "financing_cash": cf.net_financing_cash,
                "closing_cash": cf.closing_cash_balance
            }
        )
