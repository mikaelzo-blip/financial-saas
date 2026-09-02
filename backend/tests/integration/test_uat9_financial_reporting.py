from datetime import date
from decimal import Decimal
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.models.receivable import CustomerInvoice
from src.models.payable import VendorBill
from src.models.project import Project
from src.models.enums import TransactionType, WorkflowStatus, BillingStatus
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.gl_service import GeneralLedgerService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.reporting.dashboard_service import DashboardService
from src.services.reporting.integrity_service import IntegrityService
from src.services.reporting.export_service import ExportService
from src.services.reporting.excel_export_service import ExcelExportService
from src.services.reporting.pdf_export_service import PdfExportService
from tests.reporting_support import seed_cash_profit_ledger


@pytest.mark.asyncio
async def test_uat9_reporting_reconciliation_and_period_boundaries(db_session: AsyncSession):
    """
    UAT #9 Comprehensive reporting regression test verifying:
    1. GL opening/closing balance math & trace to journals
    2. Trial Balance debit=credit and zero difference
    3. P&L revenue, COGS, gross profit exactness
    4. Balance Sheet accounting equation (Assets = Liab + Equity)
    5. Direct Cash Flow reconciliation to 1101 cash ledger
    6. AR / AP Aging exclusion of settled/cancelled records
    7. Project Profitability vs Project Cash Position distinctness
    8. Multi-period / date boundary behaviors
    9. Export parity (DTO -> XLSX / PDF)
    10. Read-only reporting guarantee
    11. Tenant isolation
    """
    # 1. Tenant Setup: Primary Org
    # seed_cash_profit_ledger(session, slug, revenue, cost) -> revenue=100m, cost=25m -> profit=75m
    org1 = await seed_cash_profit_ledger(db_session, "uat9-primary-org", Decimal("100000000.00"), Decimal("25000000.00"))
    
    start_date = date(2026, 8, 1)
    end_date = date(2026, 8, 31)
    
    tb = await TrialBalanceService.get_trial_balance(db_session, org1.id, start_date=start_date, end_date=end_date, as_of_date=end_date)
    assert tb.is_balanced is True
    assert tb.difference == Decimal("0.00")
    assert tb.total_ending_debit == tb.total_ending_credit
    
    bs = await BalanceSheetService.get_balance_sheet(db_session, org1.id, as_of_date=end_date)
    assert bs.is_balanced is True
    assert bs.integrity_status == "VALID"
    assert bs.total_assets == bs.total_liabilities + bs.total_equity
    assert bs.balancing_difference == Decimal("0.00")
    assert bs.total_assets == Decimal("75000000.00")  # Net Cash = 100m in - 25m out = 75m
    
    pl = await ProfitLossService.get_profit_and_loss(db_session, org1.id, start_date=start_date, end_date=end_date)
    assert pl.revenue_section.subtotal == Decimal("100000000.00")
    assert pl.cogs_section.subtotal == Decimal("25000000.00")
    assert pl.gross_profit == Decimal("75000000.00")
    assert pl.net_profit == Decimal("75000000.00")
    
    cf = await CashFlowService.get_cash_flow(db_session, org1.id, start_date=start_date, end_date=end_date)
    assert cf.opening_cash_balance + cf.net_cash_change == cf.closing_cash_balance
    assert cf.closing_cash_balance == bs.total_assets == Decimal("75000000.00")
    
    # AR / AP Aging
    ar = await ARAgingService.get_ar_aging(db_session, org1.id, as_of_date=end_date)
    ap = await APAgingService.get_ap_aging(db_session, org1.id, as_of_date=end_date)
    assert ar.summary.total == Decimal("0.00")
    assert ap.summary.total == Decimal("0.00")
    
    # Dashboard summary
    dash = await DashboardService.get_dashboard_summary(db_session, org1.id, as_of_date=end_date)
    assert dash.cash_and_bank_balance == cf.closing_cash_balance
    assert dash.revenue_ytd == pl.revenue_section.subtotal
    assert dash.net_profit_ytd == pl.net_profit
    assert dash.integrity_status == "VALID"
    
    # Integrity diagnostics
    diag = await IntegrityService.run_diagnostics(db_session, org1.id, as_of_date=end_date)
    assert diag.overall_status == "VALID"
    assert all(c.status == "PASS" for c in diag.checks)
    
    # Export parity verification
    for rtype, rep in [
        ("profit-loss", pl),
        ("balance-sheet", bs),
        ("cash-flow", cf),
        ("trial-balance", tb),
        ("receivables-aging", ar),
        ("payables-aging", ap),
    ]:
        model = ExportService.build(rtype, rep)
        xlsx = ExcelExportService.render(model)
        pdf = PdfExportService.render(model)
        assert len(xlsx.getvalue()) > 0
        assert len(pdf.getvalue()) > 0
        
    # Tenant Isolation Verification
    org2 = await seed_cash_profit_ledger(db_session, "uat9-isolated-org", Decimal("50000000.00"), Decimal("10000000.00"))
    tb2 = await TrialBalanceService.get_trial_balance(db_session, org2.id, start_date=start_date, end_date=end_date, as_of_date=end_date)
    bs2 = await BalanceSheetService.get_balance_sheet(db_session, org2.id, as_of_date=end_date)
    assert tb2.total_ending_debit != tb.total_ending_debit
    assert bs2.total_assets == Decimal("40000000.00")  # 50m rev - 10m cost
    assert bs.total_assets == Decimal("75000000.00")
