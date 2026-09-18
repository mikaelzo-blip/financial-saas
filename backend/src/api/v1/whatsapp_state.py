"""SaaS-owned state endpoints. Only this boundary accesses channel persistence."""
import uuid
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.whatsapp_auth import require_adapter, require_whatsapp_machine, require_whatsapp_admin
from src.core.database import get_db
from src.models.user import User
from src.models.whatsapp import WhatsAppSenderMapping, WhatsAppMessageLog, WhatsAppClarificationSession, WhatsAppDocumentSession
from src.models.document import Document, DocumentCorrection
from src.models.project import Project
from src.models.enums import DocumentProcessingStatus, ProjectStatus, CostCategory
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


class DocumentRequest(PhoneRequest):
    document_id: uuid.UUID


@router.post(PREFIX + "/documents/get")
async def channel_document(data: DocumentRequest, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    sender = await active_sender(db, data.phone_number, org)
    doc = await db.scalar(select(Document).where(Document.organization_id == org, Document.id == data.document_id))
    if not sender or not doc or (sender.role_in_org == "OPERATOR" and doc.created_by != sender.user_id):
        raise HTTPException(404, "Document unavailable")
    return {"document_id": str(doc.id), "document_code": doc.document_code, "processing_status": doc.processing_status.value}


@router.post(PREFIX + "/resolve", dependencies=[Depends(require_adapter)])
async def resolve_sender(data: PhoneRequest, db: AsyncSession = Depends(get_db)):
    mapping = await active_sender(db, data.phone_number)
    return {"sender": SenderResponse.model_validate(mapping).model_dump(mode="json") if mapping else None}


class RejectionRequest(PhoneRequest):
    wamid: str = Field(min_length=1, max_length=128)
    message_type: Literal["TEXT", "IMAGE", "DOCUMENT", "INTERACTIVE_REPLY"] = "TEXT"


@router.post(PREFIX + "/rejections/claim", dependencies=[Depends(require_adapter)])
async def claim_rejection(data: RejectionRequest, db: AsyncSession = Depends(get_db)):
    if await active_sender(db, data.phone_number):
        raise HTTPException(409, "Sender is registered")
    mapping = await db.scalar(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.phone_number == data.phone_number))
    record_id = uuid.uuid5(uuid.NAMESPACE_URL, "whatsapp-rejection:" + data.phone_number + ":" + data.wamid)
    if await db.get(WhatsAppMessageLog, record_id):
        return {"claimed": False}
    try:
        async with db.begin_nested():
            db.add(WhatsAppMessageLog(id=record_id, organization_id=mapping.organization_id if mapping else None,
                wamid=data.wamid, direction="INBOUND", phone_number=data.phone_number, message_type=data.message_type,
                delivery_status="REJECTED", error_message="UNREGISTERED_SENDER"))
            await db.flush()
    except IntegrityError:
        return {"claimed": False}
    await db.commit()
    return {"claimed": True}


class RejectionFinish(RejectionRequest):
    outbound_wamid: str = Field(min_length=1, max_length=128)
    delivered: bool


@router.post(PREFIX + "/rejections/finish", dependencies=[Depends(require_adapter)])
async def finish_rejection(data: RejectionFinish, db: AsyncSession = Depends(get_db)):
    inbound_id = uuid.uuid5(uuid.NAMESPACE_URL, "whatsapp-rejection:" + data.phone_number + ":" + data.wamid)
    inbound = await db.get(WhatsAppMessageLog, inbound_id)
    if not inbound or inbound.error_message != "UNREGISTERED_SENDER":
        raise HTTPException(404, "Rejection not found")
    record_id = uuid.uuid5(uuid.NAMESPACE_URL, "whatsapp-rejection-outbound:" + str(inbound_id))
    if not await db.get(WhatsAppMessageLog, record_id):
        db.add(WhatsAppMessageLog(id=record_id, organization_id=inbound.organization_id, wamid=data.outbound_wamid,
            direction="OUTBOUND", phone_number=data.phone_number, message_type="TEXT",
            delivery_status="DELIVERED" if data.delivered else "FAILED", error_message="UNREGISTERED_SENDER",
            raw_text="Nomor Anda belum terdaftar pada sistem keuangan. Silakan hubungi Administrator organisasi Anda."))
    await db.commit()
    return {"status": "success"}


@router.post(PREFIX + "/messages/claim")
async def claim_message(event: InboundMessage, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    if not await active_sender(db, event.sender_phone, org):
        raise HTTPException(403, "Sender unavailable")
    log = WhatsAppMessageLog(
        organization_id=org,
        wamid=event.wamid,
        direction="INBOUND",
        phone_number=event.sender_phone,
        message_type=event.message_type,
        raw_text="".join(c for c in event.text if c.isprintable() or c == "\n"),
        media_mime_type=event.mime_type,
        delivery_status="PROCESSING",
        provider_timestamp=event.timestamp,
        media_id=event.media_id,
    )
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
    outbound_status: Literal["DELIVERED", "FAILED"] = "DELIVERED"
    media_size_bytes: int | None = Field(default=None, ge=0, le=25 * 1024 * 1024)
    error_message: str | None = Field(default=None, max_length=4096)
    secondary_outbound_wamid: str | None = Field(default=None, max_length=128)
    secondary_outbound_text: str | None = Field(default=None, max_length=4096)
    secondary_outbound_status: Literal["DELIVERED", "FAILED"] = "DELIVERED"


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
    if data.error_message:
        log.error_message = data.error_message
    if data.outbound_wamid:
        existing = await db.scalar(select(WhatsAppMessageLog.id).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == data.outbound_wamid))
        if not existing:
            db.add(WhatsAppMessageLog(organization_id=org, wamid=data.outbound_wamid, direction="OUTBOUND", phone_number=data.phone_number,
                message_type="TEXT", raw_text=data.outbound_text, delivery_status=data.outbound_status, document_id=data.document_id))
    if data.secondary_outbound_wamid:
        existing_sec = await db.scalar(select(WhatsAppMessageLog.id).where(WhatsAppMessageLog.organization_id == org, WhatsAppMessageLog.wamid == data.secondary_outbound_wamid))
        if not existing_sec:
            db.add(WhatsAppMessageLog(organization_id=org, wamid=data.secondary_outbound_wamid, direction="OUTBOUND", phone_number=data.phone_number,
                message_type="TEXT", raw_text=data.secondary_outbound_text, delivery_status=data.secondary_outbound_status, document_id=data.document_id))

    # Candidate Document Session grouping & persistence (Sections 2, 3, 4, 5)
    try:
        from src.services.documents.whatsapp_session_service import WhatsAppSessionService
        msg_ts = log.provider_timestamp or log.created_at
        sess, _ = await WhatsAppSessionService.record_inbound_message(
            db=db,
            organization_id=org,
            phone_number=data.phone_number,
            wamid=data.wamid,
            message_type=log.message_type,
            text=log.raw_text,
            provider_timestamp=msg_ts,
            document_id=data.document_id,
            media_id=log.media_id,
        )
        if sess:
            log.session_id = sess.id
    except Exception:
        pass

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
    elif session.question_type == "CONFIRM_AMOUNT":
        # The user confirms an existing extraction, never types a new amount.
        try:
            amount = Decimal(value)
            evidence = Decimal(str(doc.extracted_data.get("total_amount")))
        except (InvalidOperation, TypeError):
            raise HTTPException(422, "Amount evidence unavailable") from None
        if not amount.is_finite() or amount <= 0 or amount != evidence:
            raise HTTPException(422, "Amount must match source extraction")
        field, value = "amount", str(amount)
    elif session.question_type == "SELECT_CATEGORY":
        try:
            value = CostCategory(value).value
        except ValueError:
            raise HTTPException(422, "Category unavailable") from None
        field = "cost_category"
    else:
        # No arbitrary amounts, account selection or categories from chat text.
        raise HTTPException(422, "This clarification requires the SaaS Review Queue")
    old_value = doc.candidate_transaction.get(field)
    candidate_data = candidate.model_dump(mode="json")
    candidate_data[field] = value
    doc.candidate_transaction = TransactionCandidate.model_validate(candidate_data).model_dump(mode="json")
    # Preserve every review flag and REVIEW_REQUIRED status for final human review.
    db.add(DocumentCorrection(organization_id=org, document_id=doc.id, field_path=field, old_value=old_value,
        new_value=value, reason="WhatsApp clarification (review still required)", corrected_by=sender.user_id))
    session.status = "ANSWERED"
    await AuditService(db).log_event(org, "Document", doc.id, "WHATSAPP_CLARIFICATION", sender.user_id,
        old_values={field: old_value}, new_values={field: value}, reason="Clarification only; approval not granted")
    await db.commit()
    label = {"project_id": "proyek", "amount": "nominal", "cost_category": "kategori"}[field]
    return {"reply": f"✅ Terima kasih, {label} berhasil diperbarui. Persetujuan tetap melalui Review Queue SaaS."}


class PromptRequest(DocumentRequest):
    question_type: Literal["SELECT_PROJECT", "CONFIRM_AMOUNT", "SELECT_CATEGORY"]


@router.post(PREFIX + "/clarifications/open")
async def open_clarification(data: PromptRequest, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    sender = await active_sender(db, data.phone_number, org)
    doc = await db.scalar(select(Document).where(Document.id == data.document_id, Document.organization_id == org))
    own_message = await db.scalar(select(WhatsAppMessageLog.id).where(WhatsAppMessageLog.organization_id == org,
        WhatsAppMessageLog.phone_number == data.phone_number, WhatsAppMessageLog.document_id == data.document_id, WhatsAppMessageLog.direction == "INBOUND"))
    if not sender or not doc or not own_message:
        raise HTTPException(404, "Document unavailable")
    if doc.processing_status != DocumentProcessingStatus.REVIEW_REQUIRED or doc.candidate_transaction.get("converted_transaction_id"):
        raise HTTPException(409, "Document not awaiting review")
    await db.scalar(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.id == sender.id).with_for_update())
    await expire_sessions(db, org)
    pending = await db.scalar(select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.organization_id == org,
        WhatsAppClarificationSession.phone_number == data.phone_number, WhatsAppClarificationSession.status == "PENDING"))
    if pending:
        return {"session_id": str(pending.id)}
    if data.question_type == "SELECT_PROJECT":
        projects = (await db.scalars(select(Project).where(Project.organization_id == org, Project.project_status == ProjectStatus.ACTIVE).order_by(Project.project_code).limit(3))).all()
        options = {str(i): str(project.id) for i, project in enumerate(projects, 1)}
    elif data.question_type == "SELECT_CATEGORY":
        options = {str(i): category.value for i, category in enumerate(CostCategory, 1)}
    else:
        try:
            amount = Decimal(str(doc.extracted_data.get("total_amount")))
        except InvalidOperation:
            raise HTTPException(422, "Amount evidence unavailable") from None
        if not amount.is_finite() or amount <= 0:
            raise HTTPException(422, "Amount evidence unavailable")
        options = {"1": str(amount)}
    if not options:
        raise HTTPException(409, "No safe choices available")
    session = WhatsAppClarificationSession(organization_id=org, phone_number=data.phone_number, document_id=doc.id,
        question_type=data.question_type, options_payload=options)
    db.add(session)
    await db.commit()
    return {"session_id": str(session.id)}


@router.post(PREFIX + "/notifications")
async def pending_notifications(org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    """Keep WhatsApp document intake silent after its one acknowledgement per session.

    Section 10, 11, 12:
    - Exactly one ACK ("Oke, saya catat.") per finalized candidate session.
    - Zero retry or failure spam: OCR, matching, and queue failures remain silent in chat.
    - Failures remain visible in the web SaaS.
    """
    await expire_sessions(db, org)
    from src.services.documents.whatsapp_session_service import WhatsAppSessionService
    await WhatsAppSessionService.finalize_expired_sessions(db, org)

    notices = []
    sessions_to_ack = await WhatsAppSessionService.get_sessions_needing_ack(db, org)
    for sess in sessions_to_ack:
        sender = await active_sender(db, sess.phone_number, org)
        if not sender:
            continue
        key = f"session-ack-{sess.id}"
        existing = await db.scalar(select(WhatsAppMessageLog).where(
            WhatsAppMessageLog.organization_id == org,
            WhatsAppMessageLog.wamid == key,
            WhatsAppMessageLog.direction == "OUTBOUND",
        ))
        if existing:
            if existing.delivery_status == "DELIVERED":
                continue
            if existing.delivery_status == "PROCESSING":
                log_time = existing.created_at
                if log_time.tzinfo is None:
                    log_time = log_time.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - log_time).total_seconds() < 30.0:
                    continue
        first_doc_id = sess.document_ids[0] if sess.document_ids else None
        notices.append({
            "key": key,
            "phone_number": sess.phone_number,
            "document_id": first_doc_id,
            "body": "Oke, saya catat.",
            "buttons": [],
        })

    await db.commit()
    return {"notices": notices}


class NoticeClaim(PhoneRequest):
    key: str = Field(pattern=r"^(prompt|result|session-ack)-[0-9a-f-]{36}$")
    document_id: uuid.UUID | None = None
    body: str = Field(max_length=4096)


@router.post(PREFIX + "/notifications/claim")
async def claim_notice(data: NoticeClaim, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    if not await active_sender(db, data.phone_number, org):
        raise HTTPException(404, "Notification unavailable")
    if data.document_id and not await db.scalar(select(Document.id).where(Document.organization_id == org, Document.id == data.document_id)):
        raise HTTPException(404, "Notification unavailable")

    now = datetime.now(timezone.utc)

    if data.key.startswith("session-ack-"):
        from src.services.documents.whatsapp_session_service import WhatsAppSessionService
        session_id = uuid.UUID(data.key.replace("session-ack-", ""))
        sess = await db.scalar(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.id == session_id,
                WhatsAppDocumentSession.organization_id == org,
            ).with_for_update()
        )
        if not sess:
            raise HTTPException(404, "Session not found")
        if sess.ack_sent_at is not None:
            return {"claimed": False}

        existing_log = await db.scalar(
            select(WhatsAppMessageLog).where(
                WhatsAppMessageLog.organization_id == org,
                WhatsAppMessageLog.wamid == data.key,
                WhatsAppMessageLog.direction == "OUTBOUND",
            ).with_for_update()
        )
        if existing_log:
            if existing_log.delivery_status == "DELIVERED":
                sess.ack_sent_at = existing_log.created_at
                sess.ack_wamid = data.key
                meta = dict(sess.session_metadata or {})
                meta["ack_status"] = "SENT_CONFIRMED"
                sess.session_metadata = meta
                await db.commit()
                return {"claimed": False}
            elif existing_log.delivery_status == "PROCESSING":
                log_time = existing_log.created_at
                if log_time.tzinfo is None:
                    log_time = log_time.replace(tzinfo=timezone.utc)
                if (now - log_time).total_seconds() < 30.0:
                    return {"claimed": False}
                existing_log.created_at = now
                existing_log.delivery_status = "PROCESSING"
                existing_log.error_message = None
            else:
                existing_log.created_at = now
                existing_log.delivery_status = "PROCESSING"
                existing_log.error_message = None
        else:
            db.add(WhatsAppMessageLog(
                organization_id=org,
                wamid=data.key,
                direction="OUTBOUND",
                phone_number=data.phone_number,
                message_type="TEXT",
                raw_text=data.body,
                delivery_status="PROCESSING",
                document_id=data.document_id,
            ))

        await WhatsAppSessionService.mark_session_ack_claimed(db, org, session_id, data.key, claimed_at=now)
        await db.commit()
        return {"claimed": True}

    try:
        async with db.begin_nested():
            db.add(WhatsAppMessageLog(organization_id=org, wamid=data.key, direction="OUTBOUND", phone_number=data.phone_number,
                message_type="TEXT", raw_text=data.body, document_id=data.document_id, delivery_status="PROCESSING"))
            await db.flush()
    except IntegrityError:
        return {"claimed": False}

    await db.commit()
    return {"claimed": True}


class FinalizeSessionsRequest(BaseModel):
    as_of: Optional[datetime] = None


@router.post(PREFIX + "/sessions/finalize")
async def finalize_sessions_endpoint(
    data: Optional[FinalizeSessionsRequest] = None,
    org: uuid.UUID = Depends(require_whatsapp_machine),
    db: AsyncSession = Depends(get_db),
):
    from src.services.documents.whatsapp_session_service import WhatsAppSessionService
    as_of = data.as_of if data else None
    finalized = await WhatsAppSessionService.finalize_expired_sessions(db, org, as_of=as_of)
    await db.commit()
    return {"finalized_count": len(finalized), "session_ids": [str(s.id) for s in finalized]}


class ReconstructBacklogRequest(BaseModel):
    messages: List[Dict[str, Any]]
    as_of: Optional[datetime] = None


@router.post(PREFIX + "/sessions/reconstruct_backlog")
async def reconstruct_backlog_endpoint(
    data: ReconstructBacklogRequest,
    org: uuid.UUID = Depends(require_whatsapp_machine),
    db: AsyncSession = Depends(get_db),
):
    from src.services.documents.whatsapp_session_service import WhatsAppSessionService
    sessions = await WhatsAppSessionService.reconstruct_backlog(
        db=db,
        organization_id=org,
        messages=data.messages,
        as_of=data.as_of,
    )
    await db.commit()
    return {
        "reconstructed_session_count": len(sessions),
        "sessions": [
            {
                "session_id": str(s.id),
                "session_code": s.session_code,
                "phone_number": s.phone_number,
                "document_count": len(s.document_ids),
                "message_count": len(s.message_wamids),
                "first_message_at": s.first_message_at.isoformat(),
                "last_message_at": s.last_message_at.isoformat(),
            }
            for s in sessions
        ],
    }


class NoticeFinish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    delivered: bool
    outbound_wamid: Optional[str] = None
    error_message: Optional[str] = None


@router.post(PREFIX + "/notifications/finish")
async def finish_notice(data: NoticeFinish, org: uuid.UUID = Depends(require_whatsapp_machine), db: AsyncSession = Depends(get_db)):
    log = await db.scalar(select(WhatsAppMessageLog).where(
        WhatsAppMessageLog.organization_id == org,
        WhatsAppMessageLog.wamid == data.key,
        WhatsAppMessageLog.direction == "OUTBOUND",
    ).with_for_update())
    if not log:
        raise HTTPException(404, "Notification not found")

    now = datetime.now(timezone.utc)
    if data.delivered:
        log.delivery_status = "DELIVERED"
        if data.key.startswith("session-ack-"):
            from src.services.documents.whatsapp_session_service import WhatsAppSessionService
            session_id = uuid.UUID(data.key.replace("session-ack-", ""))
            await WhatsAppSessionService.mark_session_ack_confirmed(
                db, org, session_id, wamid=data.outbound_wamid or data.key, sent_at=now
            )
    else:
        log.delivery_status = "FAILED"
        if data.error_message:
            log.error_message = data.error_message
        if data.key.startswith("session-ack-"):
            from src.services.documents.whatsapp_session_service import WhatsAppSessionService
            session_id = uuid.UUID(data.key.replace("session-ack-", ""))
            await WhatsAppSessionService.mark_session_ack_failed(
                db, org, session_id, error_message=data.error_message
            )

    await db.commit()
    return {"status": "success"}
