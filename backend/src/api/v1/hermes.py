"""Authenticated SaaS machine boundary for Hermes document orchestration."""
import hashlib
import hmac
import uuid
import json
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.models.enums import DocumentProcessingStatus, DocumentType
from src.models.hermes import HermesSubmission
from src.schemas.document import DocumentResponse
from src.services.audit_service import AuditService
from src.services.document_service import DocumentService
from src.services.documents.pipeline import process_document_background
from src.api.whatsapp_auth import whatsapp_machine_organization

router = APIRouter(prefix="/hermes", tags=["Hermes"])
DOCUMENT_INTAKE_OPERATION = "DOCUMENT_INTAKE"


async def get_hermes_organization_id(request: Request) -> uuid.UUID:
    """Authenticate a runtime machine secret before selecting its fixed tenant."""
    whatsapp_org = whatsapp_machine_organization(request)
    if whatsapp_org is not None:
        return whatsapp_org
    expected = settings.HERMES_AGENT_TOKEN
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Hermes machine endpoint is disabled")
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not hmac.compare_digest(
        authorization.removeprefix("Bearer "), expected
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Hermes machine credential")
    try:
        return uuid.UUID(settings.HERMES_ORGANIZATION_ID or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hermes machine tenant is not configured",
        ) from exc


def idempotency_hash(idempotency_key: str) -> str:
    """Fingerprint a client key without storing a replayable key value."""
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()


class WhatsAppSourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wamid: str = Field(min_length=1, max_length=128)
    sender_phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    timestamp: datetime
    caption: str = Field(max_length=4096)
    media_id: str = Field(min_length=1, max_length=128)


@router.post("/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    process: bool = Form(True),
    source_channel: str = Form("API"),
    source_metadata: str = Form("{}", max_length=10000),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=200),
    organization_id: uuid.UUID = Depends(get_hermes_organization_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Reuse Feature 005 immutable intake; this surface cannot approve or post."""
    metadata = {}
    sender = None
    if source_channel == "WHATSAPP":
        from src.api.v1.whatsapp_state import active_sender
        try:
            metadata = WhatsAppSourceMetadata.model_validate_json(source_metadata).model_dump(mode="json")
        except ValidationError:
            raise HTTPException(422, "Invalid WhatsApp source metadata") from None
        sender = await active_sender(db, metadata["sender_phone"], organization_id)
        if not sender:
            raise HTTPException(403, "Sender unavailable")
    elif source_channel != "API" or source_metadata != "{}":
        raise HTTPException(422, "Unsupported source metadata")
    key_hash = idempotency_hash(idempotency_key)
    existing = await db.scalar(select(HermesSubmission).where(and_(
        HermesSubmission.organization_id == organization_id,
        HermesSubmission.operation == DOCUMENT_INTAKE_OPERATION,
        HermesSubmission.idempotency_key_hash == key_hash,
    )))
    if existing:
        if not existing.document_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hermes submission is incomplete")
        response.status_code = status.HTTP_200_OK
        response.headers["X-Hermes-Correlation-ID"] = str(existing.id)
        return await DocumentService(db).get_document(organization_id, existing.document_id)

    submission = HermesSubmission(
        organization_id=organization_id,
        operation=DOCUMENT_INTAKE_OPERATION,
        idempotency_key_hash=key_hash,
        outcome_status="RECEIVED",
    )
    db.add(submission)
    await db.flush()

    service = DocumentService(db)
    from src.services.document_service import compute_sha256
    duplicate = await service.get_document_by_hash(organization_id, compute_sha256(file.file)) if sender else None
    document = duplicate or await service.ingest_document(
        organization_id=organization_id,
        file_obj=file.file,
        file_name=file.filename or "unknown_file",
        mime_type=file.content_type or "application/octet-stream",
        document_type=document_type,
        source_channel=source_channel,
        source_metadata={**metadata, "hermes_submission_id": str(submission.id)},
        created_by=sender.user_id if sender else None,
    )
    submission.document_id = document.id
    submission.outcome_status = "ACCEPTED"
    await AuditService(db).log_event(
        organization_id, "HermesSubmission", submission.id, "HERMES_DOCUMENT_SUBMITTED",
        new_values={
            "document_id": str(document.id),
            "operation": DOCUMENT_INTAKE_OPERATION,
            "idempotency_key_fingerprint": key_hash[:12],
            "outcome_status": submission.outcome_status,
        },
    )
    if duplicate:
        response.headers["X-Document-Duplicate"] = "true"
    if process and not duplicate:
        document.processing_status = DocumentProcessingStatus.EXTRACTING
        await db.flush()
        background_tasks.add_task(process_document_background, document.id)
    response.headers["X-Hermes-Correlation-ID"] = str(submission.id)
    if sender:
        await db.commit()
    return document
