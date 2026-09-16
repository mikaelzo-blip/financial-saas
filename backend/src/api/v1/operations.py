import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user
from src.models.user import User
from src.models.enums import DocumentType, DocumentProcessingStatus
from src.schemas.document_operations import (
    DocumentOperationsSummaryResponse,
    DocumentOperationalListResponse,
)
from src.services.document_operations_service import DocumentOperationsService

router = APIRouter(prefix="/operations/documents", tags=["Document Operations"])


@router.get(
    "/summary",
    response_model=DocumentOperationsSummaryResponse,
    summary="Get Operational Document Pipeline Summary & Queue Health",
)
async def get_operational_summary(
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_application_user),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentOperationsService(db)
    return await service.get_summary(org_id)


@router.get(
    "",
    response_model=DocumentOperationalListResponse,
    summary="List Operational Documents with Filtering and Pagination",
)
async def list_operational_documents(
    processing_status: Optional[DocumentProcessingStatus] = Query(None),
    action_filter: Optional[str] = Query(None),
    source_channel: Optional[str] = Query(None),
    document_type: Optional[DocumentType] = Query(None),
    review_flag: Optional[str] = Query(None),
    project_id: Optional[uuid.UUID] = Query(None),
    counterparty_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    failed_or_retrying: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_application_user),
    db: AsyncSession = Depends(get_db),
):
    service = DocumentOperationsService(db)
    return await service.list_operational_documents(
        organization_id=org_id,
        processing_status=processing_status,
        action_filter=action_filter,
        source_channel=source_channel,
        document_type=document_type,
        review_flag=review_flag,
        project_id=project_id,
        counterparty_id=counterparty_id,
        date_from=date_from,
        date_to=date_to,
        failed_or_retrying=failed_or_retrying,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        limit=limit,
    )
