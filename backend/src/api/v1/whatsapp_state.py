"""SaaS-owned state endpoints. Only this boundary accesses channel persistence."""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.whatsapp_auth import require_adapter, require_whatsapp_machine, require_whatsapp_admin
from src.core.database import get_db
from src.models.user import User
from src.models.whatsapp import WhatsAppSenderMapping, WhatsAppMessageLog, WhatsAppClarificationSession
from src.models.document import Document, DocumentCorrection
from src.models.project import Project
from src.models.enums import DocumentProcessingStatus, ProjectStatus
from src.schemas.document import TransactionCandidate
from src.schemas.whatsapp import SenderCreate, SenderResponse, InboundMessage
from src.services.audit_service import AuditService

router = APIRouter(tags=["WhatsApp state"])
PREFIX = "/hermes/whatsapp"


async def active_sender(db, phone, org=None):
    query = select(WhatsAppSenderMapping).join(User, User.id == WhatsAppSenderMapping.user_id).where(
        WhatsAppSenderMapping.phone_number == phone, WhatsAppSenderMapping.is_active.is_(True),
        User.is_active.is_(True), User.organization_id == WhatsAppSenderMapping.organization_id)
    if org is not None:
        query = query.where(WhatsAppSenderMapping.organization_id == org)
    return await db.scalar(query)


@router.get("/integrations/whatsapp/senders", response_model=list[SenderResponse])
async def list_senders(admin: User = Depends(require_whatsapp_admin), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.organization_id == admin.organization_id))).all()


@router.post("/integrations/whatsapp/senders", response_model=SenderResponse, status_code=201)
async def create_sender(data: SenderCreate, admin: User = Depends(require_whatsapp_admin), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.id == data.user_id, User.organization_id == admin.organization_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(400, "User is not available in this organization")
    mapping = WhatsAppSenderMapping(organization_id=admin.organization_id, **data.model_dump())
    try:
        async with db.begin_nested():
            db.add(mapping)
            await db.flush()
    except IntegrityError:
        raise HTTPException(400, "Phone number is unavailable") from None
    await AuditService(db).log_event(admin.organization_id, "WhatsAppSenderMapping", mapping.id, "REGISTER_SENDER", admin.id, new_values=data.model_dump(mode="json"))
    await db.commit()
    return mapping


@router.delete("/integrations/whatsapp/senders/{mapping_id}", status_code=204)
async def disable_sender(mapping_id: uuid.UUID, admin: User = Depends(require_whatsapp_admin), db: AsyncSession = Depends(get_db)):
    mapping = await db.scalar(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.id == mapping_id, WhatsAppSenderMapping.organization_id == admin.organization_id))
    if not mapping:
        raise HTTPException(404, "Mapping not found")
    mapping.is_active = False
    await AuditService(db).log_event(admin.organization_id, "WhatsAppSenderMapping", mapping.id, "DISABLE_SENDER", admin.id, old_values={"is_active": True}, new_values={"is_active": False})
    await db.commit()


class PhoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


@router.post(PREFIX + "/resolve", dependencies=[Depends(require_adapter)])
async def resolve_sender(data: PhoneRequest, db: AsyncSession = Depends(get_db)):
    mapping = await active_sender(db, data.phone_number)
    return {"sender": SenderResponse.model_validate(mapping).model_dump(mode="json") if mapping else None}


@router.post(PREFIX + "/messages/claim")
async def claim_message(event: InboundMessage, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    if not await active_sender(db, event.sender_phone, org):
        raise HTTPException(403, "Sender unavailable")
    log = WhatsAppMessageLog(organization_id=org, wamid=event.wamid, direction="INBOUND", phone_number=event.sender_phone,
        message_type=event.message_type, raw_text="".join(c for c in event.text if c.isprintable() or c == "\n"),
        media_mime_type=event.mime_type, delivery_status="PROCESSING")
    try:
        async with db.begin_nested():
            db.add(log)
            await db.flush()
    except IntegrityError:
        return {"claimed": False}
    await db.commit()
    return {"claimed": True}


class LogUpdate(PhoneRequest):
    wamid: str = Field(min_length=1, max_length=128)
    delivery_status: str = Field(pattern=r"^(DELIVERED|FAILED|REJECTED|DOWNLOAD_FAILED)$")
    document_id: uuid.UUID | None = None
    hermes_submission_id: uuid.UUID | None = None
    outbound_wamid: str | None = Field(default=None, max_length=128)
    outbound_text: str | None = Field(default=None, max_length=4096)
    media_size_bytes: int | None = Field(default=None, ge=0, le=25 * 1024 * 1024)


@router.post(PREFIX + "/messages/finish")
async def finish_message(data: LogUpdate, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    from src.models.document import Document
    from src.models.hermes import HermesSubmission
    log = await db.scalar(select(WhatsAppMessageLog).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == data.wamid, WhatsAppMessageLog.phone_number == data.phone_number, WhatsAppMessageLog.direction == "INBOUND"))
    if not log:
        raise HTTPException(404, "Message not found")
    for value, model in ((data.document_id, Document), (data.hermes_submission_id, HermesSubmission)):
        if value and not await db.scalar(select(model.id).where(model.id == value, model.organization_id == org)):
            raise HTTPException(404, "Reference not found")
    log.delivery_status, log.document_id = data.delivery_status, data.document_id
    log.hermes_submission_id, log.media_size_bytes = data.hermes_submission_id, data.media_size_bytes
    if data.outbound_wamid:
        existing = await db.scalar(select(WhatsAppMessageLog.id).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == data.outbound_wamid))
        if not existing:
            db.add(WhatsAppMessageLog(organization_id=org, wamid=data.outbound_wamid, direction="OUTBOUND", phone_number=data.phone_number,
                message_type="TEXT", raw_text=data.outbound_text, delivery_status="DELIVERED", document_id=data.document_id))
    await db.commit()
    return {"status": "success"}


@router.post(PREFIX + "/status")
async def operational_status(data: PhoneRequest, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    sender = await active_sender(db, data.phone_number, org)
    if not sender or sender.role_in_org not in {"PROJECT_MANAGER", "FINANCE_MANAGER"}:
        raise HTTPException(403, "Operational summary permission required")
    return {
        "documents": await db.scalar(select(func.count()).select_from(Document).where(Document.organization_id == org)),
        "pending_review": await db.scalar(select(func.count()).select_from(Document).where(Document.organization_id == org, Document.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED)),
        "active_projects": await db.scalar(select(func.count()).select_from(Project).where(Project.organization_id == org, Project.project_status == ProjectStatus.ACTIVE)),
    }


async def expire_sessions(db, org):
    result = await db.execute(update(WhatsAppClarificationSession).where(WhatsAppClarificationSession.organization_id == org,
        WhatsAppClarificationSession.status == "PENDING", WhatsAppClarificationSession.expires_at <= datetime.now(timezone.utc)).values(status="EXPIRED").execution_options(synchronize_session="fetch"))
    return result.rowcount


@router.post(PREFIX + "/clarifications/expire")
async def expire_clarifications(org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    count = await expire_sessions(db, org)
    await db.commit()
    return {"expired": count}


class ClarificationReply(PhoneRequest):
    text: str = Field(max_length=4096)
    session_id: uuid.UUID | None = None


@router.post(PREFIX + "/clarifications/reply")
async def clarification_reply(data: ClarificationReply, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    sender = await active_sender(db, data.phone_number, org)
    if not sender:
        raise HTTPException(403, "Sender unavailable")
    await expire_sessions(db, org)
    query = select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.organization_id == org,
        WhatsAppClarificationSession.phone_number == data.phone_number)
    if data.session_id:
        query = query.where(WhatsAppClarificationSession.id == data.session_id)
    else:
        query = query.where(WhatsAppClarificationSession.status == "PENDING")
    sessions = (await db.scalars(query.with_for_update())).all()
    if not sessions:
        await db.commit()
        if data.session_id:
            raise HTTPException(404, "Session not found")
        return {"reply": None}
    if len(sessions) != 1:
        return {"reply": "Gunakan tombol pilihan pada pesan klarifikasi terkait."}
    session = sessions[0]
    if session.status != "PENDING":
        return {"reply": "Sesi sudah selesai atau kedaluwarsa. Silakan gunakan Review Queue SaaS."}
    if data.text not in session.options_payload:
        return {"reply": "Mohon balas angka pilihan yang sesuai pada pesan klarifikasi."}
    doc = await db.scalar(select(Document).where(Document.id == session.document_id, Document.organization_id == org).with_for_update())
    if not doc or doc.processing_status != DocumentProcessingStatus.REVIEW_REQUIRED or doc.candidate_transaction.get("converted_transaction_id"):
        raise HTTPException(409, "Document is no longer awaiting clarification")
    candidate = TransactionCandidate.model_validate(doc.candidate_transaction)
    value = session.options_payload[data.text]
    if session.question_type == "SELECT_PROJECT":
        project = await db.scalar(select(Project).where(Project.id == uuid.UUID(value), Project.organization_id == org, Project.project_status == ProjectStatus.ACTIVE))
        if not project:
            raise HTTPException(422, "Project unavailable")
        field, value = "project_id", str(project.id)
    else:
        # No arbitrary amounts, account selection or categories from chat text.
        raise HTTPException(422, "This clarification requires the SaaS Review Queue")
    old_value = doc.candidate_transaction.get(field)
    candidate.project_id = project.id
    doc.candidate_transaction = candidate.model_dump(mode="json")
    # Preserve every review flag and REVIEW_REQUIRED status for final human review.
    db.add(DocumentCorrection(organization_id=org, document_id=doc.id, field_path=field, old_value=old_value,
        new_value=value, reason="WhatsApp clarification (review still required)", corrected_by=sender.user_id))
    session.status = "ANSWERED"
    await AuditService(db).log_event(org, "Document", doc.id, "WHATSAPP_CLARIFICATION", sender.user_id,
        old_values={field: old_value}, new_values={field: value}, reason="Clarification only; approval not granted")
    await db.commit()
    return {"reply": "✅ Terima kasih, proyek berhasil diperbarui. Persetujuan tetap melalui Review Queue SaaS."}


@router.post(PREFIX + "/notifications")
async def pending_notifications(org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    await expire_sessions(db, org)
    logs = (await db.scalars(select(WhatsAppMessageLog).where(WhatsAppMessageLog.organization_id == org,
        WhatsAppMessageLog.direction == "INBOUND", WhatsAppMessageLog.document_id.is_not(None)))).all()
    notices = []
    for log in logs:
        sender = await active_sender(db, log.phone_number, org)
        if not sender:
            continue
        doc = await db.scalar(select(Document).where(Document.organization_id == org, Document.id == log.document_id))
        if not doc or doc.processing_status in {DocumentProcessingStatus.UPLOADED, DocumentProcessingStatus.HASHED, DocumentProcessingStatus.EXTRACTING, DocumentProcessingStatus.MATCHING}:
            continue
        key = "result-" + str(doc.id)
        buttons = []
        body = f"[{doc.document_code}] Hasil ekstraksi: {doc.processing_status.value}. Review dan persetujuan melalui SaaS."
        if doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED and {"PROJECT_UNKNOWN", "PROJECT_AMBIGUOUS"}.intersection(doc.review_flags):
            # Serialize session creation per sender; never associate numeric replies to two documents.
            await db.scalar(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.id == sender.id).with_for_update())
            session = await db.scalar(select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.organization_id == org,
                WhatsAppClarificationSession.document_id == doc.id, WhatsAppClarificationSession.phone_number == sender.phone_number))
            if session and session.status != "PENDING":
                continue
            if not session:
                active = await db.scalar(select(WhatsAppClarificationSession.id).where(WhatsAppClarificationSession.organization_id == org,
                    WhatsAppClarificationSession.phone_number == sender.phone_number, WhatsAppClarificationSession.status == "PENDING"))
                if active:
                    continue
                projects = (await db.scalars(select(Project).where(Project.organization_id == org, Project.project_status == ProjectStatus.ACTIVE).order_by(Project.project_code).limit(3))).all()
                if projects:
                    session = WhatsAppClarificationSession(organization_id=org, phone_number=sender.phone_number, document_id=doc.id,
                        question_type="SELECT_PROJECT", options_payload={str(i): str(project.id) for i, project in enumerate(projects, 1)})
                    db.add(session)
                    await db.flush()
            if session:
                key = "prompt-" + str(session.id)
                body = f"[{doc.document_code}] Pilih proyek untuk klarifikasi (bukan persetujuan):"
                for choice, project_id in session.options_payload.items():
                    project = await db.scalar(select(Project).where(Project.id == uuid.UUID(project_id), Project.organization_id == org))
                    if project:
                        body += f"\n{choice}: {project.project_name}"
                        buttons.append({"id": str(session.id) + ":" + choice, "title": choice})
        if not await db.scalar(select(WhatsAppMessageLog.id).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == key)):
            notices.append({"key": key, "phone_number": sender.phone_number, "document_id": str(doc.id), "body": body, "buttons": buttons})
    await db.commit()
    return {"notices": notices}


class NoticeClaim(PhoneRequest):
    key: str = Field(pattern=r"^(prompt|result)-[0-9a-f-]{36}$")
    document_id: uuid.UUID
    body: str = Field(max_length=4096)


@router.post(PREFIX + "/notifications/claim")
async def claim_notice(data: NoticeClaim, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    if not await active_sender(db, data.phone_number, org) or not await db.scalar(select(Document.id).where(Document.organization_id == org, Document.id == data.document_id)):
        raise HTTPException(404, "Notification unavailable")
    try:
        async with db.begin_nested():
            db.add(WhatsAppMessageLog(organization_id=org, wamid=data.key, direction="OUTBOUND", phone_number=data.phone_number,
                message_type="TEXT", raw_text=data.body, document_id=data.document_id, delivery_status="PROCESSING"))
            await db.flush()
    except IntegrityError:
        return {"claimed": False}
    await db.commit()
    return {"claimed": True}


class NoticeFinish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    delivered: bool


@router.post(PREFIX + "/notifications/finish")
async def finish_notice(data: NoticeFinish, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    log = await db.scalar(select(WhatsAppMessageLog).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == data.key, WhatsAppMessageLog.direction == "OUTBOUND"))
    if not log:
        raise HTTPException(404, "Notification not found")
    log.delivery_status = "DELIVERED" if data.delivered else "FAILED"
    await db.commit()
    return {"status": "success"}
