import uuid
import hashlib
import base64
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.inbox import InboxMessage, InboxAttachment, DocumentSession, MatchEvidence
from src.models.document import Document
from src.models.enums import InboxMessageStatus, SessionMatchStatus, DocumentProcessingStatus, DocumentType

from src.schemas.inbox import RemoteInboxPayload
from src.core.exceptions import DuplicateEntityException, EntityNotFoundException


class RemoteInboxService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_remote_capture(
        self,
        organization_id: uuid.UUID,
        payload: RemoteInboxPayload
    ) -> InboxMessage:
        """
        Receives captured messages from the remote capture relay.
        Ensures idempotent deduplication via external_message_id.
        Preserves raw evidence regardless of whether Finance PC is online.
        """
        # Check if already captured
        existing = await self.session.scalar(
            select(InboxMessage).where(
                InboxMessage.organization_id == organization_id,
                InboxMessage.external_message_id == payload.external_message_id
            )
        )
        if existing:
            return existing

        msg = InboxMessage(
            organization_id=organization_id,
            external_message_id=payload.external_message_id,
            sender_phone=payload.sender_phone,
            sender_name=payload.sender_name,
            caption=payload.caption,
            status=InboxMessageStatus.RECEIVED,
            received_at=payload.received_at
        )
        self.session.add(msg)
        await self.session.flush()

        # If payload carries attachment
        if payload.file_content_base64 and payload.file_name:
            file_bytes = base64.b64decode(payload.file_content_base64)
            computed_hash = hashlib.sha256(file_bytes).hexdigest()
            storage_path = f"storage/inbox/{organization_id}/{msg.id}/{payload.file_name}"

            att = InboxAttachment(
                inbox_message_id=msg.id,
                organization_id=organization_id,
                file_name=payload.file_name,
                mime_type=payload.mime_type or "application/octet-stream",
                size_bytes=len(file_bytes),
                file_hash_sha256=computed_hash,
                storage_path=storage_path
            )
            self.session.add(att)

        await self.session.flush()

        loaded_msg = await self.session.scalar(
            select(InboxMessage)
            .where(InboxMessage.id == msg.id)
            .options(selectinload(InboxMessage.attachments))
        )
        return loaded_msg

    async def sync_backlog(
        self,
        organization_id: uuid.UUID
    ) -> List[InboxMessage]:
        """
        Local Sync Worker responsibility:
        Finds all RECEIVED messages, creates tenant-isolated Documents for attachments,
        marks message as SYNCED, and establishes a DocumentSession for deferred AI analysis.
        """
        messages = (await self.session.scalars(
            select(InboxMessage)
            .where(
                InboxMessage.organization_id == organization_id,
                InboxMessage.status == InboxMessageStatus.RECEIVED
            )
            .options(selectinload(InboxMessage.attachments))
            .order_by(InboxMessage.received_at.asc())
        )).all()

        synced_list: List[InboxMessage] = []

        for msg in messages:
            for att in msg.attachments:
                # Check or create Document
                doc = await self.session.scalar(
                    select(Document).where(
                        Document.organization_id == organization_id,
                        Document.file_hash == att.file_hash_sha256
                    )
                )
                if not doc:
                    doc = Document(
                        organization_id=organization_id,
                        document_code=f"DOC-WA-{uuid.uuid4().hex[:8].upper()}",
                        document_type=DocumentType.VENDOR_INVOICE,
                        file_name=att.file_name,

                        storage_path=att.storage_path,
                        file_hash=att.file_hash_sha256,
                        file_size_bytes=att.size_bytes,
                        mime_type=att.mime_type,
                        processing_status=DocumentProcessingStatus.UPLOADED,
                        source_channel="WHATSAPP",
                        source_metadata={"caption": msg.caption, "sender_phone": msg.sender_phone}
                    )

                    self.session.add(doc)
                    await self.session.flush()

                att.document_id = doc.id

                # Create DocumentSession for deferred Hermes analysis
                session_code = f"SESS-{uuid.uuid4().hex[:8].upper()}"
                doc_session = DocumentSession(
                    organization_id=organization_id,
                    session_code=session_code,
                    status=SessionMatchStatus.PENDING,
                    inbox_message_id=msg.id,
                    document_id=doc.id,
                    notes=f"Synced from WhatsApp message {msg.external_message_id}"
                )
                self.session.add(doc_session)

            msg.status = InboxMessageStatus.SYNCED
            msg.synced_at = datetime.now(timezone.utc)
            synced_list.append(msg)

        await self.session.flush()
        return synced_list

    async def list_inbox_messages(
        self,
        organization_id: uuid.UUID,
        status_filter: Optional[InboxMessageStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[InboxMessage]:
        query = (
            select(InboxMessage)
            .where(InboxMessage.organization_id == organization_id)
            .options(selectinload(InboxMessage.attachments))
            .order_by(desc(InboxMessage.received_at))
            .limit(limit)
            .offset(offset)
        )
        if status_filter:
            query = query.where(InboxMessage.status == status_filter)

        return (await self.session.scalars(query)).all()
