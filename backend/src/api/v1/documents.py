import uuid
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, Query, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from src.core.database import get_db
from src.api.deps import get_current_org_id, get_current_user_id
from src.models.enums import DocumentType, DocumentProcessingStatus, CandidateStatus
from src.models.document import DocumentCorrection
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.coa import PaymentAccount
from src.models.user import User
from src.models.enums import UserRole
from src.schemas.document import DocumentResponse, DocumentCorrectionRequest, TransactionCandidate
from src.schemas.transaction import TransactionCreate, TransactionResponse
from src.services.document_service import DocumentService
from src.services.documents.pipeline import process_document_background
from src.services.transaction_service import TransactionService
from src.services.audit_service import AuditService

router = APIRouter(prefix="/documents", tags=["Documents"])


async def require_reviewer(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(and_(User.id == user_id, User.organization_id == org_id,
        User.role.in_([UserRole.ADMIN, UserRole.MANAGER]))))
    if not user:
        raise HTTPException(status_code=403, detail="Manager or administrator review permission required")
    return user


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Source Evidentiary Document"
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    source_channel: str = Form("WEB"),
    project_id: Optional[uuid.UUID] = Form(None),
    process: bool = Form(True),
    org_id: uuid.UUID = Depends(get_current_org_id),
    user_id: uuid.UUID = Depends(get_current_user_id),
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
        project_id=project_id,
        created_by=user_id
    )
    if process:
        document.processing_status = DocumentProcessingStatus.EXTRACTING
        await db.flush()
        background_tasks.add_task(process_document_background, document.id)
    return document


@router.get("/{document_id}/content", summary="Stream Immutable Original")
async def get_document_content(document_id: uuid.UUID, org_id: uuid.UUID = Depends(get_current_org_id),
                               db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id)
    path = service.storage.get_file_path(document.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored document content not found")
    return FileResponse(path, media_type=document.mime_type, filename=document.file_name)


@router.post("/{document_id}/retry", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_document(document_id: uuid.UUID, background_tasks: BackgroundTasks,
                         org_id: uuid.UUID = Depends(get_current_org_id),
                         db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id)
    if document.processing_status not in {DocumentProcessingStatus.FAILED, DocumentProcessingStatus.REVIEW_REQUIRED}:
        raise HTTPException(status_code=409, detail="Document is not in a retryable state")
    document.processing_status = DocumentProcessingStatus.EXTRACTING
    await db.flush()
    background_tasks.add_task(process_document_background, document.id)
    return document


@router.post("/{document_id}/corrections", response_model=DocumentResponse)
async def correct_document(document_id: uuid.UUID, data: DocumentCorrectionRequest,
                           org_id: uuid.UUID = Depends(get_current_org_id),
                           user_id: uuid.UUID = Depends(get_current_user_id),
                           db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_document(org_id, document_id)
    await require_reviewer(db, org_id, user_id)
    allowed = {"project_id", "counterparty_id", "payment_account_id", "proposed_transaction_type",
               "cost_category", "expense_category", "transaction_date", "amount", "description", "external_reference"}
    if not data.changes or set(data.changes) - allowed:
        raise HTTPException(status_code=422, detail="Correction contains unsupported fields")
    candidate = dict(document.candidate_transaction)
    old = {key: candidate.get(key) for key in data.changes}
    candidate.update(data.changes)
    validated = TransactionCandidate.model_validate(candidate)
    checks = ((validated.project_id, Project), (validated.counterparty_id, Counterparty),
              (validated.payment_account_id, PaymentAccount))
    for entity_id, model in checks:
        if entity_id and not await db.scalar(select(model.id).where(and_(model.id == entity_id, model.organization_id == org_id))):
            raise HTTPException(status_code=422, detail=f"{model.__name__} is not available in this organization")
    document.candidate_transaction = validated.model_dump(mode="json")
    resolved = {"project_id": "PROJECT_UNKNOWN", "counterparty_id": "VENDOR_UNKNOWN",
                "amount": "OCR_LOW_CONFIDENCE", "transaction_date": "OCR_LOW_CONFIDENCE"}
    cleared = {resolved[key] for key, value in data.changes.items() if key in resolved and value}
    document.review_flags = [flag for flag in document.review_flags if flag not in cleared]
    if not document.review_flags and validated.proposed_transaction_type and validated.amount and validated.transaction_date:
        validated.status = CandidateStatus.READY_FOR_APPROVAL
        document.candidate_transaction = validated.model_dump(mode="json")
        document.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    for key, value in data.changes.items():
        db.add(DocumentCorrection(organization_id=org_id, document_id=document.id, field_path=key,
            old_value=old.get(key), new_value=value, reason=data.reason, corrected_by=user_id))
    await AuditService(db).log_event(org_id, "Document", document.id, "CORRECT_EXTRACTION", user_id,
                                     old_values=old, new_values=data.changes, reason=data.reason)
    await db.flush()
    return document


@router.post("/{document_id}/approve", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def approve_document_candidate(document_id: uuid.UUID, org_id: uuid.UUID = Depends(get_current_org_id),
                                     user_id: uuid.UUID = Depends(get_current_user_id),
                                     db: AsyncSession = Depends(get_db)):
    document = await DocumentService(db).get_document(org_id, document_id)
    await require_reviewer(db, org_id, user_id)
    if document.review_flags or document.processing_status != DocumentProcessingStatus.READY_FOR_APPROVAL:
        raise HTTPException(status_code=409, detail="Document has unresolved review requirements")
    candidate = TransactionCandidate.model_validate(document.candidate_transaction)
    if candidate.converted_transaction_id:
        raise HTTPException(status_code=409, detail="Candidate already converted")
    if not candidate.proposed_transaction_type or not candidate.transaction_date or not candidate.amount:
        raise HTTPException(status_code=409, detail="Candidate is incomplete")
    transaction = await TransactionService(db).create_transaction(org_id, TransactionCreate(
        transaction_type=candidate.proposed_transaction_type, transaction_date=candidate.transaction_date,
        amount=candidate.amount, currency=candidate.currency_code or "IDR", counterparty_id=candidate.counterparty_id,
        payment_account_id=candidate.payment_account_id, reference_no=candidate.external_reference,
        description=candidate.description or f"Document {document.document_code}", document_ids=[document.id],
        project_id=candidate.project_id, cost_category=candidate.cost_category,
        expense_category=candidate.expense_category), created_by=user_id)
    candidate.status, candidate.converted_transaction_id = CandidateStatus.CONVERTED, transaction.id
    document.candidate_transaction = candidate.model_dump(mode="json")
    document.processing_status = DocumentProcessingStatus.PROCESSED
    await AuditService(db).log_event(org_id, "Document", document.id, "CONVERT_CANDIDATE", user_id,
                                     new_values={"transaction_id": str(transaction.id)})
    await db.flush()
    return transaction


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
