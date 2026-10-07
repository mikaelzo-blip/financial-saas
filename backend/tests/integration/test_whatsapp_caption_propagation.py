"""Test WhatsApp caption propagation to Document source_metadata and review queue.

Verifies:
1. User sends text caption first, then sends image -> Document source_metadata['caption'] gets user text, not '[image received]'.
2. User sends image first, then sends text caption within session window -> Document source_metadata['caption'] gets updated with user text.
3. Bridge placeholder '[image received]' is stripped and never recorded as caption.
4. Late message enrichment updates Document source_metadata['caption'] and hints.
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from src.models import Document, WhatsAppDocumentSession
from src.models.enums import DocumentProcessingStatus, DocumentType
from src.services.documents.whatsapp_session_service import WhatsAppSessionService
from src.services.integrations.whatsapp.baileys_provider import BaileysBridgeWhatsAppProvider
from src.schemas.whatsapp import InboundMessage
from tests.integration.test_whatsapp_quiet_ack import wa


@pytest.mark.asyncio
async def test_text_first_then_image_propagates_caption(wa, db_session):
    """When user sends text caption first, then image, the document gets the user's caption."""
    org_id = wa["orgs"][0].id
    phone = "+628****1111"
    t0 = datetime(2026, 9, 20, 18, 12, 30, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 20, 18, 12, 31, tzinfo=timezone.utc)

    # 1. User sends text first: 'fee po conveyor arjer'
    sess1, is_new1 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-text-1",
        message_type="TEXT",
        text="fee po conveyor arjer",
        provider_timestamp=t0,
        document_id=None,
    )
    assert is_new1 is True
    assert len(sess1.captions) == 1
    assert sess1.captions[0]["text"] == "fee po conveyor arjer"

    # 2. Document arrives 1 second later (with placeholder or empty text from bridge)
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        document_code="DOC-TEST-001",
        document_type=DocumentType.UNKNOWN,
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="hash001",
        storage_path="documents/test.jpg",
        source_channel="WHATSAPP",
        source_metadata={"wamid": "wamid-img-1", "caption": "[image received]"},
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc)
    await db_session.flush()

    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-img-1",
        message_type="IMAGE",
        text="[image received]",
        provider_timestamp=t1,
        document_id=doc_id,
    )
    assert is_new2 is False
    assert sess2.id == sess1.id

    # The placeholder '[image received]' should NOT be added to session captions
    assert len(sess2.captions) == 1
    assert sess2.captions[0]["text"] == "fee po conveyor arjer"

    # Crucial: Document source_metadata['caption'] MUST be updated from session
    await db_session.refresh(doc)
    assert doc.source_metadata.get("caption") == "fee po conveyor arjer"
    assert doc.source_metadata.get("hints", {}).get("project_hint") is not None


@pytest.mark.asyncio
async def test_image_first_then_text_updates_document_caption(wa, db_session):
    """When user sends image first, then text caption, the document gets updated with the user's caption."""
    org_id = wa["orgs"][0].id
    phone = "+628****2222"
    t0 = datetime(2026, 9, 20, 18, 15, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 9, 20, 18, 15, 10, tzinfo=timezone.utc)

    # 1. Document arrives first (no caption)
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        organization_id=org_id,
        document_code="DOC-TEST-002",
        document_type=DocumentType.UNKNOWN,
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="hash002",
        storage_path="documents/test2.jpg",
        source_channel="WHATSAPP",
        source_metadata={"wamid": "wamid-img-2"},
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc)
    await db_session.flush()

    sess1, is_new1 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-img-2",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t0,
        document_id=doc_id,
    )
    assert is_new1 is True

    # 2. User sends caption 10 seconds later: 'pembelian semen 50 sak'
    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-text-2",
        message_type="TEXT",
        text="pembelian semen 50 sak",
        provider_timestamp=t1,
        document_id=None,
    )
    assert is_new2 is False
    assert sess2.id == sess1.id

    # Crucial: Existing document in the session MUST be updated with the newly arrived caption!
    await db_session.refresh(doc)
    assert doc.source_metadata.get("caption") == "pembelian semen 50 sak"
    assert doc.source_metadata.get("hints") is not None


def test_baileys_provider_strips_image_received_placeholder():
    """BaileysBridgeWhatsAppProvider strips bridge synthetic '[image received]' placeholders."""
    provider = BaileysBridgeWhatsAppProvider()
    raw_payload = {
        "messageId": "msg-001",
        "senderId": "62812345678@s.whatsapp.net",
        "hasMedia": True,
        "mediaType": "image",
        "mediaUrls": ["/tmp/test.jpg"],
        "body": "[image received]",
        "mime": "image/jpeg",
    }
    events = provider.parse(raw_payload)
    assert len(events) == 1
    assert events[0].text == ""  # Stripped, not '[image received]'
