import uuid
from decimal import Decimal
from typing import List, Dict
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project, ProjectBudget
from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, CostCategory
from src.schemas.reporting import (
    BudgetVsActualLine,
    BudgetVsActualReportResponse
)
from src.services.reporting.base import get_organization_name


class BudgetVsActualService:
    @staticmethod
    async def get_budget_vs_actual(
        session: AsyncSession,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> BudgetVsActualReportResponse:
        org_name = await get_organization_name(session, organization_id)

        # 1. Fetch project
        proj_stmt = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.id == project_id
            )
        )
        proj = (await session.execute(proj_stmt)).scalar_one_or_none()
        if not proj:
            raise ValueError("Proyek tidak ditemukan.")

        # 2. Fetch project budgets
        b_stmt = select(ProjectBudget).where(ProjectBudget.project_id == project_id)
        budgets = (await session.execute(b_stmt)).scalars().all()
        budget_map: Dict[str, Decimal] = {
            b.cost_category.value: Decimal(str(b.budget_amount)) for b in budgets
        }
        has_budget = len(budgets) > 0

        # 3. Fetch actual posted costs per category
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

        actual_rows = (await session.execute(cost_stmt)).all()
        actual_map: Dict[str, Decimal] = {
            row[0].value if row[0] else "OTH": Decimal(str(row[1])) for row in actual_rows
        }

        category_labels = {
            "MAT": "Material & Bahan Bangunan",
            "SUB": "Subkontraktor & Spesialis",
            "LAB": "Upah Tenaga Kerja Langsung",
            "EQP": "Sewa Alat Berat",
            "TRN": "Transportasi & Bahan Bakar",
            "TRV": "Perjalanan Dinas",
            "LOG": "Logistik & Ekspedisi",
            "SIT": "Operasional Lapangan",
            "OTH": "Biaya Langsung Lainnya"
        }

        lines: List[BudgetVsActualLine] = []
        tot_budget = Decimal("0.00")
        tot_actual = Decimal("0.00")

        for cat_key, label in category_labels.items():
            b_amt = budget_map.get(cat_key, Decimal("0.00"))
            a_amt = actual_map.get(cat_key, Decimal("0.00"))
            var_amt = b_amt - a_amt
            pct = (a_amt / b_amt * 100) if b_amt > 0 else Decimal("0.00")

            if not has_budget:
                st = "NORMAL"
            elif pct > 100:
                st = "OVERBUDGET"
            elif pct >= 90:
                st = "WARNING"
            else:
                st = "NORMAL"

            tot_budget += b_amt
            tot_actual += a_amt

            lines.append(
                BudgetVsActualLine(
                    cost_category=cat_key,
                    category_name=label,
                    budget_amount=b_amt,
                    actual_amount=a_amt,
                    variance_amount=var_amt,
                    variance_percentage=pct.quantize(Decimal("0.01")),
                    status=st
                )
            )

        tot_variance = tot_budget - tot_actual
        tot_pct = (tot_actual / tot_budget * 100) if tot_budget > 0 else Decimal("0.00")

        return BudgetVsActualReportResponse(
            organization_name=org_name,
            project_id=str(proj.id),
            project_code=proj.project_code,
            project_name=proj.project_name,
            has_budget=has_budget,
            budget_status_label="Anggaran Ditetapkan" if has_budget else "Anggaran Belum Ditetapkan",
            total_budget=tot_budget,
            total_actual=tot_actual,
            total_variance=tot_variance,
            consumption_percentage=tot_pct.quantize(Decimal("0.01")),
            lines=lines
        )
