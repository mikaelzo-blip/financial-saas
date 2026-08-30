import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.transaction import Transaction
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, TransactionType
from src.schemas.reporting import (
    ReportLineItem,
    ReportSection,
    CashFlowReportResponse,
    ReportPeriodType
)
from src.services.reporting.base import get_organization_name
from src.services.reporting.period_helper import resolve_report_dates, format_period_label


class CashFlowService:
    @staticmethod
    async def get_cash_flow(
        session: AsyncSession,
        organization_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> CashFlowReportResponse:
        s_date, e_date = resolve_report_dates(
            ReportPeriodType.CUSTOM,
            start_date=start_date,
            end_date=end_date
        )
        org_name = await get_organization_name(session, organization_id)
        period_label = format_period_label(s_date, e_date)

        # 1. Fetch cash/bank COA IDs (1101 prefix)
        cash_acc_stmt = select(ChartOfAccount.id).where(
            and_(
                ChartOfAccount.organization_id == organization_id,
                ChartOfAccount.account_code.like("1101%"),
                ChartOfAccount.is_active == True
            )
        )
        cash_acc_ids = (await session.execute(cash_acc_stmt)).scalars().all()

        if not cash_acc_ids:
            return CashFlowReportResponse(
                organization_name=org_name,
                period_label=period_label,
                start_date=s_date,
                end_date=e_date,
                opening_cash_balance=Decimal("0.00"),
                operating_activities=ReportSection(section_code="CF_OP", section_name="Arus Kas dari Aktivitas Operasi", lines=[], subtotal=Decimal("0.00")),
                net_operating_cash=Decimal("0.00"),
                investing_activities=ReportSection(section_code="CF_INV", section_name="Arus Kas dari Aktivitas Investasi", lines=[], subtotal=Decimal("0.00")),
                net_investing_cash=Decimal("0.00"),
                financing_activities=ReportSection(section_code="CF_FIN", section_name="Arus Kas dari Aktivitas Pendanaan", lines=[], subtotal=Decimal("0.00")),
                net_financing_cash=Decimal("0.00"),
                net_cash_change=Decimal("0.00"),
                closing_cash_balance=Decimal("0.00")
            )

        # 2. Opening Cash Balance (before start_date)
        op_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.account_id.in_(cash_acc_ids),
                JournalEntry.posting_date < s_date
            )
        )
        opening_cash = Decimal(str((await session.execute(op_stmt)).scalar() or "0.00"))

        # 3. Period Cash Movements linked to Transactions
        period_stmt = select(
            Transaction.transaction_type,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            Transaction, JournalEntry.transaction_id == Transaction.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.account_id.in_(cash_acc_ids),
                JournalEntry.posting_date >= s_date,
                JournalEntry.posting_date <= e_date
            )
        ).group_by(Transaction.transaction_type)

        period_rows = (await session.execute(period_stmt)).all()

        op_lines: List[ReportLineItem] = []
        inv_lines: List[ReportLineItem] = []
        fin_lines: List[ReportLineItem] = []
        unclass_lines: List[ReportLineItem] = []

        tot_op = Decimal("0.00")
        tot_inv = Decimal("0.00")
        tot_fin = Decimal("0.00")
        tot_unclass = Decimal("0.00")

        for trx_type, dr_sum, cr_sum in period_rows:
            dr = Decimal(str(dr_sum))
            cr = Decimal(str(cr_sum))
            net_inflow = dr - cr

            if trx_type == TransactionType.CUSTOMER_PAYMENT:
                op_lines.append(ReportLineItem(line_name="Penerimaan Pembayaran Pelanggan", amount=net_inflow))
                tot_op += net_inflow
            elif trx_type in [TransactionType.DIRECT_PURCHASE, TransactionType.PAY_VENDOR_BILL, TransactionType.PAY_SUBCONTRACTOR]:
                op_lines.append(ReportLineItem(line_name=f"Pembayaran Pemasok & Subkon ({trx_type.value})", amount=net_inflow))
                tot_op += net_inflow
            elif trx_type in [TransactionType.VENDOR_ADVANCE, TransactionType.EMPLOYEE_ADVANCE]:
                op_lines.append(ReportLineItem(line_name="Pengeluaran Uang Muka / Kasbon Lapangan", amount=net_inflow))
                tot_op += net_inflow
            elif trx_type in [TransactionType.BANK_CHARGE, TransactionType.PETTY_CASH_EXPENSE, TransactionType.PAY_REIMBURSEMENT]:
                op_lines.append(ReportLineItem(line_name=f"Beban Operasional & Administrasi Bank ({trx_type.value})", amount=net_inflow))
                tot_op += net_inflow
            elif trx_type == TransactionType.ASSET_PURCHASE:
                inv_lines.append(ReportLineItem(line_name="Pembelian Aset Tetap & Alat Berat", amount=net_inflow))
                tot_inv += net_inflow
            elif trx_type in [TransactionType.OWNER_CONTRIBUTION, TransactionType.LOAN_RECEIVED]:
                fin_lines.append(ReportLineItem(line_name=f"Penerimaan Modal / Pinjaman ({trx_type.value})", amount=net_inflow))
                tot_fin += net_inflow
            elif trx_type in [TransactionType.OWNER_WITHDRAWAL, TransactionType.LOAN_PAYMENT]:
                fin_lines.append(ReportLineItem(line_name=f"Penarikan Prive / Angsuran Pinjaman ({trx_type.value})", amount=net_inflow))
                tot_fin += net_inflow
            else:
                unclass_lines.append(ReportLineItem(line_name=f"Mutasi Lainnya ({trx_type.value})", amount=net_inflow))
                tot_unclass += net_inflow

        net_change = tot_op + tot_inv + tot_fin + tot_unclass
        closing_cash = opening_cash + net_change

        return CashFlowReportResponse(
            organization_name=org_name,
            period_label=period_label,
            start_date=s_date,
            end_date=e_date,
            opening_cash_balance=opening_cash,
            operating_activities=ReportSection(
                section_code="CF_OP",
                section_name="Arus Kas dari Aktivitas Operasi",
                lines=op_lines,
                subtotal=tot_op
            ),
            net_operating_cash=tot_op,
            investing_activities=ReportSection(
                section_code="CF_INV",
                section_name="Arus Kas dari Aktivitas Investasi",
                lines=inv_lines,
                subtotal=tot_inv
            ),
            net_investing_cash=tot_inv,
            financing_activities=ReportSection(
                section_code="CF_FIN",
                section_name="Arus Kas dari Aktivitas Pendanaan",
                lines=fin_lines,
                subtotal=tot_fin
            ),
            net_financing_cash=tot_fin,
            net_cash_change=net_change,
            closing_cash_balance=closing_cash,
            unclassified_cash_activities=ReportSection(
                section_code="CF_UNCLASS",
                section_name="Transaksi Kas Perlu Klasifikasi",
                lines=unclass_lines,
                subtotal=tot_unclass
            ) if unclass_lines else None
        )
