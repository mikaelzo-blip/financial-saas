import uuid
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project, ProjectBudget
from src.models.journal import JournalLine, JournalEntry
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.enums import CostCategory, AccountType
from src.models.coa import ChartOfAccount
from src.core.exceptions import EntityNotFoundException


class ProjectCostService:
    """
    Computes real-time project financial metrics dynamically derived from posted journal lines
    and authoritative transaction sub-ledgers.
    Preserves invariant: No manually maintained duplicate Project Cost records.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_project_cost_breakdown(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Calculates total project cost and breakdown by CostCategory derived from posted journal lines on 5101.
        """
        proj_stmt = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.id == project_id
            )
        )
        project = await self.session.scalar(proj_stmt)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        # Query all posted debit legs on 5101 for this project
        stmt = (
            select(
                JournalLine.cost_category,
                func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00")).label("net_cost")
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.project_id == project_id,
                    ChartOfAccount.account_code.like("5101%")
                )
            )
            .group_by(JournalLine.cost_category)
        )
        results = (await self.session.execute(stmt)).all()

        category_breakdown: Dict[str, Decimal] = {cat.value: Decimal("0.00") for cat in CostCategory}
        total_cost = Decimal("0.00")

        for cat, net_cost in results:
            cat_key = cat.value if cat else "OTH"
            category_breakdown[cat_key] = net_cost
            total_cost += net_cost

        # Compare with Project Budgets
        budgets_stmt = select(ProjectBudget).where(
            ProjectBudget.project_id == project_id
        )
        budgets = (await self.session.execute(budgets_stmt)).scalars().all()
        budget_map = {b.cost_category.value: b.budget_amount for b in budgets}
        total_budget = sum(budget_map.values(), Decimal("0.00"))

        budget_variance_rows = []
        for cat in CostCategory:
            b_amount = budget_map.get(cat.value, Decimal("0.00"))
            actual = category_breakdown[cat.value]
            variance = b_amount - actual
            budget_variance_rows.append({
                "cost_category": cat.value,
                "budgeted_amount": b_amount,
                "actual_cost": actual,
                "variance": variance,
                "is_over_budget": actual > b_amount if b_amount > 0 else False
            })

        return {
            "project_id": str(project.id),
            "project_code": project.project_code,
            "project_name": project.project_name,
            "total_actual_cost": total_cost,
            "total_budgeted_cost": total_budget,
            "total_cost_variance": total_budget - total_cost,
            "category_breakdown": category_breakdown,
            "budget_vs_actual": budget_variance_rows
        }

    async def get_project_profitability(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Calculates Recognized Revenue, Actual Project Cost, Project Profit, and Margin %.
        """
        cost_data = await self.get_project_cost_breakdown(organization_id, project_id)
        total_cost = cost_data["total_actual_cost"]

        # Recognized revenue from 4101 journal lines
        rev_stmt = (
            select(
                func.coalesce(func.sum(JournalLine.credit_amount - JournalLine.debit_amount), Decimal("0.00"))
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.project_id == project_id,
                    ChartOfAccount.account_code.like("4101%")
                )
            )
        )
        recognized_revenue = (await self.session.scalar(rev_stmt)) or Decimal("0.00")

        gross_profit = recognized_revenue - total_cost
        margin_percentage = Decimal("0.00")
        if recognized_revenue > Decimal("0.00"):
            margin_percentage = (gross_profit / recognized_revenue) * Decimal("100.00")

        return {
            "project_id": str(project_id),
            "project_code": cost_data["project_code"],
            "project_name": cost_data["project_name"],
            "recognized_revenue": recognized_revenue,
            "actual_project_cost": total_cost,
            "gross_profit": gross_profit,
            "margin_percentage": round(margin_percentage, 2)
        }

    async def get_project_financial_summary(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Full financial statement summary for a project:
        - Contract Dimensions (Original, Variations, Revised)
        - Revenue & Cost (Recognized Revenue, Actual Cost, Profit)
        - Cash Dimensions (Invoiced, Received, Outstanding AR, Cash Net Flow)
        """
        proj_stmt = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.id == project_id
            )
        )
        project = await self.session.scalar(proj_stmt)
        if not project:
            raise EntityNotFoundException("Project", project_id)

        profitability = await self.get_project_profitability(organization_id, project_id)
        cost_data = await self.get_project_cost_breakdown(organization_id, project_id)

        # Invoicing & Collection metrics
        inv_stmt = (
            select(
                func.coalesce(func.sum(CustomerInvoice.total_amount), Decimal("0.00"))
            )
            .where(
                and_(
                    CustomerInvoice.organization_id == organization_id,
                    CustomerInvoice.project_id == project_id,
                    CustomerInvoice.status != "CANCELLED",
                )
            )
        )
        total_invoiced = (await self.session.scalar(inv_stmt)) or Decimal("0.00")

        # Cash Received
        rec_stmt = (
            select(
                func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))
            )
            .join(CustomerInvoice, CustomerPaymentAllocation.invoice_id == CustomerInvoice.id)
            .where(
                and_(
                    CustomerInvoice.organization_id == organization_id,
                    CustomerInvoice.project_id == project_id,
                    CustomerInvoice.status != "CANCELLED",
                )
            )
        )
        total_cash_received = (await self.session.scalar(rec_stmt)) or Decimal("0.00")
        outstanding_ar = total_invoiced - total_cash_received

        # Cash Spent directly on cash/bank accounts for this project
        cash_spent_stmt = (
            select(
                func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.project_id == project_id,
                    ChartOfAccount.account_code.like("1101%")
                )
            )
        )
        cash_spent = (await self.session.scalar(cash_spent_stmt)) or Decimal("0.00")

        # Vendor Spending breakdown
        vendor_spend_stmt = (
            select(
                JournalLine.counterparty_id,
                func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00")).label("spend")
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.project_id == project_id,
                    ChartOfAccount.account_code.like("5101%"),
                    JournalLine.counterparty_id.isnot(None)
                )
            )
            .group_by(JournalLine.counterparty_id)
        )
        vendor_rows = (await self.session.execute(vendor_spend_stmt)).all()
        vendor_spend = []
        for c_id, spend in vendor_rows:
            from src.models.counterparty import Counterparty
            c_name = await self.session.scalar(select(Counterparty.name).where(Counterparty.id == c_id))
            vendor_spend.append({
                "counterparty_id": str(c_id),
                "counterparty_name": c_name or "Unknown",
                "total_spend": spend
            })

        # Documents attached to this project
        from src.models.document import Document, ProjectDocumentLink
        doc_stmt = (
            select(Document.id, Document.document_type, Document.document_code, Document.file_name, Document.created_at)
            .join(ProjectDocumentLink, Document.id == ProjectDocumentLink.document_id)
            .where(
                and_(
                    Document.organization_id == organization_id,
                    ProjectDocumentLink.project_id == project_id
                )
            )
            .order_by(Document.created_at.desc())
        )
        docs = (await self.session.execute(doc_stmt)).all()
        doc_list = [{
            "id": str(d.id),
            "document_type": d.document_type.value if hasattr(d.document_type, "value") else str(d.document_type),
            "document_code": d.document_code,
            "file_name": d.file_name,
            "created_at": d.created_at.isoformat() if d.created_at else None
        } for d in docs]

        # Unallocated items for this project
        from src.models.money_movement import SettlementAllocation
        unalloc_items = []

        return {
            "project_id": str(project.id),
            "project_code": project.project_code,
            "project_name": project.project_name,
            "contract": {
                "original_contract_value": project.original_contract_value,
                "variation_order_value": project.variation_order_value,
                "revised_contract_value": project.revised_contract_value,
            },
            "pnl": {
                "recognized_revenue": profitability["recognized_revenue"],
                "actual_project_cost": profitability["actual_project_cost"],
                "gross_profit": profitability["gross_profit"],
                "margin_percentage": profitability["margin_percentage"]
            },
            "cash_and_billing": {
                "total_invoiced": total_invoiced,
                "total_cash_received": total_cash_received,
                "outstanding_receivable": outstanding_ar,
                "cash_spent": cash_spent,
                "net_cash_flow": total_cash_received - cash_spent,
                "project_cash_surplus": total_cash_received - profitability["actual_project_cost"]
            },
            "cost_categories": cost_data["category_breakdown"],
            "vendor_spend": vendor_spend,
            "documents": doc_list,
            "unallocated_items": unalloc_items
        }
