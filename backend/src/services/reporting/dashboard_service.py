import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.transaction import Transaction, TransactionReviewFlag
from src.models.enums import AccountType, ProjectStatus, WorkflowStatus
from src.schemas.reporting import DashboardSummaryResponse
from src.services.reporting.base import get_organization_name


class DashboardService:
    @staticmethod
    async def get_dashboard_summary(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> DashboardSummaryResponse:
        as_of = as_of_date or date.today()
        start_of_year = date(as_of.year, 1, 1)
        org_name = await get_organization_name(session, organization_id)

        # 1. Kas & Bank Balance (1101%)
        cash_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_code.like("1101%")
            )
        )
        cash_balance = Decimal(str((await session.execute(cash_stmt)).scalar() or "0.00"))

        # 2. AR Outstanding
        ar_invoices_stmt = select(CustomerInvoice).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.invoice_date <= as_of,
                CustomerInvoice.status != "CANCELLED",
            )
        )
        invoices = (await session.execute(ar_invoices_stmt)).scalars().all()
        ar_alloc_stmt = select(
            CustomerPaymentAllocation.invoice_id,
            func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))
        ).group_by(CustomerPaymentAllocation.invoice_id)
        ar_alloc_map = dict((await session.execute(ar_alloc_stmt)).all())

        ar_outstanding = Decimal("0.00")
        for inv in invoices:
            paid = Decimal(str(ar_alloc_map.get(inv.id, Decimal("0.00"))))
            out = Decimal(str(inv.total_amount)) - paid
            if out > Decimal("0.00"):
                ar_outstanding += out

        # 3. AP Outstanding
        ap_bills_stmt = select(VendorBill).where(
            and_(
                VendorBill.organization_id == organization_id,
                VendorBill.bill_date <= as_of
            )
        )
        bills = (await session.execute(ap_bills_stmt)).scalars().all()
        ap_alloc_stmt = select(
            VendorPaymentAllocation.bill_id,
            func.coalesce(func.sum(VendorPaymentAllocation.allocated_amount), Decimal("0.00"))
        ).group_by(VendorPaymentAllocation.bill_id)
        ap_alloc_map = dict((await session.execute(ap_alloc_stmt)).all())

        ap_outstanding = Decimal("0.00")
        for bill in bills:
            paid = Decimal(str(ap_alloc_map.get(bill.id, Decimal("0.00"))))
            out = Decimal(str(bill.total_amount)) - paid
            if out > Decimal("0.00"):
                ap_outstanding += out

        # 4. Revenue YTD & Net Profit YTD
        ytd_stmt = select(
            ChartOfAccount.account_type,
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date >= start_of_year,
                JournalEntry.posting_date <= as_of,
                ChartOfAccount.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE])
            )
        ).group_by(ChartOfAccount.account_type)

        ytd_rows = (await session.execute(ytd_stmt)).all()
        tot_rev_ytd = Decimal("0.00")
        tot_exp_ytd = Decimal("0.00")

        for acc_type, dr, cr in ytd_rows:
            if acc_type == AccountType.REVENUE:
                tot_rev_ytd += (Decimal(str(cr)) - Decimal(str(dr)))
            elif acc_type == AccountType.EXPENSE:
                tot_exp_ytd += (Decimal(str(dr)) - Decimal(str(cr)))

        net_profit_ytd = tot_rev_ytd - tot_exp_ytd

        # 5. Burn Rate & Cash Runway
        months_elapsed = max(as_of.month, 1)
        monthly_burn = (tot_exp_ytd / Decimal(str(months_elapsed))).quantize(Decimal("0.01"))
        
        cash_runway: Optional[Decimal] = None
        if monthly_burn > Decimal("0.00") and cash_balance > Decimal("0.00"):
            cash_runway = (cash_balance / monthly_burn).quantize(Decimal("0.1"))

        # 6. Active Projects Count
        proj_stmt = select(func.count(Project.id)).where(
            and_(
                Project.organization_id == organization_id,
                Project.project_status == ProjectStatus.ACTIVE
            )
        )
        active_projects_count = int((await session.execute(proj_stmt)).scalar() or 0)

        # 7. Pending Review Items Count
        review_stmt = select(func.count(TransactionReviewFlag.id)).join(
            Transaction, TransactionReviewFlag.transaction_id == Transaction.id
        ).where(
            and_(
                Transaction.organization_id == organization_id,
                TransactionReviewFlag.resolved_at == None
            )
        )
        pending_reviews = int((await session.execute(review_stmt)).scalar() or 0)

        # 8. Integrity check (Total Debit == Total Credit)
        bal_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00")),
            func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date <= as_of
            )
        )
        dr_tot, cr_tot = (await session.execute(bal_stmt)).one()
        is_balanced = (Decimal(str(dr_tot)) == Decimal(str(cr_tot)))

        return DashboardSummaryResponse(
            organization_name=org_name,
            as_of_date=as_of,
            cash_and_bank_balance=cash_balance,
            accounts_receivable_outstanding=ar_outstanding,
            accounts_payable_outstanding=ap_outstanding,
            revenue_ytd=tot_rev_ytd,
            net_profit_ytd=net_profit_ytd,
            estimated_monthly_burn_rate=monthly_burn,
            cash_runway_months=cash_runway,
            active_projects_count=active_projects_count,
            review_queue_pending_count=pending_reviews,
            integrity_status="VALID" if is_balanced else "INTEGRITY_ERROR"
        )
