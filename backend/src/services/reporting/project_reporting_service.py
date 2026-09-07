import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict, Optional
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project
from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, CostCategory
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.counterparty import Counterparty
from src.schemas.reporting import (
    ProjectCostCategoryLine,
    ProjectProfitabilityReportResponse,
    ProjectCashPositionReportResponse
)
from src.services.reporting.base import get_organization_name

PROJECT_HELP_TEXTS: Dict[str, str] = {
    "laba_kotor_proyek": "Invoice proyek dikurangi biaya langsung proyek.",
    "margin_proyek": "Persentase laba kotor dibanding nilai yang sudah diinvoice.",
    "posisi_kas_proyek": "Cash yang sudah diterima dikurangi cash yang sudah keluar untuk proyek.",
    "pph_dipotong": "Pajak yang dipotong saat pelanggan membayar. Tidak selalu merupakan biaya.",
    "pokok_pinjaman": "Pengembalian pokok utang. Mengurangi kas dan utang, bukan laba."
}


class ProjectReportingService:
    @staticmethod
    async def get_project_profitability(
        session: AsyncSession,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> ProjectProfitabilityReportResponse:
        org_name = await get_organization_name(session, organization_id)

        # 1. Fetch project details
        proj_stmt = select(Project).options(
            selectinload(Project.customer)
        ).where(
            and_(
                Project.organization_id == organization_id,
                Project.id == project_id
            )
        )
        proj = (await session.execute(proj_stmt)).scalar_one_or_none()
        if not proj:
            raise ValueError("Proyek tidak ditemukan.")

        orig_val = Decimal(str(proj.original_contract_value))
        vo_val = Decimal(str(proj.variation_order_value))
        revised_val = Decimal(str(proj.revised_contract_value))

        # 2. Invoices, Collections, AR, and Retention
        inv_stmt = select(CustomerInvoice).options(
            selectinload(CustomerInvoice.allocations)
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.project_id == project_id,
                CustomerInvoice.status != "CANCELLED"
            )
        )
        invoices = (await session.execute(inv_stmt)).scalars().all()
        invoiced_amt = sum((Decimal(str(inv.total_amount)) for inv in invoices), Decimal("0.00"))
        cash_rec = sum((sum((Decimal(str(a.allocated_amount)) for a in inv.allocations), Decimal("0.00")) for inv in invoices), Decimal("0.00"))
        ar_outstanding = sum((inv.calculate_outstanding_amount() for inv in invoices), Decimal("0.00"))
        retention_withheld = sum((inv.calculate_retention_outstanding() for inv in invoices), Decimal("0.00"))

        # 3. Direct Cost breakdown per 9 categories from posted journal lines
        cost_stmt = select(
            JournalLine.cost_category,
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                ChartOfAccount.account_type == AccountType.EXPENSE,
                ChartOfAccount.account_code.like("5%")
            )
        ).group_by(JournalLine.cost_category)

        cost_rows = (await session.execute(cost_stmt)).all()
        cost_map: Dict[str, Decimal] = {
            row[0].value if row[0] else "OTH": Decimal(str(row[1])) for row in cost_rows
        }

        category_labels = {
            "MAT": "Material & Bahan Bangunan",
            "SUB": "Subkontraktor & Pekerjaan Spesialis",
            "LAB": "Upah Tenaga Kerja Langsung",
            "EQP": "Sewa Alat Berat & Perkakas",
            "TRN": "Transportasi & Bahan Bakar",
            "TRV": "Perjalanan Dinas Proyek",
            "LOG": "Logistik & Ekspedisi",
            "SIT": "Operasional Lapangan & K3",
            "OTH": "Biaya Langsung Lainnya"
        }

        breakdown: List[ProjectCostCategoryLine] = []
        total_direct_cost = Decimal("0.00")

        for cat_key, label in category_labels.items():
            amt = cost_map.get(cat_key, Decimal("0.00"))
            total_direct_cost += amt
            breakdown.append(
                ProjectCostCategoryLine(
                    cost_category=cat_key,
                    category_name=label,
                    amount=amt
                )
            )

        # 4. Cash Spent (All credits on Cash/Bank COA 1101/1102 with this project_id)
        cash_spent_stmt = select(
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                ChartOfAccount.account_code.like("110%")
            )
        )
        cash_spent = Decimal(str((await session.execute(cash_spent_stmt)).scalar() or "0.00"))

        # 5. Secondary Management Items: Fee, Bank Charges, Final Tax, Withheld Tax, Loan Principal
        # Direct Project Fee / Commission (6106 or fee/konsultan name)
        fee_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                or_(
                    ChartOfAccount.account_code.like("6106%"),
                    ChartOfAccount.account_name.ilike("%fee%"),
                    ChartOfAccount.account_name.ilike("%konsultan%"),
                    ChartOfAccount.account_name.ilike("%komisi%")
                )
            )
        )
        project_fee = Decimal(str((await session.execute(fee_stmt)).scalar() or "0.00"))

        # Project Bank Charges / Interest (7101 / 7102)
        bank_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                ChartOfAccount.account_code.like("710%")
            )
        )
        bank_charges = Decimal(str((await session.execute(bank_stmt)).scalar() or "0.00"))

        # Project Final Tax (8101)
        tax_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                ChartOfAccount.account_code.like("810%")
            )
        )
        pph_final = Decimal(str((await session.execute(tax_stmt)).scalar() or "0.00"))

        # Loan Principal Repayment on Project (2501 - affects cash position, NEVER profit)
        loan_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                ChartOfAccount.account_code.like("2501%")
            )
        )
        loan_principal = Decimal(str((await session.execute(loan_stmt)).scalar() or "0.00"))

        # PPh Withheld (Prepaid tax 1108 / 1109)
        withheld_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id == project_id,
                or_(
                    ChartOfAccount.account_code.like("1108%"),
                    ChartOfAccount.account_code.like("1109%")
                )
            )
        )
        pph_withheld = Decimal(str((await session.execute(withheld_stmt)).scalar() or "0.00"))

        # Primary Result: Gross Project Profit
        gross_profit = invoiced_amt - total_direct_cost
        margin_pct = (gross_profit / invoiced_amt * 100) if invoiced_amt > 0 else Decimal("0.00")

        # Secondary Result: Project Net Contribution (if sufficient data exists)
        has_secondary_data = (project_fee > 0) or (bank_charges > 0) or (pph_final > 0)
        net_contribution = (
            gross_profit - project_fee - bank_charges - pph_final
        ) if has_secondary_data else None

        net_cash_pos = cash_rec - cash_spent
        is_surplus = net_cash_pos >= Decimal("0.00")

        return ProjectProfitabilityReportResponse(
            organization_name=org_name,
            project_id=str(proj.id),
            project_code=proj.project_code,
            project_name=proj.project_name,
            client_name=proj.customer.name if proj.customer else None,
            status=proj.project_status.value,
            contract_value=revised_val,
            original_contract_value=orig_val,
            variation_orders_value=vo_val,
            revised_contract_value=revised_val,
            invoiced_amount=invoiced_amt,
            revenue_recognized=invoiced_amt,
            cash_received=cash_rec,
            receivable_outstanding=ar_outstanding,
            retention_withheld=retention_withheld,
            cost_breakdown=breakdown,
            direct_project_cost=total_direct_cost,
            total_project_cost=total_direct_cost,
            gross_profit=gross_profit,
            gross_project_profit=gross_profit,
            gross_margin_percentage=margin_pct.quantize(Decimal("0.01")),
            gross_margin=margin_pct.quantize(Decimal("0.01")),
            cash_spent=cash_spent,
            project_cash_position=net_cash_pos,
            is_cash_surplus=is_surplus,
            pph_withheld=pph_withheld,
            pph_final=pph_final,
            project_fee=project_fee,
            bank_charges=bank_charges,
            loan_principal_paid=loan_principal,
            has_net_contribution_data=has_secondary_data,
            project_net_contribution=net_contribution,
            help_texts=PROJECT_HELP_TEXTS
        )

    @staticmethod
    async def get_project_cash_position(
        session: AsyncSession,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> ProjectCashPositionReportResponse:
        # Reuse get_project_profitability to guarantee 100% calculation consistency
        prof = await ProjectReportingService.get_project_profitability(
            session=session,
            organization_id=organization_id,
            project_id=project_id
        )

        return ProjectCashPositionReportResponse(
            organization_name=prof.organization_name,
            project_id=prof.project_id,
            project_code=prof.project_code,
            project_name=prof.project_name,
            contract_value=prof.contract_value,
            invoiced_amount=prof.invoiced_amount,
            cash_received=prof.cash_received,
            receivable_outstanding=prof.receivable_outstanding,
            retention_withheld=prof.retention_withheld,
            direct_project_cost=prof.direct_project_cost,
            gross_profit=prof.gross_profit,
            gross_margin_percentage=prof.gross_margin_percentage,
            cash_spent=prof.cash_spent,
            net_cash_position=prof.project_cash_position,
            is_surplus=prof.is_cash_surplus,
            pph_withheld=prof.pph_withheld,
            loan_principal_paid=prof.loan_principal_paid,
            notice_message="Laba Proyek (Akrual) Berbeda dengan Posisi Kas Proyek (Likuiditas).",
            help_texts=PROJECT_HELP_TEXTS
        )
