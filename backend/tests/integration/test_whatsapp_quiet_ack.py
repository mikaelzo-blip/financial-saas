"""Dedicated integration tests for WhatsApp Quiet Acknowledgement and Zero Retry Spam.

Verifies:
1. One inbound IMAGE -> exactly one: "Oke, saya catat."
2. One inbound PDF -> exactly one: "Oke, saya catat."
3. Duplicate webhook / same wamid -> no second reply
4. Media download failure/retry -> no repeated chat reply (0 failure spam messages)
5. DOCUMENT_PROCESS retry / background execution -> no chat reply
6. Notification loop / polling -> 0 QUEUED or OCR status replies
"""
import time
import json
import hmac
import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from tests.integration.test_whatsapp_intake_flow import wa
from src.models import Counterparty, Document, Project, WhatsAppClarificationSession, WhatsAppMessageLog
from src.models.enums import DocumentProcessingStatus, ProjectStatus


async def send_wa_event(
    wa,
    *,
    phone=None,
    wamid="wamid.test-0001",
    msg_type="image",
    media_id="123",
    mime_type="image/png",
    file_name="receipt.png",
    caption="Nota belanja",
    text=None,
    timestamp=None,
):
    sender = (phone or wa["phones"][0]).lstrip("+")
    ts = str(timestamp or int(time.time()))
    if msg_type == "text":
        msg = {"id": wamid, "from": sender, "timestamp": ts, "type": "text", "text": {"body": text or ""}}
    elif msg_type == "document":
        msg = {
            "id": wamid,
            "from": sender,
            "timestamp": ts,
            "type": "document",
            "document": {"id": media_id, "mime_type": mime_type, "filename": file_name, "caption": caption},
        }
    else:
        msg = {
            "id": wamid,
            "from": sender,
            "timestamp": ts,
            "type": "image",
            "image": {"id": media_id, "mime_type": mime_type, "caption": caption},
        }
    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [msg]}}]}]}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"test-webhook", body, hashlib.sha256).hexdigest()
    return await wa["client"].post(
        "/api/v1/integrations/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": signature}
    )


@pytest.mark.asyncio
async def test_one_inbound_image_quiet_ack(wa, db_session):
    """One inbound image generates exactly one quiet acknowledgment ('Oke, saya catat.') upon session finalization."""
    wa["provider"].outbound.clear()
    wa["provider"].media["img-quiet-1"] = (
        "image/png",
        b"\x89PNG\r\n\x1a\n-img-content",
    )
    now = datetime.now(timezone.utc)
    response = await send_wa_event(wa, wamid="wamid.image.quiet.001", media_id="img-quiet-1", mime_type="image/png")
    assert response.status_code == 200

    # No immediate chat reply during the quiet grouping window (Section 10)
    assert len(wa["provider"].outbound) == 0

    # Finalize session after quiet window
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))

    # Exactly one outbound chat message
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."
    assert "DOC-" not in wa["provider"].outbound[0].body_text
    assert "OCR" not in wa["provider"].outbound[0].body_text
    assert "QUEUED" not in wa["provider"].outbound[0].body_text

    # Document created and logged
    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.image.quiet.001")
    )
    assert doc is not None


@pytest.mark.asyncio
async def test_one_inbound_pdf_quiet_ack(wa, db_session):
    """One inbound PDF generates exactly one quiet acknowledgment ('Oke, saya catat.') upon session finalization."""
    wa["provider"].outbound.clear()
    wa["provider"].media["pdf-quiet-1"] = (
        "application/pdf",
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
    )
    now = datetime.now(timezone.utc)
    response = await send_wa_event(
        wa,
        wamid="wamid.pdf.quiet.001",
        msg_type="document",
        media_id="pdf-quiet-1",
        mime_type="application/pdf",
        file_name="invoice_nota.pdf",
    )
    assert response.status_code == 200

    # No immediate chat reply during quiet grouping window
    assert len(wa["provider"].outbound) == 0

    # Finalize session after quiet window
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))

    # Exactly one outbound chat message
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."
    assert "DOC-" not in wa["provider"].outbound[0].body_text
    assert "OCR" not in wa["provider"].outbound[0].body_text

    # Document created
    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.pdf.quiet.001")
    )
    assert doc is not None


@pytest.mark.asyncio
async def test_duplicate_webhook_same_wamid_no_second_reply(wa, db_session):
    """Replaying the same webhook or duplicate wamid sends NO second acknowledgment."""
    wa["provider"].outbound.clear()
    wa["provider"].media["dup-wamid-1"] = (
        "image/png",
        b"\x89PNG\r\n\x1a\n-dup-wamid",
    )
    now = datetime.now(timezone.utc)

    # First delivery
    resp1 = await send_wa_event(wa, wamid="wamid.dup.test.001", media_id="dup-wamid-1", mime_type="image/png")
    assert resp1.status_code == 200
    assert len(wa["provider"].outbound) == 0

    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    # Duplicate delivery (same wamid)
    resp2 = await send_wa_event(wa, wamid="wamid.dup.test.001", media_id="dup-wamid-1", mime_type="image/png")
    assert resp2.status_code == 200

    # Running notifications again sends NO second message
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=70))
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].downloads == 1


@pytest.mark.asyncio
async def test_media_download_failure_no_repeated_chat_reply(wa, db_session):
    """Media download failure records DOWNLOAD_FAILED status and sends 0 extra failure messages (Section 12)."""
    wa["provider"].outbound.clear()
    wa["provider"].media.clear()  # No media present -> causes download failure

    response = await send_wa_event(wa, wamid="wamid.fail.media.001", media_id="missing-media", mime_type="image/png")
    assert response.status_code == 200

    # Section 12 & 34: 0 extra chat replies on failure
    assert len(wa["provider"].outbound) == 0

    # Duplicate delivery sends NO messages
    resp_dup = await send_wa_event(wa, wamid="wamid.fail.media.001", media_id="missing-media", mime_type="image/png")
    assert resp_dup.status_code == 200
    assert len(wa["provider"].outbound) == 0

    # Message log recorded as DOWNLOAD_FAILED
    log = await db_session.scalar(
        select(WhatsAppMessageLog).where(
            WhatsAppMessageLog.wamid == "wamid.fail.media.001",
            WhatsAppMessageLog.direction == "INBOUND",
        )
    )
    assert log is not None
    assert log.delivery_status == "DOWNLOAD_FAILED"


@pytest.mark.asyncio
async def test_notification_polling_zero_queue_or_ocr_status_replies(wa, db_session):
    """Notification loop does not broadcast QUEUED or REVIEW_REQUIRED status results to WhatsApp chat."""
    wa["provider"].outbound.clear()
    wa["provider"].media["notif-quiet-1"] = (
        "image/png",
        b"\x89PNG\r\n\x1a\n-notif-sample",
    )
    now = datetime.now(timezone.utc)
    await send_wa_event(wa, wamid="wamid.notif.001", media_id="notif-quiet-1", mime_type="image/png")

    # Finalize session and deliver ACK
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.notif.001")
    )
    assert doc is not None

    # Simulate document in QUEUED and then REVIEW_REQUIRED status
    doc.processing_status = DocumentProcessingStatus.QUEUED
    await db_session.commit()
    await wa["service"].deliver_pending_notifications()

    # No additional outbound message sent
    assert len(wa["provider"].outbound) == 1

    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.review_flags = ["OCR_LOW_CONFIDENCE", "PROJECT_UNKNOWN", "PROJECT_AMBIGUOUS"]
    await db_session.commit()
    await wa["service"].deliver_pending_notifications()

    # REVIEW_REQUIRED sends ZERO failure messages
    assert len(wa["provider"].outbound) == 1


@pytest.mark.asyncio
async def test_document_process_retry_and_failure_no_chat_reply(wa, db_session):
    """Permanent document processing failure remains silent in WhatsApp chat (Section 12 & 34)."""
    wa["provider"].outbound.clear()
    wa["provider"].media["fail-proc-1"] = (
        "image/png",
        b"\x89PNG\r\n\x1a\n-proc-fail",
    )
    now = datetime.now(timezone.utc)
    await send_wa_event(wa, wamid="wamid.proc.fail.001", media_id="fail-proc-1", mime_type="image/png")

    # Session finalized: 1 ACK
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.proc.fail.001")
    )
    assert doc is not None

    # Mark document as permanently FAILED (all retries exhausted)
    doc.processing_status = DocumentProcessingStatus.FAILED
    doc.error_message = "Corrupted image payload"
    await db_session.commit()

    # Notification loop runs: Section 12 specifies OCR/terminal failures send NO extra WhatsApp message
    await wa["service"].deliver_pending_notifications()

    # Total outbound messages remains exactly 1 (0 extra chat replies on failure)
    assert len(wa["provider"].outbound) == 1

    # Running notification loop again sends NO extra messages
    await wa["service"].deliver_pending_notifications()
    assert len(wa["provider"].outbound) == 1


@pytest.mark.asyncio
async def test_transient_download_failure_then_success(wa, db_session):
    """Transient download failure that succeeds sends exactly 1 ACK and 0 failure messages."""
    wa["provider"].outbound.clear()
    media_id = "transient-media-001"
    wa["provider"].media[media_id] = ("image/png", b"\x89PNG\r\n\x1a\n-transient-data")
    now = datetime.now(timezone.utc)

    # Simulate 1 transient error before success inside media service
    orig_media_reference = wa["provider"].media_reference
    call_count = 0

    async def flaky_media_reference(m_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from src.services.integrations.whatsapp.provider import ProviderError
            raise ProviderError("TEMPORARY_NETWORK_TIMEOUT")
        return await orig_media_reference(m_id)

    wa["provider"].media_reference = flaky_media_reference

    response = await send_wa_event(wa, wamid="wamid.transient.001", media_id=media_id, mime_type="image/png")
    assert response.status_code == 200

    # Retried and succeeded: deliver notifications
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."


@pytest.mark.asyncio
@pytest.mark.parametrize("caption", ["PO roll arjer", "pelunasan proyek roll arjer", "byr dp roll arjer"])
async def test_ambiguous_caption_stays_in_web_review_without_chat_clarification(wa, db_session, caption):
    """Caption is a hint only: no SELECT_PROJECT or status chat reply follows intake."""
    wa["provider"].outbound.clear()
    media_id = f"ambiguous-caption-{caption.replace(' ', '-') }"
    wa["provider"].media[media_id] = ("image/png", b"\x89PNG\r\n\x1a\n-ambiguous-caption")
    now = datetime.now(timezone.utc)

    response = await send_wa_event(
        wa,
        wamid=f"wamid.{media_id}",
        media_id=media_id,
        mime_type="image/png",
        caption=caption,
    )
    assert response.status_code == 200
    await wa["service"].deliver_pending_notifications(as_of=now + timedelta(seconds=65))
    assert [message.body_text for message in wa["provider"].outbound] == ["Oke, saya catat."]

    document = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == f"wamid.{media_id}")
    )
    assert document is not None
    customer = Counterparty(
        organization_id=document.organization_id,
        name=f"Customer {media_id}",
        is_customer=True,
    )
    db_session.add(customer)
    await db_session.flush()
    db_session.add_all(
        [
            Project(
                organization_id=document.organization_id,
                project_code=f"P-{media_id}-1",
                project_name="Roll Arjer Satu",
                customer_id=customer.id,
                start_date=date.today(),
                project_status=ProjectStatus.ACTIVE,
            ),
            Project(
                organization_id=document.organization_id,
                project_code=f"P-{media_id}-2",
                project_name="Roll Arjer Dua",
                customer_id=customer.id,
                start_date=date.today(),
                project_status=ProjectStatus.ACTIVE,
            ),
        ]
    )
    document.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    document.review_flags = ["PROJECT_AMBIGUOUS"]
    await db_session.commit()

    await wa["service"].deliver_pending_notifications()

    await db_session.refresh(document)
    assert document.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED
    assert document.review_flags == ["PROJECT_AMBIGUOUS"]
    assert await db_session.scalar(
        select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.document_id == document.id)
    ) is None
    assert [message.body_text for message in wa["provider"].outbound] == ["Oke, saya catat."]


@pytest.mark.asyncio
async def test_08_raw_whatsapp_caption_persisted(wa, db_session):
    """Test 8: Raw WhatsApp caption is persisted in both source_metadata and WhatsAppMessageLog."""
    wa["provider"].outbound.clear()
    media_id = "caption-persist-001"
    wa["provider"].media[media_id] = ("image/png", b"\x89PNG\r\n\x1a\n-caption-test-bytes")

    response = await send_wa_event(
        wa,
        wamid="wamid.caption.persist.001",
        media_id=media_id,
        mime_type="image/png",
        caption="po roll arjer",
    )
    assert response.status_code == 200

    # 1. Document source_metadata preserves raw caption & parsed hints
    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.caption.persist.001")
    )
    assert doc is not None
    assert doc.source_metadata.get("caption") == "po roll arjer"
    hints = doc.source_metadata.get("hints", {})
    assert hints.get("document_type_hint") == "PURCHASE_ORDER"
    assert hints.get("project_hint") == "roll arjer"

    # 2. WhatsAppMessageLog preserves raw_text
    log = await db_session.scalar(
        select(WhatsAppMessageLog).where(
            WhatsAppMessageLog.wamid == "wamid.caption.persist.001",
            WhatsAppMessageLog.direction == "INBOUND",
        )
    )
    assert log is not None
    assert log.raw_text == "po roll arjer"


@pytest.mark.asyncio
async def test_09_caption_available_as_classifier_and_matcher_evidence(wa, db_session):
    """Test 9: Caption is available as classifier & matcher evidence without bypassing review."""
    from src.schemas.document import StructuredExtraction
    from src.services.documents.matching import match_entities

    org = wa["orgs"][0]
    cust = Counterparty(organization_id=org.id, name="PT Arjer Utama", is_customer=True)
    db_session.add(cust)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-ROLL-ARJER",
        project_name="Roll Arjer Phase 1",
        customer_id=cust.id,
        start_date=date.today(),
        project_status=ProjectStatus.ACTIVE,
    )
    db_session.add(proj)
    await db_session.commit()

    # Matcher receives caption and hints in source_metadata
    extracted = StructuredExtraction(
        raw_text="Lampiran Pesanan Barang No 123",
        description="Pesanan Pembelian",
    )
    metadata = {
        "caption": "po roll arjer",
        "hints": {"document_type_hint": "PURCHASE_ORDER", "project_hint": "roll arjer"},
    }
    matches = await match_entities(
        db_session,
        org.id,
        extracted,
        document_type=None,
        source_metadata=metadata,
    )

    # Project was matched via CAPTION_PROJECT_HINT
    assert matches["project_id"] == str(proj.id)
    assert "CAPTION_PROJECT_HINT" in matches.get("project_method", "")


@pytest.mark.asyncio
async def test_10_caption_does_not_overwrite_ocr_document_content(wa, db_session, monkeypatch):
    """Test 10: Caption does NOT overwrite OCR text, description, line items, or amounts."""
    from decimal import Decimal
    from src.api.v1 import hermes
    from src.models.enums import DocumentType
    from src.schemas.document import ConfidenceScores, LineItem, StructuredExtraction
    from src.services.documents.extraction import ExtractionResult, ScriptedExtractionProvider
    from src.services.documents.pipeline import DocumentPipeline
    from src.services.document_service import DocumentService

    ocr_extracted = StructuredExtraction(
        invoice_number="INV-999-AUTHENTIC",
        total_amount=Decimal("12500000"),
        description="Pengadaan Semen 100 Sak",
        raw_text="FAKTUR PENJUALAN\nNo: INV-999-AUTHENTIC\nTotal: Rp 12.500.000",
        line_items=[
            LineItem(description="Semen Gresik 50kg", quantity=Decimal("100"), unit_price=Decimal("125000"), amount=Decimal("12500000"))
        ],
    )
    provider = ScriptedExtractionProvider(
        ExtractionResult(
            DocumentType.VENDOR_INVOICE,
            ocr_extracted,
            ConfidenceScores(ocr_confidence=Decimal("0.95"), document_type_confidence=Decimal("0.95"), entity_confidence=Decimal("0.0"), project_confidence=Decimal("0.0"), amount_confidence=Decimal("0.95")),
            "scripted-ocr",
            "1.0",
        )
    )

    async def process(document_id):
        doc = await db_session.get(Document, document_id)
        await DocumentPipeline(db_session, provider).process(doc, DocumentService(db_session).storage.get_file_path(doc.storage_path))
        await db_session.commit()

    monkeypatch.setattr(hermes, "process_document_background", process)

    media_id = "ocr-no-overwrite-001"
    wa["provider"].media[media_id] = ("image/png", b"\x89PNG\r\n\x1a\n-fake-invoice-bytes")

    # Inbound message with user caption "po roll arjer"
    resp = await send_wa_event(
        wa,
        wamid="wamid.ocr.no.overwrite.001",
        media_id=media_id,
        mime_type="image/png",
        caption="po roll arjer",
    )
    assert resp.status_code == 200

    doc = await db_session.scalar(
        select(Document).where(Document.source_metadata["wamid"].as_string() == "wamid.ocr.no.overwrite.001")
    )
    assert doc is not None

    # OCR extracted data is strictly preserved and not overwritten by caption
    data = doc.extracted_data
    assert data["invoice_number"] == "INV-999-AUTHENTIC"
    assert Decimal(str(data["total_amount"])) == Decimal("12500000")
    assert data["description"] == "Pengadaan Semen 100 Sak"
    assert "po roll arjer" not in (data.get("raw_text") or "")
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["description"] == "Semen Gresik 50kg"

    # OCR document type (VENDOR_INVOICE) is preserved over caption hint (PURCHASE_ORDER)
    assert doc.document_type == DocumentType.VENDOR_INVOICE

    # Caption is cleanly isolated in source_metadata
    assert doc.source_metadata["caption"] == "po roll arjer"
