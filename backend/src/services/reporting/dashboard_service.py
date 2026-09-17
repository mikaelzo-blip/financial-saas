import uuid
import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.payable import VendorBill, VendorPaymentAllocation
from src.models.transaction import Transaction, TransactionReviewFlag
from src.models.document import Document
from src.models.money_movement import MoneyMovement, Settlement
from src.models.enums import AccountType, ProjectStatus, WorkflowStatus, DocumentProcessingStatus
from src.schemas.reporting import (
    DashboardSummaryResponse,
    CashFlowTrendResponse,
    MonthlyCashFlowTrendItem,
    ProjectPerformanceResponse,
    ProjectPerformanceItem,
    DashboardActionItemsResponse,
    CashBankOverviewResponse,
    CashBankAccountItem,
)
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

        # 1b. Cash In, Cash Out, and Net Cash Flow (MTD / Current Month)
        # Net-neutral management cash flow aggregation:
        # Group cash debits and credits per journal entry first.
        # An internal cash transfer (e.g. Bank A -> Bank B) has net = 0 at company level,
        # so it does not inflate gross cash-in or gross cash-out.
        start_of_month = date(as_of.year, as_of.month, 1)
        entry_cash_mtd_subq = (
            select(
                JournalEntry.id.label("journal_entry_id"),
                func.coalesce(
                    func.sum(JournalLine.debit_amount - JournalLine.credit_amount),
                    Decimal("0.00"),
                ).label("entry_net_cash"),
            )
            .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
            .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
            .where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.posting_date >= start_of_month,
                    JournalEntry.posting_date <= as_of,
                    ChartOfAccount.account_code.like("1101%"),
                )
            )
            .group_by(JournalEntry.id)
            .subquery()
        )

        cash_flow_stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (entry_cash_mtd_subq.c.entry_net_cash > 0, entry_cash_mtd_subq.c.entry_net_cash),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("cash_in"),
            func.coalesce(
                func.sum(
                    case(
                        (entry_cash_mtd_subq.c.entry_net_cash < 0, -entry_cash_mtd_subq.c.entry_net_cash),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("cash_out"),
        )
        dr_cash, cr_cash = (await session.execute(cash_flow_stmt)).one()
        cash_in_period = Decimal(str(dr_cash or "0.00"))
        cash_out_period = Decimal(str(cr_cash or "0.00"))
        net_cash_flow = cash_in_period - cash_out_period

        # 1c. Project Spending (MTD)
        proj_spend_stmt = select(
            func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalEntry.posting_date >= start_of_month,
                JournalEntry.posting_date <= as_of,
                JournalLine.project_id.isnot(None),
                ChartOfAccount.account_type == AccountType.EXPENSE
            )
        )
        project_spending = Decimal(str((await session.execute(proj_spend_stmt)).scalar() or "0.00"))

        # 1d. Unallocated Cash
        from src.models.money_movement import MoneyMovement, Settlement
        unalloc_stmt = select(
            func.coalesce(func.sum(MoneyMovement.amount), Decimal("0.00"))
        ).where(
            and_(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_date <= as_of
            )
        )
        total_movements = Decimal(str((await session.execute(unalloc_stmt)).scalar() or "0.00"))

        settled_stmt = select(
            func.coalesce(func.sum(Settlement.amount), Decimal("0.00"))
        ).where(
            Settlement.organization_id == organization_id
        )
        total_settled = Decimal(str((await session.execute(settled_stmt)).scalar() or "0.00"))
        unallocated_cash = max(Decimal("0.00"), total_movements - total_settled)


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
                VendorBill.bill_date <= as_of,
                VendorBill.status != "CANCELLED",
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
            cash_in_period=cash_in_period,
            cash_out_period=cash_out_period,
            net_cash_flow=net_cash_flow,
            unallocated_cash=unallocated_cash,
            project_spending=project_spending,
            accounts_receivable_outstanding=ar_outstanding,
            accounts_payable_outstanding=ap_outstanding,
            revenue_ytd=tot_rev_ytd,
            net_profit_ytd=net_profit_ytd,
            estimated_monthly_burn_rate=monthly_burn,
            cash_runway_months=cash_runway,
            active_projects_count=active_projects_count,
            review_queue_pending_count=pending_reviews,
            integrity_status="VALID" if is_balanced else "REPORT_INTEGRITY_ERROR"
        )

    @staticmethod
    async def get_cash_flow_trend(
        session: AsyncSession,
        organization_id: uuid.UUID,
        months: int = 6,
        as_of_date: Optional[date] = None
    ) -> CashFlowTrendResponse:
        as_of = as_of_date or date.today()
        id_months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

        items: List[MonthlyCashFlowTrendItem] = []
        for i in range(months - 1, -1, -1):
            total_months = as_of.year * 12 + (as_of.month - 1) - i
            target_year = total_months // 12
            target_month = (total_months % 12) + 1
            start_m = date(target_year, target_month, 1)
            days_in_month = calendar.monthrange(target_year, target_month)[1]
            end_m = date(target_year, target_month, days_in_month)
            if i == 0 and as_of < end_m:
                end_m = as_of

            period_str = f"{target_year}-{target_month:02d}"
            label_str = f"{id_months[target_month - 1]} {target_year}"

            # Net-neutral management cash flow aggregation:
            # Group cash debits and credits per journal entry first.
            # An internal cash transfer (e.g. Bank A -> Bank B) has net = 0 at company level,
            # so it does not inflate gross cash-in or gross cash-out.
            entry_cash_subq = (
                select(
                    JournalEntry.id.label("journal_entry_id"),
                    func.coalesce(
                        func.sum(JournalLine.debit_amount - JournalLine.credit_amount),
                        Decimal("0.00"),
                    ).label("entry_net_cash"),
                )
                .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
                .join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id)
                .where(
                    and_(
                        JournalEntry.organization_id == organization_id,
                        JournalEntry.posting_date >= start_m,
                        JournalEntry.posting_date <= end_m,
                        ChartOfAccount.account_code.like("1101%"),
                    )
                )
                .group_by(JournalEntry.id)
                .subquery()
            )

            flow_stmt = select(
                func.coalesce(
                    func.sum(
                        case(
                            (entry_cash_subq.c.entry_net_cash > 0, entry_cash_subq.c.entry_net_cash),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("cash_in"),
                func.coalesce(
                    func.sum(
                        case(
                            (entry_cash_subq.c.entry_net_cash < 0, -entry_cash_subq.c.entry_net_cash),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("cash_out"),
            )
            dr, cr = (await session.execute(flow_stmt)).one()
            c_in = Decimal(str(dr or "0.00"))
            c_out = Decimal(str(cr or "0.00"))
            items.append(
                MonthlyCashFlowTrendItem(
                    period=period_str,
                    month_label=label_str,
                    cash_in=c_in,
                    cash_out=c_out,
                    net_cash=c_in - c_out
                )
            )

        return CashFlowTrendResponse(items=items)

    @staticmethod
    async def get_project_performance(
        session: AsyncSession,
        organization_id: uuid.UUID,
        status_filter: Optional[ProjectStatus] = None,
        limit: Optional[int] = None
    ) -> ProjectPerformanceResponse:
        stmt = select(Project).options(
            selectinload(Project.customer)
        ).where(
            Project.organization_id == organization_id
        )
        if status_filter:
            stmt = stmt.where(Project.project_status == status_filter)
        stmt = stmt.order_by(Project.project_code.asc())
        if limit:
            stmt = stmt.limit(limit)

        projects = (await session.execute(stmt)).scalars().all()
        if not projects:
            return ProjectPerformanceResponse(
                items=[],
                total_active_projects=0,
                total_contract_value=Decimal("0.00"),
                total_actual_cost=Decimal("0.00"),
                average_margin_percentage=Decimal("0.00")
            )

        project_ids = [p.id for p in projects]

        cost_stmt = select(
            JournalLine.project_id,
            func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
        ).join(
            JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).join(
            ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
        ).where(
            and_(
                JournalEntry.organization_id == organization_id,
                JournalLine.project_id.in_(project_ids),
                ChartOfAccount.account_type == AccountType.EXPENSE,
                ChartOfAccount.account_code.like("5%")
            )
        ).group_by(JournalLine.project_id)
        cost_map = dict((await session.execute(cost_stmt)).all())

        inv_stmt = select(
            CustomerInvoice.project_id,
            func.coalesce(func.sum(CustomerInvoice.total_amount), Decimal("0.00"))
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.project_id.in_(project_ids),
                CustomerInvoice.status != "CANCELLED"
            )
        ).group_by(CustomerInvoice.project_id)
        inv_map = dict((await session.execute(inv_stmt)).all())

        rec_stmt = select(
            CustomerInvoice.project_id,
            func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00"))
        ).join(
            CustomerPaymentAllocation, CustomerPaymentAllocation.invoice_id == CustomerInvoice.id
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.project_id.in_(project_ids),
                CustomerInvoice.status != "CANCELLED"
            )
        ).group_by(CustomerInvoice.project_id)
        rec_map = dict((await session.execute(rec_stmt)).all())

        items: List[ProjectPerformanceItem] = []
        tot_contract = Decimal("0.00")
        tot_cost = Decimal("0.00")
        active_count = 0

        for p in projects:
            contract_v = Decimal(str(p.revised_contract_value))
            cost_v = Decimal(str(cost_map.get(p.id, Decimal("0.00"))))
            invoiced_v = Decimal(str(inv_map.get(p.id, Decimal("0.00"))))
            rec_v = Decimal(str(rec_map.get(p.id, Decimal("0.00"))))

            gp = contract_v - cost_v
            margin_pct = (gp / contract_v * Decimal("100.00")).quantize(Decimal("0.1")) if contract_v > Decimal("0.00") else Decimal("0.0")
            prog_pct = (cost_v / contract_v * Decimal("100.00")).quantize(Decimal("0.1")) if contract_v > Decimal("0.00") else Decimal("0.0")

            if cost_v > contract_v and contract_v > Decimal("0.00"):
                health = "CRITICAL"
            elif prog_pct >= Decimal("85.0") and p.project_status == ProjectStatus.ACTIVE:
                health = "WARNING"
            else:
                health = "NORMAL"

            if p.project_status == ProjectStatus.ACTIVE:
                active_count += 1
                tot_contract += contract_v
                tot_cost += cost_v

            cust_name = p.customer.name if p.customer else None

            items.append(
                ProjectPerformanceItem(
                    project_id=str(p.id),
                    project_code=p.project_code,
                    project_name=p.project_name,
                    customer_name=cust_name,
                    contract_value=contract_v,
                    actual_cost=cost_v,
                    invoiced_amount=invoiced_v,
                    cash_received=rec_v,
                    gross_profit=gp,
                    gross_margin_percentage=margin_pct,
                    financial_progress_percentage=prog_pct,
                    status=p.project_status.value,
                    health_status=health
                )
            )

        avg_margin = (
            ((tot_contract - tot_cost) / tot_contract * Decimal("100.00")).quantize(Decimal("0.1"))
            if tot_contract > Decimal("0.00")
            else Decimal("0.00")
        )

        return ProjectPerformanceResponse(
            items=items,
            total_active_projects=active_count,
            total_contract_value=tot_contract,
            total_actual_cost=tot_cost,
            average_margin_percentage=avg_margin
        )

    @staticmethod
    async def get_action_items(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> DashboardActionItemsResponse:
        as_of = as_of_date or date.today()

        doc_stmt = select(
            Document.processing_status,
            func.count(Document.id)
        ).where(
            Document.organization_id == organization_id
        ).group_by(Document.processing_status)
        doc_rows = (await session.execute(doc_stmt)).all()
        doc_counts = {status: count for status, count in doc_rows}

        req_review = doc_counts.get(DocumentProcessingStatus.REVIEW_REQUIRED, 0)
        failed = doc_counts.get(DocumentProcessingStatus.FAILED, 0)
        ready_to_post = doc_counts.get(DocumentProcessingStatus.READY_TO_POST, 0)

        unmatched_mov_stmt = select(
            func.count(MoneyMovement.id)
        ).where(
            and_(
                MoneyMovement.organization_id == organization_id,
                ~MoneyMovement.id.in_(
                    select(Settlement.money_movement_id).where(Settlement.organization_id == organization_id)
                )
            )
        )
        unmatched_movements = int((await session.execute(unmatched_mov_stmt)).scalar() or 0)

        ar_alloc_sub = select(
            CustomerPaymentAllocation.invoice_id,
            func.coalesce(func.sum(CustomerPaymentAllocation.allocated_amount), Decimal("0.00")).label("paid")
        ).group_by(CustomerPaymentAllocation.invoice_id).subquery()

        ar_stmt = select(
            func.count(CustomerInvoice.id),
            func.coalesce(func.sum(CustomerInvoice.total_amount - func.coalesce(ar_alloc_sub.c.paid, Decimal("0.00"))), Decimal("0.00"))
        ).outerjoin(
            ar_alloc_sub, CustomerInvoice.id == ar_alloc_sub.c.invoice_id
        ).where(
            and_(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.status != "CANCELLED",
                CustomerInvoice.due_date < as_of,
                (CustomerInvoice.total_amount - func.coalesce(ar_alloc_sub.c.paid, Decimal("0.00"))) > Decimal("0.00")
            )
        )
        ar_count, ar_amount = (await session.execute(ar_stmt)).one()

        ap_alloc_sub = select(
            VendorPaymentAllocation.bill_id,
            func.coalesce(func.sum(VendorPaymentAllocation.allocated_amount), Decimal("0.00")).label("paid")
        ).group_by(VendorPaymentAllocation.bill_id).subquery()

        ap_stmt = select(
            func.count(VendorBill.id),
            func.coalesce(func.sum(VendorBill.total_amount - func.coalesce(ap_alloc_sub.c.paid, Decimal("0.00"))), Decimal("0.00"))
        ).outerjoin(
            ap_alloc_sub, VendorBill.id == ap_alloc_sub.c.bill_id
        ).where(
            and_(
                VendorBill.organization_id == organization_id,
                VendorBill.status != "CANCELLED",
                VendorBill.due_date < as_of,
                (VendorBill.total_amount - func.coalesce(ap_alloc_sub.c.paid, Decimal("0.00"))) > Decimal("0.00")
            )
        )
        ap_count, ap_amount = (await session.execute(ap_stmt)).one()

        perf = await DashboardService.get_project_performance(
            session=session,
            organization_id=organization_id,
            status_filter=ProjectStatus.ACTIVE
        )
        warning_projects = sum(1 for item in perf.items if item.health_status in ("WARNING", "CRITICAL"))

        total_actions = (
            req_review +
            failed +
            ready_to_post +
            unmatched_movements +
            int(ar_count) +
            int(ap_count) +
            warning_projects
        )

        return DashboardActionItemsResponse(
            documents_requires_review=req_review,
            documents_failed=failed,
            documents_ready_to_post=ready_to_post,
            unmatched_bank_movements=unmatched_movements,
            overdue_ar_count=int(ar_count),
            overdue_ar_amount=Decimal(str(ar_amount)),
            overdue_ap_count=int(ap_count),
            overdue_ap_amount=Decimal(str(ap_amount)),
            projects_with_warning=warning_projects,
            total_action_count=total_actions
        )

    @staticmethod
    async def get_cash_bank_overview(
        session: AsyncSession,
        organization_id: uuid.UUID,
        as_of_date: Optional[date] = None
    ) -> CashBankOverviewResponse:
        as_of = as_of_date or date.today()

        stmt = select(PaymentAccount, ChartOfAccount).join(
            ChartOfAccount, PaymentAccount.coa_account_id == ChartOfAccount.id
        ).where(
            PaymentAccount.organization_id == organization_id
        ).order_by(ChartOfAccount.account_code.asc())
        rows = (await session.execute(stmt)).all()

        account_coa_ids = [pa.coa_account_id for pa, _ in rows]

        bal_map: dict = {}
        if account_coa_ids:
            bal_stmt = select(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit_amount - JournalLine.credit_amount), Decimal("0.00"))
            ).join(
                JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
            ).where(
                and_(
                    JournalEntry.organization_id == organization_id,
                    JournalLine.account_id.in_(account_coa_ids),
                    JournalEntry.posting_date <= as_of
                )
            ).group_by(JournalLine.account_id)
            bal_map = dict((await session.execute(bal_stmt)).all())

        pa_ids = [pa.id for pa, _ in rows]
        last_mov_map: dict = {}
        if pa_ids:
            mov_stmt = select(
                MoneyMovement.payment_account_id,
                func.max(MoneyMovement.movement_date)
            ).where(
                and_(
                    MoneyMovement.organization_id == organization_id,
                    MoneyMovement.payment_account_id.in_(pa_ids)
                )
            ).group_by(MoneyMovement.payment_account_id)
            last_mov_map = dict((await session.execute(mov_stmt)).all())

        unmatched_stmt = select(
            func.count(MoneyMovement.id),
            func.coalesce(func.sum(MoneyMovement.amount), Decimal("0.00"))
        ).where(
            and_(
                MoneyMovement.organization_id == organization_id,
                ~MoneyMovement.id.in_(
                    select(Settlement.money_movement_id).where(Settlement.organization_id == organization_id)
                )
            )
        )
        unmatched_count, unmatched_amt = (await session.execute(unmatched_stmt)).one()

        items: List[CashBankAccountItem] = []
        tot_bank = Decimal("0.00")
        tot_cash = Decimal("0.00")

        for pa, coa in rows:
            bal = Decimal(str(bal_map.get(pa.coa_account_id, Decimal("0.00"))))
            last_mov = last_mov_map.get(pa.id)

            is_cash = "KAS" in pa.name.upper() or "TUNAI" in pa.name.upper() or "PETTY" in pa.name.upper() or coa.account_code.startswith("1101-01") or coa.account_code == "1101.01"

            if is_cash:
                tot_cash += bal
                type_label = "CASH"
            else:
                tot_bank += bal
                type_label = "BANK"

            items.append(
                CashBankAccountItem(
                    id=str(pa.id),
                    name=pa.name,
                    bank_name=pa.bank_name,
                    account_number=pa.account_number,
                    account_type=type_label,
                    coa_account_code=coa.account_code,
                    balance=bal,
                    is_active=pa.is_active,
                    last_movement_date=last_mov
                )
            )

        total_cash_and_bank = tot_bank + tot_cash

        return CashBankOverviewResponse(
            total_cash_and_bank=total_cash_and_bank,
            total_bank=tot_bank,
            total_cash=tot_cash,
            unmatched_movements_count=int(unmatched_count or 0),
            unmatched_amount=Decimal(str(unmatched_amt or "0.00")),
            accounts=items
        )

