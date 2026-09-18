import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select

from src.models.whatsapp import WhatsAppDocumentSession, WhatsAppSenderMapping, WhatsAppMessageLog
from src.models.document import Document
from src.models.enums import DocumentProcessingStatus, DocumentType
from src.services.documents.whatsapp_session_service import WhatsAppSessionService
from tests.integration.test_whatsapp_quiet_ack import wa, send_wa_event


@pytest.mark.asyncio
async def test_online_grouping_invoice_and_transfer(wa, db_session):
    """Section 26 Test A: Invoice at t=0, transfer at t=20 -> same candidate session."""
    org_id = wa["orgs"][0].id
    phone = "+628120000001"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t20 = t0 + timedelta(seconds=20)

    # Message 1: Invoice
    sess1, is_new1 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-inv-1",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    assert is_new1 is True
    assert sess1.status == "OPEN"
    assert len(sess1.document_ids) == 1

    # Message 2: Transfer 20s later
    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-tr-1",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t20,
        document_id=uuid.uuid4(),
    )
    assert is_new2 is False
    assert sess2.id == sess1.id
    assert len(sess2.document_ids) == 2
    assert sess2.last_message_at == t20


@pytest.mark.asyncio
async def test_online_grouping_caption_within_window(wa, db_session):
    """Section 26 Test B: Invoice at t=0, caption at t=50 -> same candidate session."""
    org_id = wa["orgs"][0].id
    phone = "+628120000002"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t50 = t0 + timedelta(seconds=50)

    # Message 1: Invoice
    sess1, is_new1 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-inv-2",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    assert is_new1 is True

    # Message 2: Caption at t=50
    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-cap-2",
        message_type="TEXT",
        text="Pembelian semen untuk proyek Ancol",
        provider_timestamp=t50,
        document_id=None,
    )
    assert is_new2 is False
    assert sess2.id == sess1.id
    assert len(sess2.captions) == 1
    assert "Ancol" in sess2.captions[0]["text"]


@pytest.mark.asyncio
async def test_sliding_window_capped_by_hard_maximum(wa, db_session):
    """Section 26 Test C: New messages extend quiet window, but cannot exceed hard max (120s)."""
    org_id = wa["orgs"][0].id
    phone = "+628120000003"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t50 = t0 + timedelta(seconds=50)
    t100 = t0 + timedelta(seconds=100)
    t130 = t0 + timedelta(seconds=130)

    # t=0: first message. Hard max is t=120.
    sess1, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m1", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    assert sess1.hard_max_at == t0 + timedelta(seconds=120)
    assert sess1.window_expires_at == t0 + timedelta(seconds=60)

    # t=50: extends quiet window to min(t50+60s=t110s, hard_max=t120s) -> t110s
    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m2", message_type="IMAGE", text=None, provider_timestamp=t50,
        document_id=uuid.uuid4(),
    )
    assert is_new2 is False
    assert sess2.window_expires_at == t50 + timedelta(seconds=60)

    # t=100: extends quiet window to min(t100+60s=t160s, hard_max=t120s) -> capped at t120s!
    sess3, is_new3 = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m3", message_type="IMAGE", text=None, provider_timestamp=t100,
        document_id=uuid.uuid4(),
    )
    assert is_new3 is False
    assert sess3.window_expires_at == sess1.hard_max_at

    # t=130: exceeds hard max (120s) -> old session is FINALIZED, new session created!
    sess4, is_new4 = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m4", message_type="IMAGE", text=None, provider_timestamp=t130,
        document_id=uuid.uuid4(),
    )
    assert is_new4 is True
    assert sess4.id != sess1.id
    assert sess1.status == "FINALIZED"
    assert sess4.status == "OPEN"


@pytest.mark.asyncio
async def test_different_senders_never_same_session(wa, db_session):
    """Section 26 Test D: Different senders -> never same session."""
    org_id = wa["orgs"][0].id
    phone_a = "+628120000004"
    phone_b = "+628120000005"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)

    sess_a, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone_a,
        wamid="m-a", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    sess_b, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone_b,
        wamid="m-b", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    assert sess_a.id != sess_b.id
    assert sess_a.phone_number == phone_a
    assert sess_b.phone_number == phone_b


@pytest.mark.asyncio
async def test_same_sender_gap_exceeded_creates_new_session(wa, db_session):
    """Section 26 Test E: Same sender, gap > 60s -> different candidate sessions."""
    org_id = wa["orgs"][0].id
    phone = "+628120000006"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t75 = t0 + timedelta(seconds=75)

    sess1, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m-1", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )

    sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m-2", message_type="IMAGE", text=None, provider_timestamp=t75,
        document_id=uuid.uuid4(),
    )
    assert is_new2 is True
    assert sess2.id != sess1.id
    assert sess1.status == "FINALIZED"
    assert sess2.status == "OPEN"


@pytest.mark.asyncio
async def test_offline_backlog_reconstruction_by_provider_timestamp(wa, db_session):
    """Section 27: Offline backlog reconstructs into candidate sessions using original timestamps,
    NOT local ingestion time.
    Batch:
    - 10:01:00 Invoice A
    - 10:01:20 Transfer A
    - 10:04:00 Invoice B
    - 10:04:30 Transfer B
    Reconstructs into 2 distinct candidate sessions.
    """
    org_id = wa["orgs"][0].id
    phone = "+628120000007"

    t1_1 = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)
    t1_2 = datetime(2026, 9, 18, 10, 1, 20, tzinfo=timezone.utc)
    t2_1 = datetime(2026, 9, 18, 10, 4, 0, tzinfo=timezone.utc)
    t2_2 = datetime(2026, 9, 18, 10, 4, 30, tzinfo=timezone.utc)

    # Intentionally scrambled arrival order to prove reconstruction uses provider_timestamp
    messages = [
        {"phone_number": phone, "wamid": "w4", "message_type": "IMAGE", "timestamp": t2_2.isoformat(), "document_id": str(uuid.uuid4())},
        {"phone_number": phone, "wamid": "w1", "message_type": "IMAGE", "timestamp": t1_1.isoformat(), "document_id": str(uuid.uuid4())},
        {"phone_number": phone, "wamid": "w3", "message_type": "IMAGE", "timestamp": t2_1.isoformat(), "document_id": str(uuid.uuid4())},
        {"phone_number": phone, "wamid": "w2", "message_type": "IMAGE", "timestamp": t1_2.isoformat(), "document_id": str(uuid.uuid4())},
    ]

    sessions = await WhatsAppSessionService.reconstruct_backlog(
        db=db_session,
        organization_id=org_id,
        messages=messages,
        as_of=datetime(2026, 9, 18, 10, 30, 0, tzinfo=timezone.utc),
    )

    assert len(sessions) == 2
    sess_first = min(sessions, key=lambda s: s.first_message_at)
    sess_second = max(sessions, key=lambda s: s.first_message_at)

    assert len(sess_first.document_ids) == 2
    assert sess_first.first_message_at == t1_1
    assert sess_first.last_message_at == t1_2

    assert len(sess_second.document_ids) == 2
    assert sess_second.first_message_at == t2_1
    assert sess_second.last_message_at == t2_2


@pytest.mark.asyncio
async def test_session_ack_idempotency_and_no_duplicates(wa, db_session):
    """Sections 10 & 11: Exactly one ACK per finalized candidate session.
    Retries must NOT duplicate ACKs.
    """
    org_id = wa["orgs"][0].id
    phone = "+628120000008"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)

    sess, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="msg-ack-test", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )

    # Advance clock past quiet window (t0 + 65s)
    finalized = await WhatsAppSessionService.finalize_expired_sessions(
        db=db_session, organization_id=org_id, as_of=t0 + timedelta(seconds=65)
    )
    assert len(finalized) == 1
    assert finalized[0].id == sess.id
    assert finalized[0].status == "FINALIZED"
    assert finalized[0].ack_sent_at is None

    # Check sessions needing ACK
    needing_ack = await WhatsAppSessionService.get_sessions_needing_ack(db=db_session, organization_id=org_id)
    assert len(needing_ack) == 1

    # Mark ACK sent
    await WhatsAppSessionService.mark_session_ack_sent(
        db=db_session,
        organization_id=org_id,
        session_id=sess.id,
        wamid="ack-wamid-001",
    )

    # Second check for sessions needing ACK -> MUST be 0!
    needing_ack_again = await WhatsAppSessionService.get_sessions_needing_ack(db=db_session, organization_id=org_id)
    assert len(needing_ack_again) == 0


@pytest.mark.asyncio
async def test_late_message_enrichment_unapproved_vs_approved(wa, db_session):
    """Section 22:
    - If unapproved: allow session enrichment with late project hint.
    - If already approved/posted: preserve original accounting state and record in audit log.
    """
    org_id = wa["orgs"][0].id
    phone = "+628120000009"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t180 = t0 + timedelta(seconds=180)  # 3 minutes later

    # Create session with document
    doc = Document(
        organization_id=org_id,
        document_code=f"DOC-{uuid.uuid4().hex[:6]}",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="test.png",
        storage_path="uploads/test.png",
        file_size_bytes=100,
        mime_type="image/png",
        file_hash=uuid.uuid4().hex,
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        source_metadata={},
    )
    db_session.add(doc)
    await db_session.flush()

    sess, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m-doc", message_type="IMAGE", text=None, provider_timestamp=t0,
        document_id=doc.id,
    )

    # Finalize session
    await WhatsAppSessionService.finalize_expired_sessions(
        db=db_session, organization_id=org_id, as_of=t0 + timedelta(seconds=70)
    )

    # 1. Unapproved document: late caption "Untuk proyek Ancol"
    enriched_sess, status = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m-late-caption", message_type="TEXT", text="Untuk proyek Ancol",
        provider_timestamp=t180,
    )
    assert status is False  # Enriched existing session, did not create new
    assert enriched_sess.id == sess.id
    assert any("Ancol" in c.get("text", "") for c in enriched_sess.captions)

    # 2. Approved document: late caption must NOT rewrite accounting state
    doc.processing_status = DocumentProcessingStatus.POSTED
    await db_session.flush()

    sess_after_posted, status2 = await WhatsAppSessionService.record_inbound_message(
        db=db_session, organization_id=org_id, phone_number=phone,
        wamid="m-late-caption-2", message_type="TEXT", text="Koreksi proyek Sudirman",
        provider_timestamp=t180 + timedelta(seconds=10),
    )
    # Status is preserved as POSTED, not silently overwritten
    assert doc.processing_status == DocumentProcessingStatus.POSTED
    assert "late_message_audit" in (doc.source_metadata or {})


@pytest.mark.asyncio
async def test_crash_recovery_overdue_session_finalization_on_restart(wa, db_session):
    """Section 5: Crash recovery scenario.
    t=0 invoice received
    t=20 transfer received
    t=30 application crashes (in-memory timers lost)
    t=100 application restarts
    Expected:
    - Session discovered as overdue from PostgreSQL state
    - Session finalizes
    - ACK is sent at most once
    - No session remains permanently OPEN
    """
    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    t20 = t0 + timedelta(seconds=20)
    t100 = t0 + timedelta(seconds=100)

    doc1 = Document(
        id=uuid.uuid4(),
        organization_id=org_id,
        document_code=f"DOC-{uuid.uuid4().hex[:6]}",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="inv.png",
        storage_path="uploads/inv.png",
        file_size_bytes=100,
        mime_type="image/png",
        file_hash=uuid.uuid4().hex,
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        source_metadata={},
    )
    doc2 = Document(
        id=uuid.uuid4(),
        organization_id=org_id,
        document_code=f"DOC-{uuid.uuid4().hex[:6]}",
        document_type=DocumentType.TRANSFER_PROOF,
        file_name="tr.png",
        storage_path="uploads/tr.png",
        file_size_bytes=100,
        mime_type="image/png",
        file_hash=uuid.uuid4().hex,
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        source_metadata={},
    )
    db_session.add_all([doc1, doc2])
    await db_session.flush()

    # t=0: invoice received
    sess, is_new = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="crash-test-inv",
        message_type="IMAGE",
        text="Invoice supplier material",
        provider_timestamp=t0,
        document_id=doc1.id,
    )
    assert is_new is True
    assert sess.status == "OPEN"

    # t=20: transfer received
    sess, is_new = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="crash-test-tr",
        message_type="IMAGE",
        text="Bukti transfer lunas",
        provider_timestamp=t20,
        document_id=doc2.id,
    )
    assert is_new is False
    assert sess.status == "OPEN"
    # Quiet deadline is t20 + 60s = t80
    assert sess.window_expires_at == t20 + timedelta(seconds=60)
    await db_session.commit()

    # t=30: Application crashes!
    # In-memory asyncio timers are gone.
    # Verify DB still has OPEN session
    open_in_db = await WhatsAppSessionService.get_open_session(db_session, org_id, phone)
    assert open_in_db is not None
    assert open_in_db.status == "OPEN"

    # t=100: Application restarts / worker cycle runs
    # deliver_pending_notifications is called with as_of=t100
    wa["provider"].outbound.clear()
    await wa["service"].deliver_pending_notifications(as_of=t100)

    # Overdue session was discovered and finalized from persistent PostgreSQL state
    await db_session.refresh(open_in_db)
    assert open_in_db.status == "FINALIZED"

    # Exactly one ACK sent
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    # Subsequent restart or poll at t=120 sends NO second ACK
    await wa["service"].deliver_pending_notifications(as_of=t0 + timedelta(seconds=120))
    assert len(wa["provider"].outbound) == 1


@pytest.mark.asyncio
async def test_ack_idempotency_restart_after_ack_and_crash_boundary(wa, db_session):
    """Section 6: ACK Idempotency across crash boundaries.
    Case A: session finalizes, ACK persisted as sent, process restarts -> no second ACK.
    Case B: session finalizes, process crashes, restart safely resolves ACK.
    Case C: duplicate calls never exceed 1 ACK per session.
    """
    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)

    doc = Document(
        id=uuid.uuid4(),
        organization_id=org_id,
        document_code=f"DOC-{uuid.uuid4().hex[:6]}",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="inv.png",
        storage_path="uploads/inv.png",
        file_size_bytes=100,
        mime_type="image/png",
        file_hash=uuid.uuid4().hex,
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        source_metadata={},
    )
    db_session.add(doc)
    await db_session.flush()

    # Ingest document
    sess, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="ack-crash-wamid-1",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t0,
        document_id=doc.id,
    )
    await db_session.commit()

    # Finalize session
    wa["provider"].outbound.clear()
    await wa["service"].deliver_pending_notifications(as_of=t0 + timedelta(seconds=65))
    assert len(wa["provider"].outbound) == 1

    # Simulate process restart: fresh deliver_pending_notifications
    await wa["service"].deliver_pending_notifications(as_of=t0 + timedelta(seconds=70))
    await wa["service"].deliver_pending_notifications(as_of=t0 + timedelta(seconds=150))
    # Exactly one ACK maximum across entire lifecycle
    assert len(wa["provider"].outbound) == 1


@pytest.mark.asyncio
async def test_tenant_safety_session_isolation(wa, db_session):
    """Section 12: Tenant isolation.
    A session belonging to Tenant A is never accessible, finalizable, or acknowledged by Tenant B.
    """
    org_a = wa["orgs"][0].id
    org_b = wa["orgs"][1].id
    phone = "+628****0012"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)

    # Create session in Tenant A
    sess_a, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_a,
        phone_number=phone,
        wamid="wamid-tenant-a",
        message_type="IMAGE",
        text=None,
        provider_timestamp=t0,
        document_id=uuid.uuid4(),
    )
    await db_session.commit()

    # Tenant B tries to get open session for this phone -> returns None
    sess_b = await WhatsAppSessionService.get_open_session(db_session, org_b, phone)
    assert sess_b is None

    # Tenant B finalization cycle does NOT touch Tenant A's session
    finalized_b = await WhatsAppSessionService.finalize_expired_sessions(
        db_session, org_b, as_of=t0 + timedelta(seconds=70)
    )
    assert len(finalized_b) == 0

    # Tenant B cannot mark Tenant A's session acknowledgement state.
    marked_by_b = await WhatsAppSessionService.mark_session_ack_sent(
        db_session,
        organization_id=org_b,
        session_id=sess_a.id,
        wamid="session-ack-foreign",
    )
    assert marked_by_b is False

    # Session in Tenant A remains untouched by Tenant B
    await db_session.refresh(sess_a)
    assert sess_a.status == "OPEN"
    assert sess_a.ack_sent_at is None

    # Tenant A finalizes its own session safely
    finalized_a = await WhatsAppSessionService.finalize_expired_sessions(
        db_session, org_a, as_of=t0 + timedelta(seconds=70)
    )
    assert len(finalized_a) == 1
    assert finalized_a[0].id == sess_a.id


@pytest.mark.asyncio
async def test_session_finalization_idempotency_repeated_calls(wa, db_session):
    """Section 10: Calling finalize multiple times is safe and idempotent.
    Expected:
    - 1 final session state
    - 1 ACK maximum
    - No duplicate documents or candidate corruption
    """
    org_id = wa["orgs"][0].id
    phone = "+628****0013"
    t0 = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
    doc_id = uuid.uuid4()

    sess, _ = await WhatsAppSessionService.record_inbound_message(
        db=db_session,
        organization_id=org_id,
        phone_number=phone,
        wamid="wamid-idem-1",
        message_type="IMAGE",
        text="Nota material",
        provider_timestamp=t0,
        document_id=doc_id,
    )
    await db_session.commit()

    # Call finalize 3 times with same or later as_of
    f1 = await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=t0 + timedelta(seconds=65))
    f2 = await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=t0 + timedelta(seconds=70))
    f3 = await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=t0 + timedelta(seconds=100))

    assert len(f1) == 1
    assert len(f2) == 0  # Already finalized
    assert len(f3) == 0  # Already finalized

    await db_session.refresh(sess)
    assert sess.status == "FINALIZED"
    assert sess.document_ids == [str(doc_id)]


@pytest.mark.asyncio
async def test_backlog_batch_race_prevents_premature_historical_finalization(wa, db_session):
    """Section 10: Backlog batch race test.
    Historical timestamps:
    10:01:00 invoice A
    10:01:20 transfer A
    Both ingested locally much later (e.g. 12:00:00).
    Force overdue scanner opportunity between logical message operations.

    Expected:
    - Same session
    - One finalized session
    - One ACK maximum
    - No premature finalization
    """
    org_id = wa["orgs"][0].id
    phone = "+628****0014"
    t_inv = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)
    t_tr = datetime(2026, 9, 18, 10, 1, 20, tzinfo=timezone.utc)
    t_local = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()

    # Enter explicit batch boundary for this sender
    async with WhatsAppSessionService.batch_scope(org_id, [phone]):
        # Message 1 arrives
        sess1, is_new1 = await WhatsAppSessionService.record_inbound_message(
            db=db_session,
            organization_id=org_id,
            phone_number=phone,
            wamid="wamid-batch-inv",
            message_type="IMAGE",
            text=None,
            provider_timestamp=t_inv,
            document_id=doc_a,
            as_of=t_local,
        )
        assert is_new1 is True

        # Interleaved overdue scanner runs between message operations!
        # Because batch boundary is active, it must NOT prematurely finalize historical session
        finalized_mid = await WhatsAppSessionService.finalize_expired_sessions(
            db_session, org_id, as_of=t_local + timedelta(seconds=5)
        )
        assert len(finalized_mid) == 0, "Premature finalization occurred during active batch!"

        # Message 2 arrives
        sess2, is_new2 = await WhatsAppSessionService.record_inbound_message(
            db=db_session,
            organization_id=org_id,
            phone_number=phone,
            wamid="wamid-batch-tr",
            message_type="IMAGE",
            text=None,
            provider_timestamp=t_tr,
            document_id=doc_b,
            as_of=t_local + timedelta(seconds=1),
        )
        assert is_new2 is False, "Transfer A should attach to existing session, not create new!"
        assert sess2.id == sess1.id

    # After batch scope completes, evaluate overdue sessions
    finalized_after = await WhatsAppSessionService.finalize_expired_sessions(
        db_session, org_id, as_of=t_local + timedelta(seconds=10)
    )
    assert len(finalized_after) == 1
    assert finalized_after[0].id == sess1.id

    # Check ACK count
    acks_needing = await WhatsAppSessionService.get_sessions_needing_ack(db_session, org_id)
    session_acks = [s for s in acks_needing if s.id == sess1.id]
    assert len(session_acks) == 1


@pytest.mark.asyncio
async def test_backlog_batch_two_pairs_creates_two_sessions_and_two_acks(wa, db_session):
    """Section 10: Backlog batch containing 2 separate transaction pairs:
    10:01 invoice A
    10:01:20 transfer A
    10:04 invoice B
    10:04:20 transfer B

    Expected:
    - 2 sessions
    - 2 ACK maximum (not 4)
    """
    org_id = wa["orgs"][0].id
    phone = "+628****0015"
    t1 = datetime(2026, 9, 18, 10, 1, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 18, 10, 1, 20, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 18, 10, 4, 0, tzinfo=timezone.utc)
    t4 = datetime(2026, 9, 18, 10, 4, 20, tzinfo=timezone.utc)
    t_local = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)

    d1, d2, d3, d4 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async with WhatsAppSessionService.batch_scope(org_id, [phone]):
        # Pair 1: invoice A + transfer A
        s1, is_new1 = await WhatsAppSessionService.record_inbound_message(
            db=db_session, organization_id=org_id, phone_number=phone,
            wamid="m1", message_type="IMAGE", text=None, provider_timestamp=t1,
            document_id=d1, as_of=t_local,
        )
        # Interleaved scanner
        await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=t_local)

        s2, is_new2 = await WhatsAppSessionService.record_inbound_message(
            db=db_session, organization_id=org_id, phone_number=phone,
            wamid="m2", message_type="IMAGE", text=None, provider_timestamp=t2,
            document_id=d2, as_of=t_local,
        )
        assert is_new1 is True
        assert is_new2 is False
        assert s1.id == s2.id

        # Pair 2: invoice B (gap > 120s from pair 1) + transfer B
        s3, is_new3 = await WhatsAppSessionService.record_inbound_message(
            db=db_session, organization_id=org_id, phone_number=phone,
            wamid="m3", message_type="IMAGE", text=None, provider_timestamp=t3,
            document_id=d3, as_of=t_local,
        )
        # Interleaved scanner
        await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=t_local)

        s4, is_new4 = await WhatsAppSessionService.record_inbound_message(
            db=db_session, organization_id=org_id, phone_number=phone,
            wamid="m4", message_type="IMAGE", text=None, provider_timestamp=t4,
            document_id=d4, as_of=t_local,
        )
        assert is_new3 is True
        assert is_new4 is False
        assert s3.id == s4.id
        assert s3.id != s1.id

    # Batch scope finished: evaluate overdue sessions
    finalized = await WhatsAppSessionService.finalize_expired_sessions(
        db_session, org_id, as_of=t_local + timedelta(seconds=10)
    )
    finalized_ids = {s.id for s in finalized}
    assert s1.id in finalized_ids or s1.status == "FINALIZED"
    assert s3.id in finalized_ids or s3.status == "FINALIZED"

    # Verify total session count and ACK count
    all_sessions = (await db_session.scalars(
        select(WhatsAppDocumentSession).where(
            WhatsAppDocumentSession.organization_id == org_id,
            WhatsAppDocumentSession.phone_number == phone,
        )
    )).all()
    assert len(all_sessions) == 2, f"Expected 2 sessions, got {len(all_sessions)}"

    acks_needing = await WhatsAppSessionService.get_sessions_needing_ack(db_session, org_id)
    sender_acks = [s for s in acks_needing if s.phone_number == phone]
    assert len(sender_acks) == 2, f"Expected 2 ACKs, got {len(sender_acks)}"


@pytest.mark.asyncio
async def test_out_of_order_backlog_reconstruction_chronology(wa, db_session):
    """Section 11: Out-of-order backlog batch:
    Input array order:
    transfer B (10:04:20)
    invoice A (10:01:00)
    invoice B (10:04:00)
    transfer A (10:01:20)

    Original timestamps establish chronology.
    Expected:
    Reconstruction sorts deterministically by provider timestamp before grouping.
    Produces 2 sessions, no input-array-position matching.
    """
    org_id = wa["orgs"][0].id
    phone = "+628****0016"

    d_inv_a = uuid.uuid4()
    d_tr_a = uuid.uuid4()
    d_inv_b = uuid.uuid4()
    d_tr_b = uuid.uuid4()

    # Out of order input batch
    raw_batch = [
        {"phone_number": phone, "wamid": "m-tr-b", "message_type": "IMAGE", "timestamp": "2026-09-18T10:04:20Z", "document_id": str(d_tr_b)},
        {"phone_number": phone, "wamid": "m-inv-a", "message_type": "IMAGE", "timestamp": "2026-09-18T10:01:00Z", "document_id": str(d_inv_a)},
        {"phone_number": phone, "wamid": "m-inv-b", "message_type": "IMAGE", "timestamp": "2026-09-18T10:04:00Z", "document_id": str(d_inv_b)},
        {"phone_number": phone, "wamid": "m-tr-a", "message_type": "IMAGE", "timestamp": "2026-09-18T10:01:20Z", "document_id": str(d_tr_a)},
    ]

    reconstructed = await WhatsAppSessionService.reconstruct_backlog(
        db=db_session,
        organization_id=org_id,
        messages=raw_batch,
        as_of=datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert len(reconstructed) == 2, f"Expected 2 reconstructed sessions, got {len(reconstructed)}"
    # Verify session 1 has pair A
    s_a = next(s for s in reconstructed if str(d_inv_a) in s.document_ids)
    assert str(d_tr_a) in s_a.document_ids
    assert str(d_inv_b) not in s_a.document_ids
    assert str(d_tr_b) not in s_a.document_ids

    # Verify session 2 has pair B
    s_b = next(s for s in reconstructed if str(d_inv_b) in s.document_ids)
    assert str(d_tr_b) in s_b.document_ids
    assert str(d_inv_a) not in s_b.document_ids
    assert str(d_tr_a) not in s_b.document_ids
