import hashlib
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.document import Document
from src.models.inbox import InboxMessage, DocumentSession
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import DocumentProcessingStatus, InboxMessageStatus
from src.services.remote_relay_emulator import RemoteRelayEmulator
from src.services.remote_inbox_client import RemoteInboxClient
from src.services.storage_service import StorageService


@pytest.fixture
def mock_storage(tmp_path):
    class LocalMockStorage(StorageService):
        def __init__(self):
            self.base_dir = tmp_path

        def save_file(self, organization_id, file_obj, original_filename: str) -> str:
            target = self.base_dir / f"{organization_id}_{original_filename}"
            target.write_bytes(file_obj.read())
            return str(target)

    return LocalMockStorage()


@pytest.mark.asyncio
async def test_simulation_pc_off_capture_then_pc_on_sync(db_session: AsyncSession, mock_storage):
    """
    Phase 5 Simulation:
    WhatsApp invoice captured at edge while Finance PC is OFF.
    Finance PC starts -> pulls -> verifies hash -> persists Document once -> ACKs edge.
    """
    org = Organization(legal_name="PC-Off Simulation PT", slug=f"sim-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # 1. Edge Relay is active 24/7 (Finance PC services are OFF)
    emulator = RemoteRelayEmulator()
    emulator.set_allowlist(["+6281234567890"])

    sample_pdf_bytes = b"%PDF-1.4 Mock Invoice from Vendor PT Jaya Abadi - Total IDR 25,000,000"
    wamid = f"wamid.test.{uuid.uuid4().hex}"

    # Inbound capture at edge
    capture_res = emulator.simulate_inbound_whatsapp(
        wamid=wamid,
        sender_phone="+6281234567890",
        sender_name="Budi Supplier",
        caption="Invoice material proyek gedung A",
        file_name="invoice_vendor_jaya.pdf",
        file_bytes=sample_pdf_bytes,
        mime_type="application/pdf",
    )
    assert capture_res["status"] == "captured"
    remote_msg_id = capture_res["message_id"]

    # Verify edge state: PENDING_LOCAL
    assert emulator.messages[remote_msg_id]["status"] == "PENDING_LOCAL"

    # 2. Finance PC powers ON (services start)
    client = RemoteInboxClient(relay=emulator, storage_service=mock_storage)

    sync_result = await client.sync_remote_to_local(
        session=db_session,
        organization_id=org.id,
        limit=10,
    )

    assert sync_result["pulled"] == 1
    assert sync_result["ingested"] == 1
    assert sync_result["synced_to_documents"] == 1
    assert sync_result["acknowledged"] == 1
    assert len(sync_result["errors"]) == 0

    # Verify edge state is now SYNCED
    assert emulator.messages[remote_msg_id]["status"] == "SYNCED"

    # 3. Verify local PostgreSQL database state
    inbox_msg = await db_session.scalar(
        select(InboxMessage).where(
            InboxMessage.organization_id == org.id,
            InboxMessage.external_message_id == wamid,
        )
    )
    assert inbox_msg is not None
    assert inbox_msg.sender_phone == "+6281234567890"
    assert inbox_msg.status == InboxMessageStatus.SYNCED

    # Verify Document was created
    doc = await db_session.scalar(
        select(Document).where(Document.organization_id == org.id)
    )
    assert doc is not None
    assert doc.file_name == "invoice_vendor_jaya.pdf"
    assert doc.file_hash == hashlib.sha256(sample_pdf_bytes).hexdigest()

    # Verify DocumentSession was created for review
    doc_session = await db_session.scalar(
        select(DocumentSession).where(DocumentSession.organization_id == org.id)
    )
    assert doc_session is not None
    assert doc_session.document_id == doc.id

    # 4. Verify Idempotency: re-syncing does not duplicate
    resync_result = await client.sync_remote_to_local(
        session=db_session,
        organization_id=org.id,
        limit=10,
    )
    assert resync_result["pulled"] == 0  # No pending items left

    # Document count remains exactly 1
    doc_count = await db_session.scalar(
        select(func.count()).select_from(Document).where(Document.organization_id == org.id)
    )
    assert doc_count == 1


@pytest.mark.asyncio
async def test_simulation_duplicate_wamid_deduplication():
    """Verifies edge relay deduplicates identical WAMIDs."""
    emulator = RemoteRelayEmulator()
    wamid = "wamid.duplicate.test.123"

    res1 = emulator.simulate_inbound_whatsapp(
        wamid=wamid,
        sender_phone="+6281111111",
        sender_name="Vendor A",
        caption="Bill 1",
    )
    assert res1["status"] == "captured"

    res2 = emulator.simulate_inbound_whatsapp(
        wamid=wamid,
        sender_phone="+6281111111",
        sender_name="Vendor A",
        caption="Bill 1 retry",
    )
    assert res2["status"] == "deduplicated"
    assert len(emulator.messages) == 1


@pytest.mark.asyncio
async def test_simulation_sender_allowlist_enforcement():
    """Verifies unauthorized senders are rejected at the edge."""
    emulator = RemoteRelayEmulator()
    emulator.set_allowlist(["+6281200000001", "+6281200000002"])

    # Unauthorized sender
    res = emulator.simulate_inbound_whatsapp(
        wamid="wamid.spam.999",
        sender_phone="+628999999999",
        sender_name="Random Spammer",
        caption="Promo",
    )
    assert res["status"] == "rejected"
    assert res["reason"] == "SENDER_NOT_ALLOWLISTED"
    assert len(emulator.messages) == 0


@pytest.mark.asyncio
async def test_simulation_tampered_media_hash_rejection(db_session: AsyncSession, mock_storage):
    """Verifies media SHA-256 tampering is detected and rejected."""
    org = Organization(legal_name="Tamper Test PT", slug=f"tamper-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    emulator = RemoteRelayEmulator()
    wamid = f"wamid.tamper.{uuid.uuid4().hex}"
    capture_res = emulator.simulate_inbound_whatsapp(
        wamid=wamid,
        sender_phone="+6281200000001",
        sender_name="Vendor Tamper",
        caption="Invoice",
        file_name="invoice.pdf",
        file_bytes=b"real invoice bytes",
    )
    msg_id = capture_res["message_id"]

    # Simulate byte corruption in transit
    r2_key = emulator.messages[msg_id]["attachments"][0]["r2_key"]
    emulator.media_storage[r2_key] = b"corrupted bytes modified by attacker"

    client = RemoteInboxClient(relay=emulator, storage_service=mock_storage)
    result = await client.sync_remote_to_local(
        session=db_session,
        organization_id=org.id,
    )

    assert result["pulled"] == 1
    assert result["ingested"] == 0
    assert result["acknowledged"] == 0
    assert any("SHA-256 hash mismatch" in err for err in result["errors"])


@pytest.mark.asyncio
async def test_simulation_zero_journal_mutation_invariant(db_session: AsyncSession, mock_storage):
    """
    CRITICAL FINANCIAL INVARIANT:
    WhatsApp ingestion, OCR capture, and Remote Inbox must NEVER mutate the accounting ledger
    or create direct JournalEntry records.
    """
    org = Organization(legal_name="Zero Journal PT", slug=f"zero-jnl-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    # Pre-capture ledger check
    journals_before = await db_session.scalar(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.organization_id == org.id)
    )
    lines_before = await db_session.scalar(
        select(func.count()).select_from(JournalLine)
    )

    emulator = RemoteRelayEmulator()
    emulator.simulate_inbound_whatsapp(
        wamid=f"wamid.fin.{uuid.uuid4().hex}",
        sender_phone="+6281200000001",
        sender_name="Vendor Ledger Invariant",
        caption="Invoice for direct ledger check",
        file_name="vendor_bill.pdf",
        file_bytes=b"%PDF test vendor bill",
    )

    client = RemoteInboxClient(relay=emulator, storage_service=mock_storage)
    await client.sync_remote_to_local(session=db_session, organization_id=org.id)

    # Post-capture ledger check: must remain EXACTLY zero
    journals_after = await db_session.scalar(
        select(func.count()).select_from(JournalEntry).where(JournalEntry.organization_id == org.id)
    )
    lines_after = await db_session.scalar(
        select(func.count()).select_from(JournalLine)
    )

    assert journals_after == journals_before == 0
    assert lines_after == lines_before


@pytest.mark.asyncio
async def test_simulation_lease_expiration_and_recovery(db_session: AsyncSession, mock_storage):
    """Verifies crash recovery when lease expires."""
    org = Organization(legal_name="Lease Recovery PT", slug=f"lease-rec-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    emulator = RemoteRelayEmulator()
    wamid = f"wamid.lease.{uuid.uuid4().hex}"
    capture_res = emulator.simulate_inbound_whatsapp(
        wamid=wamid,
        sender_phone="+6281200000001",
        sender_name="Vendor Lease",
        caption="Invoice Lease Test",
        file_name="invoice_lease.pdf",
        file_bytes=b"%PDF lease test content",
    )
    msg_id = capture_res["message_id"]

    # Pull message once (lease acquired)
    pulled_1 = emulator.pull_pending(limit=10)
    assert len(pulled_1) == 1
    assert emulator.messages[msg_id]["status"] == "LEASED"

    # Immediate second pull returns nothing because lease is active
    pulled_2 = emulator.pull_pending(limit=10)
    assert len(pulled_2) == 0

    # Simulate client crash / timeout: expire all leases
    emulator.expire_all_leases()

    # New client cycle pulls and completes sync successfully
    client = RemoteInboxClient(relay=emulator, storage_service=mock_storage)
    sync_res = await client.sync_remote_to_local(session=db_session, organization_id=org.id)
    assert sync_res["pulled"] == 1
    assert sync_res["ingested"] == 1
    assert sync_res["acknowledged"] == 1
    assert emulator.messages[msg_id]["status"] == "SYNCED"
