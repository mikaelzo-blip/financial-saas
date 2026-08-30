import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.schemas.reporting import (
    IntegrityReportResponse,
    TrialBalanceResponse,
    GeneralLedgerResponse,
    ProfitLossReportResponse,
    BalanceSheetReportResponse,
    CashFlowReportResponse,
    ARAgingReportResponse,
    APAgingReportResponse,
    ProjectProfitabilityReportResponse,
    ProjectCashPositionReportResponse,
    BudgetVsActualReportResponse,
    DashboardSummaryResponse
)
from src.services.reporting.integrity_service import IntegrityService
from src.services.reporting.trial_balance_service import TrialBalanceService
from src.services.reporting.gl_service import GeneralLedgerService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.reporting.budget_service import BudgetVsActualService
from src.services.reporting.dashboard_service import DashboardService
from src.services.reporting.excel_export_service import ExcelExportService
from src.services.reporting.pdf_export_service import PdfExportService
from src.services.reporting.export_service import SUPPORTED_REPORT_TYPES, ExportService, safe_filename

router = APIRouter(prefix="/reports", tags=["Financial Reports"])


async def _get_authoritative_export_report(
    report_type: str,
    db: AsyncSession,
    org_id: uuid.UUID,
    start_date: Optional[date],
    end_date: Optional[date],
    as_of_date: Optional[date],
    account_code: Optional[str],
    project_id: Optional[uuid.UUID],
):
    """Resolve exports through the same tenant-scoped services used by JSON APIs."""
    if report_type == "profit-loss":
        return await ProfitLossService.get_profit_and_loss(db, org_id, start_date, end_date)
    if report_type == "balance-sheet":
        report = await BalanceSheetService.get_balance_sheet(db, org_id, as_of_date)
        if report.integrity_status != "VALID":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Official export blocked: balance sheet integrity error.")
        return report
    if report_type == "cash-flow":
        return await CashFlowService.get_cash_flow(db, org_id, start_date, end_date)
    if report_type == "trial-balance":
        return await TrialBalanceService.get_trial_balance(db, org_id, start_date, end_date, as_of_date)
    if report_type == "general-ledger":
        if not account_code or not start_date or not end_date:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account_code, start_date, and end_date are required for general-ledger export.")
        return await GeneralLedgerService.get_general_ledger(db, org_id, account_code, start_date, end_date, project_id=project_id, page=1, page_size=500)
    if report_type == "receivables-aging":
        return await ARAgingService.get_ar_aging(db, org_id, as_of_date)
    if report_type == "payables-aging":
        return await APAgingService.get_ap_aging(db, org_id, as_of_date)
    if report_type == "project-profitability":
        if not project_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="project_id is required for project-profitability export.")
        return await ProjectReportingService.get_project_profitability(db, org_id, project_id)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unsupported report type. Supported values: {', '.join(sorted(SUPPORTED_REPORT_TYPES))}")


@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    format: str = Query(..., pattern="^(xlsx|pdf)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    as_of_date: Optional[date] = None,
    account_code: Optional[str] = None,
    project_id: Optional[uuid.UUID] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Download a tenant-isolated report generated from its authoritative DTO."""
    try:
        report = await _get_authoritative_export_report(report_type, db, org_id, start_date, end_date, as_of_date, account_code, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    model = ExportService.build(report_type, report)
    if format == "xlsx":
        stream = ExcelExportService.render(model)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        stream = PdfExportService.render(model)
        media_type = "application/pdf"
    filename = safe_filename(model.filename_stem, format)
    return StreamingResponse(stream, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/profit-loss/export")
async def export_profit_loss_report(
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Export Profit & Loss report as XLSX or PDF with verified identical figures.
    """
    pl = await ProfitLossService.get_profit_and_loss(db, org_id, start_date, end_date)
    if format == "xlsx":
        stream = ExcelExportService.export_profit_loss(pl)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=Laba_Rugi_{pl.start_date}_{pl.end_date}.xlsx"}
        )
    else:
        stream = PdfExportService.export_profit_loss(pl)
        return StreamingResponse(
            stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Laba_Rugi_{pl.start_date}_{pl.end_date}.pdf"}
        )


@router.get("/balance-sheet/export")
async def export_balance_sheet_report(
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Export Balance Sheet report as XLSX or PDF with verified identical figures.
    """
    bs = await BalanceSheetService.get_balance_sheet(db, org_id, as_of_date)
    if format == "xlsx":
        stream = ExcelExportService.export_balance_sheet(bs)
        return StreamingResponse(
            stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=Neraca_{bs.as_of_date}.xlsx"}
        )
    else:
        stream = PdfExportService.export_balance_sheet(bs)
        return StreamingResponse(
            stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Neraca_{bs.as_of_date}.pdf"}
        )


@router.get("/dashboard", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate real-time Executive Management Dashboard KPIs and runway metrics.
    """
    return await DashboardService.get_dashboard_summary(
        session=db,
        organization_id=org_id,
        as_of_date=as_of_date
    )


@router.get("/cash-flow", response_model=CashFlowReportResponse)
async def get_cash_flow_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Cash Flow Statement (Direct Method).
    """
    return await CashFlowService.get_cash_flow(
        session=db,
        organization_id=org_id,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/receivables-aging", response_model=ARAgingReportResponse)
async def get_ar_aging_report(
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Accounts Receivable Aging report based on invoice due dates.
    """
    return await ARAgingService.get_ar_aging(
        session=db,
        organization_id=org_id,
        as_of_date=as_of_date
    )


@router.get("/payables-aging", response_model=APAgingReportResponse)
async def get_ap_aging_report(
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Accounts Payable Aging report based on vendor bill due dates.
    """
    return await APAgingService.get_ap_aging(
        session=db,
        organization_id=org_id,
        as_of_date=as_of_date
    )


@router.get("/project-profitability", response_model=ProjectProfitabilityReportResponse)
async def get_project_profitability_report(
    project_id: uuid.UUID = Query(..., description="Project ID"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Project Profitability report (Accrual basis: Revenue Recognized - 9 Cost Categories).
    """
    try:
        return await ProjectReportingService.get_project_profitability(
            session=db,
            organization_id=org_id,
            project_id=project_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/project-cash", response_model=ProjectCashPositionReportResponse)
async def get_project_cash_position_report(
    project_id: uuid.UUID = Query(..., description="Project ID"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Project Cash Position report (Cash In - Cash Out liquidity).
    """
    try:
        return await ProjectReportingService.get_project_cash_position(
            session=db,
            organization_id=org_id,
            project_id=project_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/budget-vs-actual", response_model=BudgetVsActualReportResponse)
async def get_budget_vs_actual_report(
    project_id: uuid.UUID = Query(..., description="Project ID"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Budget vs Actual report per project cost category.
    """
    try:
        return await BudgetVsActualService.get_budget_vs_actual(
            session=db,
            organization_id=org_id,
            project_id=project_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/balance-sheet", response_model=BalanceSheetReportResponse)
async def get_balance_sheet_report(
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate standard Indonesian contractor Balance Sheet (Laporan Neraca) with equation validation.
    """
    return await BalanceSheetService.get_balance_sheet(
        session=db,
        organization_id=org_id,
        as_of_date=as_of_date
    )


@router.get("/profit-loss", response_model=ProfitLossReportResponse)
async def get_profit_loss_report(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    compare_with: Optional[str] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate standard Indonesian contractor Profit & Loss Statement (Laporan Laba Rugi).
    """
    return await ProfitLossService.get_profit_and_loss(
        session=db,
        organization_id=org_id,
        start_date=start_date,
        end_date=end_date,
        compare_with=compare_with
    )


@router.get("/integrity", response_model=IntegrityReportResponse)
async def get_integrity_report(
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Run financial diagnostics and accounting equation balance checks.
    """
    return await IntegrityService.run_diagnostics(
        session=db,
        organization_id=org_id,
        as_of_date=as_of_date
    )


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    as_of_date: Optional[date] = None,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate dynamic SAK Trial Balance (Neraca Saldo) from posted journal lines.
    """
    return await TrialBalanceService.get_trial_balance(
        session=db,
        organization_id=org_id,
        start_date=start_date,
        end_date=end_date,
        as_of_date=as_of_date
    )


@router.get("/general-ledger", response_model=GeneralLedgerResponse)
async def get_general_ledger(
    account_code: str = Query(..., description="Chart of Account code"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by project"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch chronological General Ledger entries with dynamic running balance.
    """
    try:
        return await GeneralLedgerService.get_general_ledger(
            session=db,
            organization_id=org_id,
            account_code=account_code,
            start_date=start_date,
            end_date=end_date,
            project_id=project_id,
            page=page,
            page_size=page_size
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
