from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.auth import require_application_user
from src.models.user import User
from src.schemas.consultant_reconciliation import (
    ConsultantFinancialStatementData,
    ConsultantReconciliationReport,
)
from src.services.reporting.consultant_reconciliation_service import (
    ConsultantReconciliationService,
)

router = APIRouter(prefix="/reports/consultant-reconciliation", tags=["Consultant Reconciliation"])


@router.get("/verified/{year}", response_model=ConsultantFinancialStatementData)
async def get_verified_statement(
    year: int,
    current_user: User = Depends(require_application_user),
) -> ConsultantFinancialStatementData:
    """Returns verified historical consultant statement data for 2023, 2024, or 2025."""
    stmt = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS.get(year)
    if not stmt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan konsultan terverifikasi untuk tahun {year} belum tersedia. Tahun yang tersedia: 2023, 2024, 2025.",
        )
    return stmt


@router.post("/reconcile-verified/{year}", response_model=ConsultantReconciliationReport)
async def reconcile_verified_year(
    year: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user),
) -> ConsultantReconciliationReport:
    """Reconciles Financial SaaS live double-entry ledger with verified consultant statement for the year."""
    stmt = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS.get(year)
    if not stmt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laporan konsultan terverifikasi untuk tahun {year} belum tersedia.",
        )
    return await ConsultantReconciliationService.reconcile_with_saas(
        session=session,
        organization_id=current_user.organization_id,
        consultant_data=stmt,
    )


@router.post("/compare", response_model=ConsultantReconciliationReport)
async def compare_consultant_statement(
    consultant_data: ConsultantFinancialStatementData,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user),
) -> ConsultantReconciliationReport:
    """Accepts consultant financial data and runs side-by-side reconciliation with Financial SaaS ledger."""
    return await ConsultantReconciliationService.reconcile_with_saas(
        session=session,
        organization_id=current_user.organization_id,
        consultant_data=consultant_data,
    )


@router.post("/upload", response_model=ConsultantReconciliationReport)
async def upload_consultant_statement(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user),
) -> ConsultantReconciliationReport:
    """Uploads PDF or XLSX consultant statement, extracts statement values, and runs reconciliation."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nama file tidak valid.")

    contents = await file.read()
    if file.filename.lower().endswith(".pdf"):
        data = ConsultantReconciliationService.parse_consultant_pdf(contents, file.filename)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format file tidak didukung. Harap upload file .pdf laporan keuangan konsultan.",
        )

    return await ConsultantReconciliationService.reconcile_with_saas(
        session=session,
        organization_id=current_user.organization_id,
        consultant_data=data,
    )
