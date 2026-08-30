import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.models.enums import DocumentType
from src.schemas.document import DocumentResponse
from src.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Source Evidentiary Document"
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    source_channel: str = Form("WEB_UPLOAD"),
    project_id: Optional[uuid.UUID] = Form(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    document = await service.ingest_document(
        organization_id=org_id,
        file_obj=file.file,
        file_name=file.filename or "unknown_file",
        mime_type=file.content_type or "application/octet-stream",
        document_type=document_type,
        source_channel=source_channel,
        project_id=project_id
    )
    return document


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Metadata"
)
async def get_document(
    document_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    return await service.get_document(org_id, document_id)


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List Documents"
)
async def list_documents(
    document_type: Optional[DocumentType] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = DocumentService(db)
    return await service.list_documents(org_id, document_type=document_type)
