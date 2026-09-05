import uuid
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user
from src.schemas.bank_reconciliation import (
    BankStatementImportResponse,
    BankStatementLineResponse,
    BankReconciliationMatchRequest,
    CashCompletenessDashboardResponse,
)
from src.services.bank_reconciliation_service import BankReconciliationService

router = APIRouter()


@router.post(
    "/imports",
    response_model=BankStatementImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Import Bank Statement"
)
async def upload_bank_statement(
    payment_account_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = BankReconciliationService(db)
    content = await file.read()
    stmt_import = await service.import_statement(
        organization_id=org_id,
        payment_account_id=payment_account_id,
        source_file=file.filename or "statement.csv",
        file_content=content
    )
    return BankStatementImportResponse(
        id=stmt_import.id,
        organization_id=stmt_import.organization_id,
        payment_account_id=stmt_import.payment_account_id,
        period_start=stmt_import.period_start,
        period_end=stmt_import.period_end,
        file_hash=stmt_import.file_hash,
        source_file=stmt_import.source_file,
        imported_at=stmt_import.imported_at,
        status=stmt_import.status,
        line_count=len(stmt_import.lines) if stmt_import.lines else 0
    )


@router.post(
    "/imports/{import_id}/auto-match",
    summary="Run Auto-Match on Statement Import"
)
async def auto_match_statement(
    import_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = BankReconciliationService(db)
    stats = await service.auto_match_statement(org_id, import_id)
    return {"message": "Auto-match execution complete", "stats": stats}


@router.post(
    "/reconcile",
    summary="Manual Reconciliation Match"
)
async def manual_reconcile(
    req: BankReconciliationMatchRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = BankReconciliationService(db)
    reconcil = await service.match_manual(org_id, req, matched_by=user.id)
    return {"message": "Reconciliation match created", "id": str(reconcil.id)}


@router.get(
    "/dashboard",
    response_model=CashCompletenessDashboardResponse,
    summary="Get Cash Completeness Dashboard"
)
async def get_cash_completeness_dashboard(
    payment_account_id: Optional[uuid.UUID] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = BankReconciliationService(db)
    return await service.get_cash_completeness_dashboard(org_id, payment_account_id=payment_account_id)
