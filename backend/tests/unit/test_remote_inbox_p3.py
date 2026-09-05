import uuid
import base64
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.inbox import InboxMessage, DocumentSession
from src.models.document import Document
from src.models.enums import InboxMessageStatus, SessionMatchStatus
from src.schemas.inbox import RemoteInboxPayload
from src.services.remote_inbox_service import RemoteInboxService


@pytest.mark.asyncio
async def test_remote_inbox_capture_and_local_sync(db_session: AsyncSession):
    service = RemoteInboxService(db_session)

    org = Organization(slug=f"inbox-org-{uuid.uuid4().hex[:6]}", legal_name="Remote Inbox Test PT")
    db_session.add(org)
    await db_session.flush()

    raw_pdf = b"%PDF-1.4 Fake invoice content for offline capture test"
    pdf_base64 = base64.b64encode(raw_pdf).decode("ascii")

    # Step 1: Remote Capture Relay accepts message while Finance PC is offline
    payload = RemoteInboxPayload(
        external_message_id="WAMID-OFFLINE-001",
        sender_phone="628123456789",
        sender_name="Pak Direktur",
        caption="Invoice semen proyek A tolong diproses",
        received_at=datetime.now(timezone.utc),
        file_name="invoice_semen.pdf",
        mime_type="application/pdf",
        file_content_base64=pdf_base64
    )

    msg1 = await service.ingest_remote_capture(org.id, payload)
    assert msg1.id is not None
    assert msg1.status == InboxMessageStatus.RECEIVED
    assert len(msg1.attachments) == 1
    assert msg1.attachments[0].file_name == "invoice_semen.pdf"

    # Step 2: Idempotent deduplication (relay retrying message)
    msg2 = await service.ingest_remote_capture(org.id, payload)
    assert msg2.id == msg1.id

    # Step 3: Finance PC starts up -> Local Sync Worker pulls backlog
    synced = await service.sync_backlog(org.id)
    assert len(synced) == 1
    assert synced[0].status == InboxMessageStatus.SYNCED
    assert synced[0].synced_at is not None

    # Verify Document and DocumentSession were created
    doc = await db_session.scalar(
        select(Document).where(Document.organization_id == org.id)
    )
    assert doc is not None
    assert doc.file_name == "invoice_semen.pdf"

    session = await db_session.scalar(
        select(DocumentSession).where(DocumentSession.organization_id == org.id)
    )
    assert session is not None
    assert session.status == SessionMatchStatus.PENDING
    assert session.document_id == doc.id
    assert session.inbox_message_id == msg1.id
