"""SaaS-owned state endpoints. Only this boundary accesses channel persistence."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.whatsapp_auth import require_adapter, require_whatsapp_machine, require_whatsapp_admin
from src.core.database import get_db
from src.models.user import User
from src.models.whatsapp import WhatsAppSenderMapping, WhatsAppMessageLog
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
