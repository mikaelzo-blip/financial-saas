import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from tests.reporting_support import seed_cash_profit_ledger
from src.services.reporting.equity_changes_service import EquityChangesService, CALKService
from src.services.reporting.export_service import ExportService
from src.services.reporting.excel_export_service import ExcelExportService
from src.services.reporting.pdf_export_service import PdfExportService


@pytest.mark.asyncio
async def test_equity_changes_and_calk_reconcile(db_session: AsyncSession):
    # Seed ledger with revenue 100,000,000.03 and cogs 30,000,000.01 -> net profit 70,000,000.02
    org = await seed_cash_profit_ledger(db_session, "equity-calk-test", Decimal("100000000.03"), Decimal("30000000.01"))
    start, end = date(2026, 8, 1), date(2026, 8, 31)

    # 1. Statement of Changes in Equity
    equity_report = await EquityChangesService.get_equity_changes(db_session, org.id, start, end)
    assert equity_report.organization_name == org.legal_name
    assert equity_report.current_period_net_profit == Decimal("70000000.02")
    assert equity_report.closing_total_equity == Decimal("70000000.02")

    # Verify export parity for equity-changes
    model_equity = ExportService.build("equity-changes", equity_report)
    assert model_equity.report_type == "equity-changes"
    xlsx_stream = ExcelExportService.render(model_equity)
    assert len(xlsx_stream.getvalue()) > 0
    pdf_stream = PdfExportService.render(model_equity)
    assert len(pdf_stream.getvalue()) > 0

    # 2. CALK Report
    calk_report = await CALKService.get_calk_report(db_session, org.id, end)
    assert calk_report.accounting_standards_basis == "SAK EP-Oriented"
    assert len(calk_report.accounting_policies) >= 5
    assert calk_report.profit_loss_summary["net_profit"] == Decimal("70000000.02")
    assert calk_report.balance_sheet_summary["balancing_difference"] == Decimal("0.00")

    # Verify export parity for CALK
    model_calk = ExportService.build("calk", calk_report)
    assert model_calk.report_type == "calk"
    calk_xlsx = ExcelExportService.render(model_calk)
    assert len(calk_xlsx.getvalue()) > 0
    calk_pdf = PdfExportService.render(model_calk)
    assert len(calk_pdf.getvalue()) > 0
