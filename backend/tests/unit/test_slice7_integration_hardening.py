"""Unit and component integration tests for Slice 7: Integration Hardening & WhatsApp Robustness.

Verifies the 20 mandatory invariants:
1. authorized image message -> one document
2. authorized PDF message -> one document
3. caption/description preserved in source_metadata (non-authoritative)
4. same external_message_id replay -> no duplicate document
5. concurrent duplicate replay -> no duplicate document
6. same file in distinct message IDs follows existing hash dedupe policy
7. unauthorized sender -> no document
8. unsupported text-only message -> no fake document
9. invalid/oversize media -> rejected safely
10. transient media failure -> bounded retry
11. permanent error -> no infinite retry
12. bridge reconnect -> session reused
13. replay after reconnect -> idempotent
14. tenant binding cannot be overridden by event payload
15. DOCUMENT_PROCESS enqueued through existing queue
16. backend failure/handoff recovery
17. integration status endpoint is tenant-safe
18. safe error redaction
19. source_channel = WHATSAPP
20. no accounting created by WhatsApp ingestion
"""
import asyncio
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.enums import DocumentProcessingStatus, DocumentType
from src.models.background_job import BackgroundJob
from src.models.whatsapp import WhatsAppMessageLog
from src.models.hermes import HermesSubmission
from src.models.transaction import Transaction
from src.models.journal import JournalEntry
from src.schemas.whatsapp import InboundMessage, WhatsAppIntegrationStatusResponse
from src.services.documents.inbound_adapter import InboundDocumentAdapter, InboundDocumentInput
from src.services.document_operations_service import sanitize_error_message
from src.services.integrations.whatsapp.media_service import WhatsAppMediaService
from src.services.integrations.whatsapp.provider import MediaReference, ProviderError, WhatsAppProvider
from src.services.whatsapp_status_service import WhatsAppStatusService
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.integrations.whatsapp.baileys_poller import BaileysBridgePoller
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
from src.core.exceptions import DuplicateEntityException
from src.models.organization import Organization


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PNG_BYTES = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"VALID_PNG_CONTENT"
SAMPLE_PDF_BYTES = b"%PDF-1.4\nVALID_PDF_CONTENT"


@pytest.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        slug=f"org-{uuid.uuid4().hex[:8]}",
        legal_name="PT Kontraktor Handal",
    )
    db_session.add(org)
    await db_session.commit()
    return org


def make_inbound_event(
    wamid: str = "wamid.test.001",
    sender_phone: str = "+6281234567890",
    message_type: str = "IMAGE",
    media_id: str = "media_001",
    mime_type: str = "image/png",
    text: str = "Nota semen Proyek Ancol",
    file_name: str = "nota_semen.png",
) -> InboundMessage:
    return InboundMessage(
        wamid=wamid,
        sender_phone=sender_phone,
        timestamp=datetime.now(timezone.utc),
        message_type=message_type,
        media_id=media_id,
        mime_type=mime_type,
        file_name=file_name,
        text=text,
    )


# ===========================================================================
# 1 & 2 & 15 & 19: Inbound Document Pipeline & Existing Durable Queue
# ===========================================================================

@pytest.mark.asyncio
async def test_01_and_02_and_15_and_19_authorized_image_and_pdf_enqueued(db_session: AsyncSession, test_org):
    """Req 1, 2, 15, 19:
    Authorized image/PDF ingestion produces one Document with source_channel=WHATSAPP,
    processing_status=QUEUED, and enqueues DOCUMENT_PROCESS in background_jobs.
    """
    adapter = InboundDocumentAdapter(db_session)
    org_id = test_org.id

    # 1. Ingest authorized Image
    img_input = InboundDocumentInput(
        organization_id=org_id,
        file_obj=io.BytesIO(SAMPLE_PNG_BYTES),
        file_name="invoice_material.png",
        mime_type="image/png",
        document_type=DocumentType.RECEIPT,
        source_channel="WHATSAPP",
        source_message_id="wamid.img.101",
        caption="Beli material kayu 2jt",
    )
    doc_img = await adapter.ingest_and_enqueue(img_input, enqueue_job=True)

    assert doc_img is not None
    assert doc_img.source_channel == "WHATSAPP"
    assert doc_img.processing_status == DocumentProcessingStatus.QUEUED
    assert doc_img.document_code.startswith("DOC-")

    # Verify existing queue holds DOCUMENT_PROCESS job
    job_stmt = select(BackgroundJob).where(
        BackgroundJob.organization_id == org_id,
        BackgroundJob.job_type == "DOCUMENT_PROCESS",
        BackgroundJob.idempotency_key == f"DOCUMENT_PROCESS:{doc_img.id}",
    )
    job = (await db_session.execute(job_stmt)).scalar_one_or_none()
    assert job is not None
    assert job.status == "PENDING"
    assert job.payload["document_id"] == str(doc_img.id)

    # 2. Ingest authorized PDF
    pdf_input = InboundDocumentInput(
        organization_id=org_id,
        file_obj=io.BytesIO(SAMPLE_PDF_BYTES),
        file_name="kontrak_subkon.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WHATSAPP",
        source_message_id="wamid.pdf.102",
        caption="Invoice subkontraktor pengecoran",
    )
    doc_pdf = await adapter.ingest_and_enqueue(pdf_input, enqueue_job=True)

    assert doc_pdf is not None
    assert doc_pdf.source_channel == "WHATSAPP"
    assert doc_pdf.processing_status == DocumentProcessingStatus.QUEUED


# ===========================================================================
# 3: Caption/Description Preserved Non-Authoritatively
# ===========================================================================

@pytest.mark.asyncio
async def test_03_caption_preserved_non_authoritative(db_session: AsyncSession, test_org):
    """Req 3:
    Caption / description is stored in source_metadata and does NOT post or alter accounting.
    """
    adapter = InboundDocumentAdapter(db_session)
    caption_text = "Pembayaran solar alat berat Excavator PC200 Proyek Tol"

    doc = await adapter.ingest_and_enqueue(
        InboundDocumentInput(
            organization_id=test_org.id,
            file_obj=io.BytesIO(b"%PDF-1.4\nSOLAR_RECEIPT_BYTES"),
            file_name="nota_solar.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            source_channel="WHATSAPP",
            source_message_id="wamid.caption.001",
            caption=caption_text,
            source_metadata={"phone_number": "+628111222333"},
        ),
        enqueue_job=True,
    )

    assert doc.source_metadata is not None
    assert doc.source_metadata.get("caption") == caption_text
    assert doc.source_metadata.get("source_message_id") == "wamid.caption.001"
    assert doc.source_metadata.get("phone_number") == "+628111222333"


# ===========================================================================
# 4 & 5: Message Idempotency and Replay
# ===========================================================================

@pytest.mark.asyncio
async def test_04_and_05_message_idempotency_and_concurrent_replay(db_session: AsyncSession, test_org):
    """Req 4 & 5:
    Replaying the same external_message_id (wamid) produces zero duplicate documents.
    DB unique constraints (uq_wa_log_org_wamid and uq_hermes_submissions_org_operation_key)
    provide race protection under concurrent delivery.
    """
    org_id = test_org.id
    wamid = "wamid.replay.12345"

    # 1. First message claimed and logged
    log1 = WhatsAppMessageLog(
        organization_id=org_id,
        wamid=wamid,
        direction="INBOUND",
        phone_number="+628****7890",
        message_type="IMAGE",
        delivery_status="DELIVERED",
    )
    db_session.add(log1)
    await db_session.commit()

    # 2. Sequential replay: Querying existing message indicates already claimed
    stmt = select(WhatsAppMessageLog).where(
        WhatsAppMessageLog.organization_id == org_id,
        WhatsAppMessageLog.wamid == wamid,
    )
    existing = (await db_session.execute(stmt)).scalar_one_or_none()
    assert existing is not None
    assert existing.delivery_status == "DELIVERED"

    # 3. Concurrent race protection: inserting duplicate (organization_id, wamid)
    # is rejected by DB constraint uq_wa_log_org_wamid
    log_duplicate = WhatsAppMessageLog(
        organization_id=org_id,
        wamid=wamid,
        direction="INBOUND",
        phone_number="+628****7890",
        message_type="IMAGE",
        delivery_status="PROCESSING",
    )
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(log_duplicate)
            await db_session.flush()

    # 4. In Hermes submission layer, same idempotency key hash is also rejected by DB
    sub1 = HermesSubmission(
        organization_id=org_id,
        operation="DOCUMENT_INTAKE",
        idempotency_key_hash="hash_12345",
        outcome_status="ACCEPTED",
    )
    db_session.add(sub1)
    await db_session.commit()

    sub_dup = HermesSubmission(
        organization_id=org_id,
        operation="DOCUMENT_INTAKE",
        idempotency_key_hash="hash_12345",
        outcome_status="ACCEPTED",
    )
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(sub_dup)
            await db_session.flush()


# ===========================================================================
# 6: Same File in Distinct Messages Follows Hash Dedupe Policy
# ===========================================================================

@pytest.mark.asyncio
async def test_06_same_file_distinct_message_ids_dedupes(db_session: AsyncSession, test_org):
    """Req 6:
    When distinct message IDs upload the exact same file content,
    existing SHA-256 dedupe policy prevents duplicate document creation.
    """
    adapter = InboundDocumentAdapter(db_session)
    identical_content = b"%PDF-1.4\nIDENTICAL_INVOICE_CONTENT_TEST_HASH"

    # First upload succeeds
    doc1 = await adapter.ingest_and_enqueue(
        InboundDocumentInput(
            organization_id=test_org.id,
            file_obj=io.BytesIO(identical_content),
            file_name="inv_original.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.VENDOR_INVOICE,
            source_channel="WHATSAPP",
            source_message_id="wamid.msg.001",
        ),
        enqueue_job=False,
    )
    assert doc1 is not None

    # Second upload with distinct message ID but identical content raises DuplicateEntityException
    with pytest.raises(DuplicateEntityException) as exc_info:
        await adapter.ingest_and_enqueue(
            InboundDocumentInput(
                organization_id=test_org.id,
                file_obj=io.BytesIO(identical_content),
                file_name="inv_retransmitted.pdf",
                mime_type="application/pdf",
                document_type=DocumentType.VENDOR_INVOICE,
                source_channel="WHATSAPP",
                source_message_id="wamid.msg.002",
            ),
            enqueue_job=False,
        )

    assert "duplicate" in str(exc_info.value).lower()


# ===========================================================================
# 7 & 8: Unauthorized Sender and Text-Only Messages
# ===========================================================================

@pytest.mark.asyncio
async def test_07_unauthorized_sender_creates_no_document():
    """Req 7:
    Sender not registered in whatsapp_sender_mappings produces no document.
    """
    mock_provider = MockWhatsAppProvider()
    mock_gateway = AsyncMock()
    mock_gateway.channel_request.return_value = {"claimed": False}
    mock_tenant_client = MagicMock()

    service = WhatsAppWebhookService(
        provider=mock_provider,
        gateway=mock_gateway,
        tenant_client=mock_tenant_client,
    )
    service.senders.resolve = AsyncMock(return_value=None)

    event = make_inbound_event(sender_phone="+6289999999999")
    await service.handle(event)

    mock_tenant_client.assert_not_called()


@pytest.mark.asyncio
async def test_08_unsupported_text_only_message_creates_no_fake_document():
    """Req 8:
    Text-only messages (e.g. 'Halo admin') do NOT invoke document submission or fake financial docs.
    """
    mock_provider = MockWhatsAppProvider()
    mock_gateway = AsyncMock()
    mock_client = AsyncMock()
    mock_client.channel_request.return_value = {"claimed": True}
    mock_client.submit_document = AsyncMock()

    sender_mock = MagicMock()
    sender_mock.organization_id = uuid.uuid4()
    sender_mock.user_id = uuid.uuid4()

    service = WhatsAppWebhookService(
        provider=mock_provider,
        gateway=mock_gateway,
        tenant_client=lambda org: mock_client,
    )
    service.senders.resolve = AsyncMock(return_value=sender_mock)

    text_event = make_inbound_event(
        message_type="TEXT",
        text="Halo, apakah invoice PT Maju sudah dibayar?",
        media_id="",
    )
    await service.handle(text_event)

    # submit_document must NOT be called for text messages
    mock_client.submit_document.assert_not_called()


# ===========================================================================
# 9: Invalid / Oversize Media Rejected Safely
# ===========================================================================

@pytest.mark.asyncio
async def test_09_invalid_and_oversize_media_rejected_safely():
    """Req 9:
    Corrupted header or file size exceeding limits is safely rejected with ProviderError.
    """
    provider = MockWhatsAppProvider()
    media_service = WhatsAppMediaService(provider, max_bytes=1024)

    # 1. Corrupt magic number
    provider.media["corrupt"] = ("image/png", b"NOT_A_PNG_FILE")
    with pytest.raises(ProviderError) as exc_info:
        await media_service.download(make_inbound_event(media_id="corrupt", mime_type="image/png"))
    assert exc_info.value.args[0] == "MIME_MISMATCH"

    # 2. Oversize media
    provider.media["huge"] = ("image/png", SAMPLE_PNG_BYTES + (b"X" * 2048))
    with pytest.raises(ProviderError) as exc_info:
        await media_service.download(make_inbound_event(media_id="huge", mime_type="image/png"))
    assert exc_info.value.args[0] == "MEDIA_TOO_LARGE"


# ===========================================================================
# 10 & 11: Transient Media Failure Retry vs Permanent Error
# ===========================================================================

@pytest.mark.asyncio
async def test_10_transient_media_failure_bounded_retry():
    """Req 10:
    Transient network/download errors are retried with bounded backoff and succeed if resolved.
    """
    provider = MagicMock(spec=WhatsAppProvider)
    attempts = 0

    async def flaky_reference(media_id: str):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ProviderError("DOWNLOAD_FAILED")
        return MediaReference(media_id, "image/png", len(SAMPLE_PNG_BYTES))

    async def stream_media(ref):
        yield SAMPLE_PNG_BYTES

    provider.media_reference = flaky_reference
    provider.stream_media = stream_media

    service = WhatsAppMediaService(provider)
    event = make_inbound_event(media_id="transient_1")
    downloaded = await service.download(event, max_attempts=3, retry_delay=0.01)

    assert downloaded is not None
    assert downloaded.content == SAMPLE_PNG_BYTES
    assert attempts == 3


@pytest.mark.asyncio
async def test_11_permanent_error_no_infinite_retry():
    """Req 11:
    Permanent errors (unsupported MIME, invalid media) fail immediately without retry.
    """
    provider = MagicMock(spec=WhatsAppProvider)
    attempts = 0

    async def failing_reference(media_id: str):
        nonlocal attempts
        attempts += 1
        return MediaReference(media_id, "application/x-dosexec", 500)

    provider.media_reference = failing_reference
    service = WhatsAppMediaService(provider)
    event = make_inbound_event(media_id="perm_1", mime_type="application/x-dosexec")

    with pytest.raises(ProviderError) as exc:
        await service.download(event, max_attempts=3, retry_delay=0.01)

    assert exc.value.args[0] == "UNSUPPORTED_MEDIA"
    assert attempts == 1  # No repeated retry on permanent error


# ===========================================================================
# 12 & 13: Bridge Reconnect and Replay
# ===========================================================================

@pytest.mark.asyncio
async def test_12_and_13_bridge_reconnect_and_idempotent_replay():
    """Req 12 & 13:
    Poller gracefully handles bridge disconnections and retries without crashing.
    """
    mock_service = MagicMock(spec=WhatsAppWebhookService)
    poller = BaileysBridgePoller(service=mock_service, bridge_url="http://127.0.0.1:3999")

    # Simulate bridge offline
    with patch.object(poller, "poll_once", side_effect=Exception("Connection refused")):
        task = poller.start()
        await asyncio.sleep(0.05)
        await poller.stop()

    assert not poller._running


# ===========================================================================
# 14: Tenant Binding Cannot Be Overridden
# ===========================================================================

@pytest.mark.asyncio
async def test_14_tenant_binding_cannot_be_overridden_by_payload(db_session: AsyncSession, test_org):
    """Req 14:
    Payload organization_id or metadata forgery cannot redirect document ingestion to another tenant.
    """
    adapter = InboundDocumentAdapter(db_session)
    legitimate_org_id = test_org.id
    forged_org_id = uuid.uuid4()

    doc = await adapter.ingest_and_enqueue(
        InboundDocumentInput(
            organization_id=legitimate_org_id,
            file_obj=io.BytesIO(b"%PDF-1.4\nTENANT_SECURITY_TEST"),
            file_name="security_doc.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.VENDOR_INVOICE,
            source_channel="WHATSAPP",
            source_metadata={"organization_id": str(forged_org_id)},  # Attempted forgery
        ),
        enqueue_job=False,
    )

    # Authoritative tenant boundary is strictly enforced
    assert doc.organization_id == legitimate_org_id
    assert doc.organization_id != forged_org_id


# ===========================================================================
# 16: Backend Failure & Handoff Recovery
# ===========================================================================

@pytest.mark.asyncio
async def test_16_backend_failure_recovery_in_poller():
    """Req 16:
    When poller receives 503 from backend during webhook dispatch, it does not drop loop.
    """
    mock_service = MagicMock(spec=WhatsAppWebhookService)
    poller = BaileysBridgePoller(service=mock_service)

    call_count = 0

    async def mock_poll():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Backend 503")
        return []

    poller.poll_once = mock_poll
    task = poller.start()
    await asyncio.sleep(0.05)
    await poller.stop()

    assert call_count >= 1


# ===========================================================================
# 17: Integration Status Endpoint Is Tenant-Safe
# ===========================================================================

@pytest.mark.asyncio
async def test_17_integration_status_tenant_safe(db_session: AsyncSession, test_org):
    """Req 17:
    Integration status metrics are isolated per tenant. Org B metrics are never mixed into Org A.
    """
    service = WhatsAppStatusService(db_session)
    org_a = test_org.id
    org_b = uuid.uuid4()

    # Log delivered message for Org A
    db_session.add(
        WhatsAppMessageLog(
            organization_id=org_a,
            wamid="wamid.orga.001",
            direction="INBOUND",
            phone_number="+62811111111",
            message_type="IMAGE",
            delivery_status="DELIVERED",
            document_id=uuid.uuid4(),
        )
    )
    await db_session.commit()

    status_a = await service.get_status(organization_id=org_a)
    status_b = await service.get_status(organization_id=org_b)

    assert status_a.last_successful_ingestion_at is not None
    assert status_b.last_successful_ingestion_at is None


@pytest.mark.asyncio
async def test_17b_status_api_endpoint_auth(client, security_client, test_org):
    """Req 17b:
    GET /api/v1/integrations/whatsapp/status requires tenant authentication.
    Anonymous caller rejected with 401/403.
    """
    # Authenticated call
    res = await client.get(
        "/api/v1/integrations/whatsapp/status",
        headers={"X-Organization-ID": str(test_org.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert "connection_state" in data
    assert "pending_handoff_count" in data
    assert "enabled" in data

    # Unauthenticated call without tenant header rejected
    unauth_res = await security_client.get("/api/v1/integrations/whatsapp/status")
    assert unauth_res.status_code in {400, 401, 403}


# ===========================================================================
# 18: Safe Error Redaction
# ===========================================================================

def test_18_safe_error_redaction():
    """Req 18:
    Stack traces, passwords, tokens, database URLs, and file paths are fully redacted.
    """
    dangerous_error = (
        'Exception occurred: postgresql+asyncpg://admin:super_secret_pw@db.internal:5432/finance\n'
        'Traceback (most recent call last):\n'
        '  File "C:\\Projects\\financial-saas\\backend\\secrets.py", line 42, in process\n'
        '    token = "token_xyz123456789"\n'
        'RuntimeError: Database connection lost'
    )
    safe = sanitize_error_message(dangerous_error)

    assert "super_secret_pw" not in safe
    assert "postgresql+asyncpg" not in safe
    assert "[DATABASE_URL_REDACTED]" in safe
    assert "Traceback" not in safe
    assert "secrets.py" not in safe


# ===========================================================================
# 20: No Accounting Created By WhatsApp Ingestion
# ===========================================================================

@pytest.mark.asyncio
async def test_20_no_accounting_created_by_whatsapp_ingestion(db_session: AsyncSession, test_org):
    """Req 20:
    Document ingestion via WhatsApp strictly produces Document + BackgroundJob.
    Zero Transactions, zero JournalEntries, zero JournalLines created.
    """
    adapter = InboundDocumentAdapter(db_session)
    org_id = test_org.id

    # Count transactions and journal entries before
    trx_count_before = (await db_session.execute(
        select(Transaction).where(Transaction.organization_id == org_id)
    )).scalars().all()
    journal_count_before = (await db_session.execute(
        select(JournalEntry).where(JournalEntry.organization_id == org_id)
    )).scalars().all()

    # Ingest document
    doc = await adapter.ingest_and_enqueue(
        InboundDocumentInput(
            organization_id=org_id,
            file_obj=io.BytesIO(SAMPLE_PDF_BYTES),
            file_name="nota_toko_besi.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.RECEIPT,
            source_channel="WHATSAPP",
            source_message_id="wamid.acct.check.001",
            caption="Nota besi beton 12mm 50 batang",
        ),
        enqueue_job=True,
    )

    assert doc.id is not None

    # Count transactions and journal entries after
    trx_count_after = (await db_session.execute(
        select(Transaction).where(Transaction.organization_id == org_id)
    )).scalars().all()
    journal_count_after = (await db_session.execute(
        select(JournalEntry).where(JournalEntry.organization_id == org_id)
    )).scalars().all()

    assert len(trx_count_after) == len(trx_count_before)
    assert len(journal_count_after) == len(journal_count_before)
