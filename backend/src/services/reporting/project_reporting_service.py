import uuid
from datetime import date
from decimal import Decimal
from typing import List, Dict
from sqlalchemy import select, and_, func
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

        # 2. Revenue Recognized (from posted customer invoices for this project)
        rev_stmt = select(
            func.coalesce(func.sum(CustomerInvoice.total_amount), Decimal("0.00"))
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.project_id == project_id
            )
        )
        rev_recognized = Decimal(str((await session.execute(rev_stmt)).scalar() or "0.00"))

        # 3. Cost breakdown per 9 categories from posted journal lines
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
                ChartOfAccount.account_type == AccountType.EXPENSE
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
        total_cost = Decimal("0.00")

        for cat_key, label in category_labels.items():
            amt = cost_map.get(cat_key, Decimal("0.00"))
            total_cost += amt
            breakdown.append(
                ProjectCostCategoryLine(
                    cost_category=cat_key,
                    category_name=label,
                    amount=amt
                )
            )

        gross_profit = rev_recognized - total_cost
        margin_pct = (gross_profit / rev_recognized * 100) if rev_recognized > 0 else Decimal("0.00")

        return ProjectProfitabilityReportResponse(
            organization_name=org_name,
            project_id=str(proj.id),
            project_code=proj.project_code,
            project_name=proj.project_name,
            client_name=proj.customer.name if proj.customer else None,
            status=proj.project_status.value,
            original_contract_value=orig_val,
            variation_orders_value=vo_val,
            revised_contract_value=revised_val,
            revenue_recognized=rev_recognized,
            cost_breakdown=breakdown,
            total_project_cost=total_cost,
            gross_profit=gross_profit,
            gross_margin_percentage=margin_pct.quantize(Decimal("0.01"))
        )

    @staticmethod
    async def get_project_cash_position(
        session: AsyncSession,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> ProjectCashPositionReportResponse:
        org_name = await get_organization_name(session, organization_id)

        proj_stmt = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.id == project_id
            )
        )
        proj = (await session.execute(proj_stmt)).scalar_one_or_none()
        if not proj:
            raise ValueError("Proyek tidak ditemukan.")

        # Invoiced & Cash Received
        inv_stmt = select(CustomerInvoice).options(
            selectinload(CustomerInvoice.allocations)
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.project_id == project_id
            )
        )
        invoices = (await session.execute(inv_stmt)).scalars().all()
        invoiced_amt = sum((Decimal(str(inv.total_amount)) for inv in invoices), Decimal("0.00"))
        cash_rec = sum((sum((Decimal(str(a.allocated_amount)) for a in inv.allocations), Decimal("0.00")) for inv in invoices), Decimal("0.00"))
        ar_outstanding = sum((inv.calculate_outstanding_amount() for inv in invoices), Decimal("0.00"))

        # Cash Spent (Journal lines on cash/bank accounts with this project_id)
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
                ChartOfAccount.account_code.like("1101%")
            )
        )
        cash_spent = Decimal(str((await session.execute(cash_spent_stmt)).scalar() or "0.00"))

        net_cash = cash_rec - cash_spent
        is_surplus = net_cash >= Decimal("0.00")

        return ProjectCashPositionReportResponse(
            organization_name=org_name,
            project_id=str(proj.id),
            project_code=proj.project_code,
            project_name=proj.project_name,
            invoiced_amount=invoiced_amt,
            cash_received=cash_rec,
            receivable_outstanding=ar_outstanding,
            cash_spent=cash_spent,
            net_cash_position=net_cash,
            is_surplus=is_surplus
        )
