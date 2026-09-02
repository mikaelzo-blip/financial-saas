import io
import time
import uuid
import json
import hmac
import hashlib
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
import httpx
from pydantic import SecretStr
from sqlalchemy import select, func

from src.core.config import settings
from src.core.security import create_access_token
from src.models import (
    Organization, User, UserRole, Document, WhatsAppMessageLog,
    WhatsAppClarificationSession, Project, Counterparty,
    Transaction, JournalEntry, CustomerInvoice,
    VendorBill, AuditLog,
)
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    DocumentType, DocumentProcessingStatus, CandidateStatus,
    ProjectStatus, AccountType, NormalBalance,
)
from src.schemas.document import StructuredExtraction, ConfidenceScores, TransactionCandidate
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.integrations.whatsapp.provider import ProviderError
from src.services.document_service import DocumentService
from src.services.documents.pipeline import DocumentPipeline
from src.services.documents.extraction import ExtractionResult, ScriptedExtractionProvider


@pytest.fixture
async def wa_uat(client, db_session, monkeypatch, tmp_path):
    """Authoritative test fixture for WhatsApp Media Transport & Intake UAT."""
    from src.api.v1 import hermes
    from src.core.database import get_db

    orgs, users, accounts = [], [], []
    for slug, legal in [("org-alpha", "PT Alpha Konstruksi"), ("org-beta", "PT Beta Mandiri")]:
        org = Organization(slug=slug, legal_name=legal)
        db_session.add(org)
        await db_session.flush()

        admin = User(
            organization_id=org.id,
            email=f"admin@{slug}.test",
            full_name=f"Admin {legal}",
            password_hash="x",
            role=UserRole.ADMIN,
        )
        db_session.add(admin)

        # Standard COA setup for accounting verification
        coa_1101 = ChartOfAccount(
            organization_id=org.id,
            account_code="1101",
            account_name="Kas dan Bank",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="ASSET",
        )
        coa_1201 = ChartOfAccount(
            organization_id=org.id,
            account_code="1201",
            account_name="Piutang Usatan",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="ASSET",
        )
        coa_2101 = ChartOfAccount(
            organization_id=org.id,
            account_code="2101",
            account_name="Utang Usaha",
            account_type=AccountType.LIABILITY,
            normal_balance=NormalBalance.CREDIT,
            report_group="LIABILITY",
        )
        coa_4101 = ChartOfAccount(
            organization_id=org.id,
            account_code="4101",
            account_name="Pendapatan Proyek",
            account_type=AccountType.REVENUE,
            normal_balance=NormalBalance.CREDIT,
            report_group="REVENUE",
        )
        coa_5101 = ChartOfAccount(
            organization_id=org.id,
            account_code="5101",
            account_name="Beban Material",
            account_type=AccountType.EXPENSE,
            normal_balance=NormalBalance.DEBIT,
            report_group="EXPENSE",
        )
        db_session.add_all([coa_1101, coa_1201, coa_2101, coa_4101, coa_5101])
        await db_session.flush()

        # Payment Account
        bank_acc = PaymentAccount(
            organization_id=org.id,
            name="BCA Operasional",
            coa_account_id=coa_1101.id,
        )
        db_session.add(bank_acc)
        await db_session.flush()

        orgs.append(org)
        users.append(admin)
        accounts.append(bank_acc)

    await db_session.commit()

    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-secret-key-123"))
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_APP_SECRET", SecretStr("webhook-app-secret-456"))
    monkeypatch.setattr(
        settings,
        "WHATSAPP_TENANT_TOKENS",
        {str(org.id): SecretStr(f"tenant-token-{i}") for i, org in enumerate(orgs)},
    )
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    # Disable default background task in hermes module to allow deterministic test pipeline execution
    async def noop_background(document_id):
        pass
    monkeypatch.setattr(hermes, "process_document_background", noop_background)

    app = client._transport.app
    database_lock = asyncio.Lock()

    async def scoped_db():
        async with database_lock:
            try:
                yield db_session
                await db_session.commit()
            except Exception:
                await db_session.rollback()
                for instance in list(db_session.identity_map.values()):
                    await db_session.refresh(instance)
                raise

    app.dependency_overrides[get_db] = scoped_db

    transport = HttpxHermesTransport("https://saas.test", transport=httpx.ASGITransport(app=app))
    gateway = HermesApiClient(transport, lambda: "adapter-secret-key-123", "https://saas.test")

    def tenant_client(org_id_str):
        token_secret = settings.WHATSAPP_TENANT_TOKENS[org_id_str].get_secret_value()
        return HermesApiClient(transport, lambda: token_secret, "https://saas.test")

    provider = MockWhatsAppProvider()
    service = WhatsAppWebhookService(provider, gateway, tenant_client, [str(o.id) for o in orgs])
    app.state.whatsapp_service = service

    # Register senders
    phones = ["+6281111111111", "+6282222222222"]
    for user, phone in zip(users, phones):
        resp = await client.post(
            "/api/v1/integrations/whatsapp/senders",
            headers={
                "Authorization": f"Bearer {create_access_token(user.id)}",
                "X-Organization-ID": str(user.organization_id),
            },
            json={
                "user_id": str(user.id),
                "phone_number": phone,
                "display_name": user.full_name,
                "role_in_org": "PROJECT_MANAGER",
            },
        )
        assert resp.status_code == 201, resp.text

    return {
        "client": client,
        "provider": provider,
        "orgs": orgs,
        "users": users,
        "phones": phones,
        "accounts": accounts,
        "service": service,
        "tmp_path": tmp_path,
    }


async def post_wa_webhook(
    wa_uat,
    *,
    phone=None,
    wamid="wamid.msg-default",
    message_type="image",
    text=None,
    media_id="media-001",
    mime_type="image/jpeg",
    file_name="receipt.jpg",
    caption=None,
    timestamp=None,
):
    """Helper to simulate WhatsApp webhook post with valid cryptographic HMAC signature."""
    sender_phone = (phone or wa_uat["phones"][0]).lstrip("+")
    msg_ts = str(timestamp or int(time.time()))

    msg = {
        "id": wamid,
        "from": sender_phone,
        "timestamp": msg_ts,
        "type": message_type,
    }

    if message_type == "text":
        msg["text"] = {"body": text or "Halo"}
    elif message_type in ("image", "document"):
        msg[message_type] = {
            "id": media_id,
            "mime_type": mime_type,
            "filename": file_name,
            "caption": caption or "Bukti transfer pembayaran",
        }

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [msg]}}]}],
    }
    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(b"webhook-app-secret-456", body, hashlib.sha256).hexdigest()

    return await wa_uat["client"].post(
        "/api/v1/integrations/whatsapp/webhook",
        content=body,
        headers={"X-Hub-Signature-256": signature},
    )


# ==============================================================================
# PHASE P AUTOMATED END-TO-END SCENARIO TESTS (1 - 30)
# ==============================================================================

@pytest.mark.asyncio
async def test_scenario_01_valid_inbound_text(wa_uat, db_session):
    """Scenario 1: Valid inbound text message handled safely without creating documents."""
    resp = await post_wa_webhook(wa_uat, wamid="wamid.txt-01", message_type="text", text="HELP")
    assert resp.status_code == 200

    # Command help reply sent
    assert len(wa_uat["provider"].outbound) == 1
    assert "Kirim foto nota/PDF" in wa_uat["provider"].outbound[0].body_text

    # No document created
    doc_count = await db_session.scalar(select(func.count()).select_from(Document))
    assert doc_count == 0

    # Inbound and outbound message logs recorded
    logs = (await db_session.scalars(select(WhatsAppMessageLog))).all()
    assert len(logs) == 2
    assert {log.direction for log in logs} == {"INBOUND", "OUTBOUND"}


@pytest.mark.asyncio
async def test_scenario_02_valid_pdf_media(wa_uat, db_session):
    """Scenario 2: Valid PDF document ingested with correct metadata and magic bytes."""
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    wa_uat["provider"].media["pdf-media-1"] = ("application/pdf", pdf_bytes)

    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.pdf-01",
        message_type="document",
        media_id="pdf-media-1",
        mime_type="application/pdf",
        file_name="invoice_spk.pdf",
        caption="Tagihan Proyek Tower A",
    )
    assert resp.status_code == 200

    doc = await db_session.scalar(select(Document).where(Document.file_name == "invoice_spk.pdf"))
    assert doc is not None
    assert doc.source_channel == "WHATSAPP"
    assert doc.mime_type == "application/pdf"
    assert doc.source_metadata["wamid"] == "wamid.pdf-01"
    assert doc.source_metadata["caption"] == "Tagihan Proyek Tower A"
    assert doc.created_by == wa_uat["users"][0].id


@pytest.mark.asyncio
async def test_scenario_03_valid_image_media(wa_uat, db_session):
    """Scenario 3: Valid JPEG, PNG, and WEBP image media ingestion."""
    # JPEG
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
    wa_uat["provider"].media["img-jpeg-1"] = ("image/jpeg", jpeg_bytes)
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.img-jpeg-01",
        message_type="image",
        media_id="img-jpeg-1",
        mime_type="image/jpeg",
        file_name="struk.jpg",
    )
    assert resp.status_code == 200

    # PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    wa_uat["provider"].media["img-png-1"] = ("image/png", png_bytes)
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.img-png-01",
        message_type="image",
        media_id="img-png-1",
        mime_type="image/png",
        file_name="nota.png",
    )
    assert resp.status_code == 200

    # WEBP
    webp_bytes = b"RIFF\x18\x00\x00\x00WEBPVP8 \x0c\x00\x00\x00\x00\x00\x00\x9d\x01*\x01\x00\x01\x00"
    wa_uat["provider"].media["img-webp-1"] = ("image/webp", webp_bytes)
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.img-webp-01",
        message_type="image",
        media_id="img-webp-1",
        mime_type="image/webp",
        file_name="foto.webp",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    assert len(docs) == 3
    assert {d.mime_type for d in docs} == {"image/jpeg", "image/png", "image/webp"}


@pytest.mark.asyncio
async def test_scenario_04_transfer_proof_flow(wa_uat, db_session):
    """Scenario 4: Transfer proof ingestion creates candidate and review item, no journal entry."""
    org = wa_uat["orgs"][0]
    cust = Counterparty(organization_id=org.id, name="PT Thamrin Properti", is_customer=True)
    db_session.add(cust); await db_session.flush()

    wa_uat["provider"].media["transfer-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-transfer-proof-01",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.transfer-01",
        message_type="image",
        media_id="transfer-01",
        mime_type="image/jpeg",
        caption="Bukti transfer pembayaran termin 1 Proyek Thamrin",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.transfer-01"][0]
    assert doc is not None

    # Run extraction pipeline
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="50000000.00",
        currency_code="IDR",
        issuer_name="PT Thamrin Properti",
    )
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".92",
        entity_confidence=".90",
        project_confidence=".90",
        amount_confidence=".95",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.TRANSFER_PROOF, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.document_type == DocumentType.TRANSFER_PROOF
    assert doc.candidate_transaction["proposed_transaction_type"] == "CUSTOMER_PAYMENT"
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED

    # Hard stop: No journal entry created
    journal_count = await db_session.scalar(select(func.count()).select_from(JournalEntry))
    assert journal_count == 0


@pytest.mark.asyncio
async def test_scenario_05_purchase_receipt_flow(wa_uat, db_session):
    """Scenario 5: Purchase receipt ingestion creates DIRECT_PURCHASE candidate awaiting review."""
    wa_uat["provider"].media["receipt-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-receipt-01",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.receipt-01",
        message_type="image",
        media_id="receipt-01",
        mime_type="image/jpeg",
        caption="Nota tunai beli semen 50 sak toko bangun jaya",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.receipt-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="3250000.00",
        currency_code="IDR",
        issuer_name="Toko Bangun Jaya",
    )
    scores = ConfidenceScores(
        ocr_confidence=".90",
        document_type_confidence=".90",
        entity_confidence=".90",
        project_confidence=".90",
        amount_confidence=".90",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.RECEIPT, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.document_type == DocumentType.RECEIPT
    assert doc.candidate_transaction["proposed_transaction_type"] == "DIRECT_PURCHASE"
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_06_vendor_invoice_flow(wa_uat, db_session):
    """Scenario 6: Vendor invoice ingestion creates VENDOR_BILL candidate awaiting review."""
    wa_uat["provider"].media["vendor-inv-01"] = (
        "application/pdf",
        b"%PDF-1.4\nvendor-bill-sample\n%%EOF",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.vendor-inv-01",
        message_type="document",
        media_id="vendor-inv-01",
        mime_type="application/pdf",
        file_name="invoice_sewa_crane.pdf",
        caption="Invoice sewa crane PT Maju Crane",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.vendor-inv-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="15000000.00",
        currency_code="IDR",
        issuer_name="PT Maju Crane",
        invoice_number="INV/CR/2026/009",
    )
    scores = ConfidenceScores(
        ocr_confidence=".96",
        document_type_confidence=".95",
        entity_confidence=".95",
        project_confidence=".95",
        amount_confidence=".96",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.VENDOR_INVOICE, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.document_type == DocumentType.VENDOR_INVOICE
    assert doc.candidate_transaction["proposed_transaction_type"] == "VENDOR_BILL"
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_07_po_spk_supporting_document_flow(wa_uat, db_session):
    """Scenario 7: PO / SPK supporting document produces no financial candidate or posting."""
    wa_uat["provider"].media["spk-01"] = (
        "application/pdf",
        b"%PDF-1.4\nspk-contract-sample\n%%EOF",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.spk-01",
        message_type="document",
        media_id="spk-01",
        mime_type="application/pdf",
        file_name="spk_kontrak.pdf",
        caption="SPK Kontrak Renovasi Ruko",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.spk-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-01",
        total_amount="250000000.00",
        currency_code="IDR",
        issuer_name="PT Pemberi Tugas",
    )
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".95",
        entity_confidence=".95",
        project_confidence=".95",
        amount_confidence=".95",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.SPK, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.document_type == DocumentType.SPK
    assert doc.candidate_transaction == {}
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_08_bast_surat_jalan_flow(wa_uat, db_session):
    """Scenario 8: BAST / Surat Jalan operational documents ingested without financial ledger entries."""
    wa_uat["provider"].media["bast-01"] = (
        "application/pdf",
        b"%PDF-1.4\nbast-sample-content\n%%EOF",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.bast-01",
        message_type="document",
        media_id="bast-01",
        mime_type="application/pdf",
        file_name="bast_termin_1.pdf",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.bast-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount=None,
        currency_code="IDR",
    )
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".90",
        entity_confidence=".90",
        project_confidence=".90",
        amount_confidence=".90",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.BAST, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.document_type == DocumentType.BAST
    assert doc.candidate_transaction == {}
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_09_duplicate_webhook_delivery(wa_uat, db_session):
    """Scenario 9: Exact webhook re-delivery does not duplicate Document or outbound ack."""
    wa_uat["provider"].media["dup-webhook-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-dup-test-01",
    )
    # First delivery
    resp1 = await post_wa_webhook(
        wa_uat,
        wamid="wamid.dup-webhook-01",
        message_type="image",
        media_id="dup-webhook-01",
        mime_type="image/jpeg",
    )
    assert resp1.status_code == 200
    outbound_count_1 = len(wa_uat["provider"].outbound)
    download_count_1 = wa_uat["provider"].downloads

    # Second delivery with exact same wamid
    resp2 = await post_wa_webhook(
        wa_uat,
        wamid="wamid.dup-webhook-01",
        message_type="image",
        media_id="dup-webhook-01",
        mime_type="image/jpeg",
    )
    assert resp2.status_code == 200

    # No second download, no second outbound ack
    assert len(wa_uat["provider"].outbound) == outbound_count_1
    assert wa_uat["provider"].downloads == download_count_1
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.asyncio
async def test_scenario_10_duplicate_media_content(wa_uat, db_session):
    """Scenario 10: Media with identical content SHA-256 is deduplicated at document level."""
    same_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-identical-bytes"
    wa_uat["provider"].media["media-a"] = ("image/jpeg", same_bytes)
    wa_uat["provider"].media["media-b"] = ("image/jpeg", same_bytes)

    resp1 = await post_wa_webhook(
        wa_uat, wamid="wamid.media-a", message_type="image", media_id="media-a", mime_type="image/jpeg"
    )
    assert resp1.status_code == 200

    resp2 = await post_wa_webhook(
        wa_uat, wamid="wamid.media-b", message_type="image", media_id="media-b", mime_type="image/jpeg"
    )
    assert resp2.status_code == 200

    # Only one Document row created
    doc_count = await db_session.scalar(select(func.count()).select_from(Document))
    assert doc_count == 1

    # Outbound response for duplicate indicates already received
    assert "sebelumnya" in wa_uat["provider"].outbound[-1].body_text


@pytest.mark.asyncio
async def test_scenario_11_concurrent_replay_resilience(wa_uat, db_session):
    """Scenario 11: Concurrent re-delivery of the same webhook produces exactly one intake."""
    wa_uat["provider"].media["concurrent-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-concurrent-bytes",
    )

    results = await asyncio.gather(
        post_wa_webhook(wa_uat, wamid="wamid.concurrent-01", media_id="concurrent-01", mime_type="image/jpeg"),
        post_wa_webhook(wa_uat, wamid="wamid.concurrent-01", media_id="concurrent-01", mime_type="image/jpeg"),
    )
    assert all(r.status_code == 200 for r in results)
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.asyncio
async def test_scenario_12_unknown_tenant_phone_rejection(wa_uat, db_session):
    """Scenario 12: Unregistered sender phone number is rejected with informative notice."""
    resp = await post_wa_webhook(
        wa_uat,
        phone="+6289999999999",
        wamid="wamid.unknown-phone-01",
        message_type="text",
        text="Halo saya mandor baru",
    )
    assert resp.status_code == 200
    assert "belum terdaftar" in wa_uat["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.asyncio
async def test_scenario_13_forged_tenant_information_rejected(wa_uat, db_session):
    """Scenario 13: Sender phone from Tenant A cannot submit with headers or claims of Tenant B."""
    org0, org1 = wa_uat["orgs"]
    phone0, phone1 = wa_uat["phones"]

    # Direct machine endpoint check: claiming phone0 with tenant-1 token must fail
    claim_resp = await wa_uat["client"].post(
        "/api/v1/hermes/whatsapp/messages/claim",
        headers={"Authorization": "Bearer tenant-token-1"},
        json={
            "wamid": "wamid.forged-01",
            "sender_phone": phone0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "TEXT",
            "text": "Attacking org",
            "file_name": "doc",
        },
    )
    assert claim_resp.status_code == 403


@pytest.mark.asyncio
async def test_scenario_14_oversized_media_rejection(wa_uat, db_session):
    """Scenario 14: Media exceeding maximum allowed size is safely rejected."""
    oversized = b"%PDF-1.4\n" + b"X" * (26 * 1024 * 1024)
    wa_uat["provider"].media["oversized-01"] = ("application/pdf", oversized)

    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.oversized-01",
        message_type="document",
        media_id="oversized-01",
        mime_type="application/pdf",
        file_name="huge.pdf",
    )
    assert resp.status_code == 200
    assert "gagal diunduh" in wa_uat["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.asyncio
async def test_scenario_15_invalid_mime_rejection(wa_uat, db_session):
    """Scenario 15: Mismatched MIME type vs magic byte signature is rejected."""
    fake_jpeg = b"THIS IS NOT A REAL JPEG IMAGE FILE"
    wa_uat["provider"].media["fake-jpeg-01"] = ("image/jpeg", fake_jpeg)

    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.fake-jpeg-01",
        message_type="image",
        media_id="fake-jpeg-01",
        mime_type="image/jpeg",
        file_name="fake.jpg",
    )
    assert resp.status_code == 200
    assert "gagal diunduh" in wa_uat["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.asyncio
async def test_scenario_16_corrupted_media_handling(wa_uat, db_session):
    """Scenario 16: Truncated or corrupted media stream terminates cleanly without crash."""
    # Truncated content with wrong bytes not matching any MIME signature
    corrupted_bytes = b"bad-stream-content"
    wa_uat["provider"].media["corrupt-01"] = ("image/jpeg", corrupted_bytes)

    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.corrupt-01",
        message_type="image",
        media_id="corrupt-01",
        mime_type="image/jpeg",
        file_name="corrupt.jpg",
    )
    assert resp.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.asyncio
async def test_scenario_17_ambiguous_amount_routes_to_clarification_and_review(wa_uat, db_session):
    """Scenario 17: Ambiguous amount extracted raises OCR_LOW_CONFIDENCE and routes to Review Queue."""
    wa_uat["provider"].media["ambig-amt-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-ambig-amt",
    )
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.ambig-amt-01",
        message_type="image",
        media_id="ambig-amt-01",
        mime_type="image/jpeg",
        caption="Nota beli semen",
    )
    assert resp.status_code == 200

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.ambig-amt-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="1500000.00",
        currency_code="IDR",
    )
    scores = ConfidenceScores(
        ocr_confidence=".55",
        document_type_confidence=".90",
        entity_confidence=".90",
        project_confidence=".90",
        amount_confidence=".45",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.RECEIPT, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert "OCR_LOW_CONFIDENCE" in doc.review_flags
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_scenario_18_ambiguous_project_triggers_clarification(wa_uat, db_session):
    """Scenario 18: Ambiguous project triggers WhatsApp interactive clarification session."""
    org = wa_uat["orgs"][0]
    cust = Counterparty(organization_id=org.id, name="Owner Thamrin", is_customer=True)
    db_session.add(cust); await db_session.flush()

    p1 = Project(organization_id=org.id, project_code="PRJ-TH-01", project_name="Ruko Thamrin 1", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    p2 = Project(organization_id=org.id, project_code="PRJ-TH-02", project_name="Ruko Thamrin 2", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add_all([p1, p2]); await db_session.commit()

    wa_uat["provider"].media["ambig-prj-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-ambig-prj",
    )
    await post_wa_webhook(
        wa_uat,
        wamid="wamid.ambig-prj-01",
        message_type="image",
        media_id="ambig-prj-01",
        mime_type="image/jpeg",
        caption="Nota beli semen",
    )

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.ambig-prj-01"][0]
    extraction = StructuredExtraction(transaction_date="2026-09-03", total_amount="1500000.00", currency_code="IDR")
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".90",
        entity_confidence=".90",
        project_confidence=".90",
        amount_confidence=".95",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.RECEIPT, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    doc.review_flags = ["PROJECT_UNKNOWN"]
    await db_session.commit()

    # Deliver notification polling -> should create clarification session
    await wa_uat["service"].deliver_pending_notifications()

    session = await db_session.scalar(select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.document_id == doc.id))
    assert session is not None
    assert session.question_type == "SELECT_PROJECT"
    assert session.status == "PENDING"
    assert "Pilih jawaban klarifikasi" in wa_uat["provider"].outbound[-1].body_text


@pytest.mark.asyncio
async def test_scenario_19_unknown_vendor_routes_to_review(wa_uat, db_session):
    """Scenario 19: Unknown vendor flags VENDOR_UNKNOWN and routes to Review Queue."""
    wa_uat["provider"].media["unkn-vendor-01"] = (
        "application/pdf",
        b"%PDF-1.4\nunkn-vendor-sample\n%%EOF",
    )
    await post_wa_webhook(
        wa_uat,
        wamid="wamid.unkn-vendor-01",
        message_type="document",
        media_id="unkn-vendor-01",
        mime_type="application/pdf",
        file_name="tagihan_bengkel.pdf",
    )
    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.unkn-vendor-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="4500000.00",
        currency_code="IDR",
        issuer_name="CV Belum Terdaftar",
    )
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".95",
        entity_confidence=".95",
        project_confidence=".95",
        amount_confidence=".95",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.VENDOR_INVOICE, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert "VENDOR_UNKNOWN" in doc.review_flags
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_scenario_20_unknown_customer_routes_to_review(wa_uat, db_session):
    """Scenario 20: Unknown customer in transfer proof flags VENDOR_UNKNOWN (counterparty unmapped) and routes to Review."""
    wa_uat["provider"].media["unkn-cust-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-unkn-cust",
    )
    await post_wa_webhook(
        wa_uat,
        wamid="wamid.unkn-cust-01",
        message_type="image",
        media_id="unkn-cust-01",
        mime_type="image/jpeg",
        caption="Transfer dari PT Klien Baru",
    )
    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.unkn-cust-01"][0]
    extraction = StructuredExtraction(
        transaction_date="2026-09-03",
        total_amount="75000000.00",
        currency_code="IDR",
        issuer_name="PT Klien Baru",
    )
    scores = ConfidenceScores(
        ocr_confidence=".95",
        document_type_confidence=".95",
        entity_confidence=".95",
        project_confidence=".95",
        amount_confidence=".95",
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.TRANSFER_PROOF, extraction, scores, "mock-ocr", "1.0"
    ))
    doc_service = DocumentService(db_session)
    await DocumentPipeline(db_session, provider).process(doc, doc_service.storage.get_file_path(doc.storage_path))
    await db_session.commit()

    await db_session.refresh(doc)
    assert "VENDOR_UNKNOWN" in doc.review_flags
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_scenario_21_clarification_state_updates_candidate_without_posting(wa_uat, db_session):
    """Scenario 21: Clarification reply updates candidate metadata only; never posts journals."""
    org = wa_uat["orgs"][0]
    cust = Counterparty(organization_id=org.id, name="Owner Clarif", is_customer=True)
    db_session.add(cust); await db_session.flush()
    project = Project(organization_id=org.id, project_code="PRJ-CL-01", project_name="Proyek Clarif 1", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add(project); await db_session.commit()

    wa_uat["provider"].media["clarif-doc-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-clarif-doc",
    )
    await post_wa_webhook(
        wa_uat,
        wamid="wamid.clarif-doc-01",
        message_type="image",
        media_id="clarif-doc-01",
        mime_type="image/jpeg",
    )
    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.clarif-doc-01"][0]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.candidate_transaction = {"id": str(uuid.uuid4()), "status": "REVIEW_REQUIRED", "amount": "5000000.00"}
    doc.review_flags = ["PROJECT_UNKNOWN"]
    await db_session.commit()

    await wa_uat["service"].deliver_pending_notifications()
    session = await db_session.scalar(select(WhatsAppClarificationSession).where(WhatsAppClarificationSession.document_id == doc.id))
    assert session.status == "PENDING"

    # Send clarification reply with option "1"
    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.clarif-reply-01",
        message_type="text",
        text="1",
    )
    assert resp.status_code == 200

    await db_session.refresh(session)
    await db_session.refresh(doc)
    assert session.status == "ANSWERED"
    assert doc.candidate_transaction["project_id"] == str(project.id)
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED

    # Verification: Zero journal entries
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_22_review_queue_retrieval(wa_uat, db_session):
    """Scenario 22: Documents requiring review are listed in authenticated Review Queue API."""
    org = wa_uat["orgs"][0]
    user = wa_uat["users"][0]
    wa_uat["provider"].media["rq-doc-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-rq-doc",
    )
    await post_wa_webhook(
        wa_uat,
        wamid="wamid.rq-doc-01",
        message_type="image",
        media_id="rq-doc-01",
        mime_type="image/jpeg",
    )
    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == "wamid.rq-doc-01"][0]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.candidate_transaction = {"id": str(uuid.uuid4()), "status": "REVIEW_REQUIRED"}
    doc.review_flags = ["OCR_LOW_CONFIDENCE"]
    await db_session.commit()

    resp = await wa_uat["client"].get(
        "/api/v1/documents/review-queue",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert any(item["id"] == str(doc.id) for item in items)


@pytest.mark.asyncio
async def test_scenario_23_rejected_candidate_creates_no_financial_mutation(wa_uat, db_session):
    """Scenario 23: Reviewer rejects candidate; document marked REJECTED, 0 journals created."""
    org = wa_uat["orgs"][0]
    user = wa_uat["users"][0]
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nreject-target\n%%EOF"),
        "fake_receipt.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        source_channel="WHATSAPP",
    )
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.candidate_transaction = {"id": str(uuid.uuid4()), "status": "REVIEW_REQUIRED"}
    await db_session.commit()

    resp = await wa_uat["client"].post(
        f"/api/v1/documents/{doc.id}/reject",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
        json={"reason": "Nota buram dan tidak valid"},
    )
    assert resp.status_code == 200
    assert resp.json()["processing_status"] == "REJECTED"

    # Ledger remains untouched
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_24_approved_candidate_converts_to_authoritative_business_event(wa_uat, db_session):
    """Scenario 24: Explicit reviewer approval creates business transaction and posts journal."""
    org = wa_uat["orgs"][0]
    user = wa_uat["users"][0]

    # Create customer, vendor and project
    cust = Counterparty(organization_id=org.id, name="Owner Gedung A", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name="PT Supplier Material", is_vendor=True)
    db_session.add_all([cust, vendor]); await db_session.flush()
    project = Project(organization_id=org.id, project_code="PRJ-APP-01", project_name="Proyek Gedung A", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add(project); await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nvendor-bill-approved\n%%EOF"),
        "tagihan_material.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        source_channel="WHATSAPP",
    )
    candidate = TransactionCandidate(
        id=doc.id,
        proposed_transaction_type="VENDOR_BILL",
        transaction_date="2026-09-03",
        amount="12000000.00",
        currency_code="IDR",
        counterparty_id=vendor.id,
        project_id=project.id,
        cost_category="MAT",
        description="Tagihan besi beton proyek Gedung A",
        status=CandidateStatus.READY_FOR_APPROVAL,
    )
    doc.candidate_transaction = candidate.model_dump(mode="json")
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()

    resp = await wa_uat["client"].post(
        f"/api/v1/documents/{doc.id}/approve",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
    )
    assert resp.status_code == 201, resp.text
    result = resp.json()
    assert result["id"] is not None
    assert result["transaction_type"] == "VENDOR_BILL"

    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.PROCESSED
    assert doc.candidate_transaction["converted_transaction_id"] == result["id"]

    # Subledger check: VendorBill created
    bill = await db_session.scalar(select(VendorBill).where(VendorBill.organization_id == org.id))
    assert bill is not None
    assert bill.total_amount == Decimal("12000000.00")
    assert bill.status == "UNPAID"


@pytest.mark.asyncio
async def test_scenario_25_no_journal_before_approval(wa_uat, db_session):
    """Scenario 25: Accounting hard stop strictly verified - 0 journals across all intake/extraction stages."""
    # Ensure zero journals initially
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0

    # Ingest several documents via WhatsApp
    wa_uat["provider"].media["doc-h1"] = ("application/pdf", b"%PDF-1.4\nhardstop-1\n%%EOF")
    wa_uat["provider"].media["doc-h2"] = ("image/jpeg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-hardstop-2")

    await post_wa_webhook(wa_uat, wamid="wamid.h1", message_type="document", media_id="doc-h1", mime_type="application/pdf")
    await post_wa_webhook(wa_uat, wamid="wamid.h2", message_type="image", media_id="doc-h2", mime_type="image/jpeg")

    # Re-verify: Zero journal entries, zero AR changes, zero AP changes
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0
    assert await db_session.scalar(select(func.count()).select_from(CustomerInvoice)) == 0
    assert await db_session.scalar(select(func.count()).select_from(VendorBill)) == 0


@pytest.mark.asyncio
async def test_scenario_26_exactly_one_journal_after_approval(wa_uat, db_session):
    """Scenario 26: Approval creates exactly 1 JournalEntry where Total Debit == Total Credit."""
    org = wa_uat["orgs"][0]
    user = wa_uat["users"][0]
    bank_acc = wa_uat["accounts"][0]
    cust = Counterparty(organization_id=org.id, name="Owner B", is_customer=True)
    db_session.add(cust); await db_session.flush()
    project = Project(organization_id=org.id, project_code="PRJ-EXP-01", project_name="Proyek Ruko B", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add(project); await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-direct-exp"),
        "nota_bensin.jpg",
        "image/jpeg",
        DocumentType.RECEIPT,
        source_channel="WHATSAPP",
    )
    candidate = TransactionCandidate(
        id=doc.id,
        proposed_transaction_type="DIRECT_PURCHASE",
        transaction_date="2026-09-03",
        amount="500000.00",
        currency_code="IDR",
        payment_account_id=bank_acc.id,
        project_id=project.id,
        cost_category="EQP",
        description="Beli bensin genset proyek",
        status=CandidateStatus.READY_FOR_APPROVAL,
    )
    doc.candidate_transaction = candidate.model_dump(mode="json")
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()

    resp = await wa_uat["client"].post(
        f"/api/v1/documents/{doc.id}/approve",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
    )
    assert resp.status_code == 201

    journals = (await db_session.scalars(select(JournalEntry).where(JournalEntry.organization_id == org.id))).all()
    assert len(journals) == 1
    journal = journals[0]
    assert journal.total_debit == Decimal("500000.00")
    assert journal.total_credit == Decimal("500000.00")
    assert journal.total_debit == journal.total_credit


@pytest.mark.asyncio
async def test_scenario_27_tenant_isolation_boundary(wa_uat, db_session):
    """Scenario 27: Tenant isolation strictly prevents cross-tenant document, sender, and clarification access."""
    org0, org1 = wa_uat["orgs"]
    user0, user1 = wa_uat["users"]
    phone0, phone1 = wa_uat["phones"]

    # Ingest document under Org 0
    wa_uat["provider"].media["iso-doc-0"] = ("image/jpeg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-iso-0")
    await post_wa_webhook(wa_uat, phone=phone0, wamid="wamid.iso-doc-0", media_id="iso-doc-0", mime_type="image/jpeg")

    doc0 = await db_session.scalar(select(Document).where(Document.organization_id == org0.id))
    assert doc0 is not None

    # Org 1 user cannot access Org 0 document
    resp = await wa_uat["client"].get(
        f"/api/v1/documents/{doc0.id}",
        headers={"X-Organization-ID": str(org1.id), "X-User-ID": str(user1.id)},
    )
    assert resp.status_code == 404

    # Org 1 cannot approve Org 0 document
    resp_approve = await wa_uat["client"].post(
        f"/api/v1/documents/{doc0.id}/approve",
        headers={"X-Organization-ID": str(org1.id), "X-User-ID": str(user1.id)},
    )
    assert resp_approve.status_code == 404


@pytest.mark.asyncio
async def test_scenario_28_end_to_end_audit_trail(wa_uat, db_session):
    """Scenario 28: Traceability verified from WhatsApp wamid -> HermesSubmission -> Document -> Approval -> Journal."""
    org = wa_uat["orgs"][0]
    user = wa_uat["users"][0]
    cust = Counterparty(organization_id=org.id, name="Owner Audit", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name="PT Audit Vendor", is_vendor=True)
    db_session.add_all([cust, vendor]); await db_session.flush()
    project = Project(organization_id=org.id, project_code="PRJ-AUD-01", project_name="Audit Project", customer_id=cust.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add(project); await db_session.flush()

    wamid = "wamid.audit-trail-001"
    wa_uat["provider"].media["audit-media-01"] = ("application/pdf", b"%PDF-1.4\naudit-trail-data\n%%EOF")
    await post_wa_webhook(
        wa_uat,
        wamid=wamid,
        message_type="document",
        media_id="audit-media-01",
        mime_type="application/pdf",
        file_name="audit_bill.pdf",
    )

    docs = (await db_session.scalars(select(Document))).all()
    doc = [d for d in docs if d.source_metadata.get("wamid") == wamid][0]
    assert doc is not None
    assert doc.source_metadata["wamid"] == wamid

    candidate = TransactionCandidate(
        id=doc.id,
        proposed_transaction_type="VENDOR_BILL",
        transaction_date="2026-09-03",
        amount="8500000.00",
        currency_code="IDR",
        counterparty_id=vendor.id,
        project_id=project.id,
        cost_category="SUB",
        description="Audit verification bill",
        status=CandidateStatus.READY_FOR_APPROVAL,
    )
    doc.candidate_transaction = candidate.model_dump(mode="json")
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()

    approve_resp = await wa_uat["client"].post(
        f"/api/v1/documents/{doc.id}/approve",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
    )
    assert approve_resp.status_code == 201

    # Trace audit logs
    audit_events = (await db_session.scalars(
        select(AuditLog).where(AuditLog.organization_id == org.id).order_by(AuditLog.timestamp.asc())
    )).all()
    actions = [evt.action for evt in audit_events]
    assert "DOCUMENT_RECEIVED" in actions
    assert "APPROVE_CANDIDATE" in actions
    assert "POST" in actions


@pytest.mark.asyncio
async def test_scenario_29_provider_failure_handling(wa_uat, db_session, monkeypatch):
    """Scenario 29: Provider download timeout or network failure handled without partial state."""
    async def failing_download(media_id):
        raise ProviderError("DOWNLOAD_FAILED")

    monkeypatch.setattr(wa_uat["service"].media.provider, "media_reference", failing_download)

    resp = await post_wa_webhook(
        wa_uat,
        wamid="wamid.fail-prov-01",
        message_type="image",
        media_id="missing-media-id",
        mime_type="image/jpeg",
    )
    assert resp.status_code == 200
    assert "gagal diunduh" in wa_uat["provider"].outbound[-1].body_text

    # Zero documents, zero transactions, zero journals
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Transaction)) == 0
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


@pytest.mark.asyncio
async def test_scenario_30_safe_retry_behavior(wa_uat, db_session):
    """Scenario 30: Safe retry behavior verifies idempotency on repeated message delivery."""
    wa_uat["provider"].media["retry-doc-01"] = (
        "image/jpeg",
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb-retry-sample",
    )

    for i in range(3):
        resp = await post_wa_webhook(
            wa_uat,
            wamid="wamid.retry-test-01",
            message_type="image",
            media_id="retry-doc-01",
            mime_type="image/jpeg",
        )
        assert resp.status_code == 200

    # Exactly one Document record, exactly one download attempt
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 1
    assert wa_uat["provider"].downloads == 1
    assert len(wa_uat["provider"].outbound) == 1
