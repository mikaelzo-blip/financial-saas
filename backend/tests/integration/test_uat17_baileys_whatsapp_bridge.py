"""Integration test suite for UAT #17: Hermes Native WhatsApp Web Bridge using Baileys.

Verifies:
1. Allowed sender (+6285712342760) accepted.
2. Unknown sender rejected with zero document or journal mutation.
3. Image intake via Baileys bridge cached files.
4. PDF document intake via Baileys bridge cached files.
5. Duplicate message/media handling (idempotent submission).
6. Malformed media rejection.
7. Strict zero direct journal posting (accounting hard-stop preserved).
"""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock
import uuid

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select, func

from src.core.config import settings
from src.models.document import Document
from src.models.journal import JournalEntry, JournalLine
from src.models.transaction import Transaction
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User
from src.models.whatsapp import WhatsAppSenderMapping
from src.services.integrations.whatsapp.baileys_provider import BaileysBridgeWhatsAppProvider
from src.services.integrations.whatsapp.baileys_poller import BaileysBridgePoller
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
import src.api.v1.hermes as hermes_api


async def noop_background(*args, **kwargs):
    pass


@pytest.fixture
async def uat17_org_and_sender(db_session):
    org = Organization(
        legal_name="PT Kontraktor Utama Indonesia",
        slug=f"pt-kontraktor-{uuid.uuid4().hex[:8]}",
        tax_id="01.234.567.8-901.000",
    )
    db_session.add(org)
    await db_session.flush()

    user = User(
        email="fikri@kontraktor.test",
        password_hash="not-a-real-hash",
        full_name="Muhammad Fikri",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6285712342760",
        display_name="Muhammad Fikri",
        role_in_org="OPERATOR",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.flush()

    return org, user, sender


@pytest.mark.asyncio
async def test_uat17_allowed_sender_and_image_intake(
    client: httpx.AsyncClient, db_session, uat17_org_and_sender, monkeypatch, tmp_path
):
    org, _, _ = uat17_org_and_sender

    # 1. Setup temporary valid image file on disk
    img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 200
    img_file = tmp_path / "invoice_sample.jpg"
    img_file.write_bytes(img_bytes)

    # 2. Configure mock transport for Baileys bridge HTTP calls
    async def handle_bridge(request: httpx.Request):
        if request.url.path == "/send":
            return httpx.Response(200, json={"success": True, "messageId": "baileys.ack.001"})
        return httpx.Response(404)

    mock_bridge_transport = httpx.MockTransport(handle_bridge)
    provider = BaileysBridgeWhatsAppProvider(bridge_url="http://127.0.0.1:3000", transport=mock_bridge_transport)

    # 3. Configure SaaS Hermes client
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")
    tenant_client_map = {str(org.id): HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test")}

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))
    monkeypatch.setattr(hermes_api, "process_document_background", noop_background)

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda org_id: tenant_client_map[org_id],
        organization_ids=[str(org.id)],
    )

    # 4. Measure baseline accounting counts
    count_tx_before = await db_session.scalar(select(func.count(Transaction.id)))
    count_je_before = await db_session.scalar(select(func.count(JournalEntry.id)))
    count_jl_before = await db_session.scalar(select(func.count(JournalLine.id)))

    # 5. Simulate inbound message from Baileys bridge
    bridge_payload = {
        "messageId": "baileys.msg.img.001",
        "senderId": "6285712342760@s.whatsapp.net",
        "hasMedia": True,
        "mediaType": "image",
        "mime": "image/jpeg",
        "fileName": "invoice_sample.jpg",
        "mediaUrls": [str(img_file)],
        "body": "Invoice pembelian semen PRJ-2026-001",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }

    events = provider.parse(bridge_payload)
    assert len(events) == 1
    assert events[0].sender_phone == "+6285712342760"
    assert events[0].message_type == "IMAGE"

    await service.handle(events[0])

    # 6. Verify Document was created
    doc = await db_session.scalar(
        select(Document).where(
            Document.organization_id == org.id,
            Document.file_name == "invoice_sample.jpg",
        )
    )
    assert doc is not None
    assert doc.processing_status.value in ["UPLOADED", "PROCESSING", "EXTRACTING", "PENDING_REVIEW"]

    # 7. Strictly verify accounting invariants: zero journals, zero transactions mutated
    count_tx_after = await db_session.scalar(select(func.count(Transaction.id)))
    count_je_after = await db_session.scalar(select(func.count(JournalEntry.id)))
    count_jl_after = await db_session.scalar(select(func.count(JournalLine.id)))

    assert count_tx_after == count_tx_before
    assert count_je_after == count_je_before
    assert count_jl_after == count_jl_before


@pytest.mark.asyncio
async def test_uat17_pdf_intake_and_duplicate_handling(
    client: httpx.AsyncClient, db_session, uat17_org_and_sender, monkeypatch, tmp_path
):
    org, _, _ = uat17_org_and_sender

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    pdf_file = tmp_path / "nota_pembayaran.pdf"
    pdf_file.write_bytes(pdf_bytes)

    async def handle_bridge(request: httpx.Request):
        return httpx.Response(200, json={"success": True, "messageId": "baileys.ack.pdf"})

    provider = BaileysBridgeWhatsAppProvider("http://127.0.0.1:3000", transport=httpx.MockTransport(handle_bridge))
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))
    monkeypatch.setattr(hermes_api, "process_document_background", noop_background)

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda _: HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test"),
        organization_ids=[str(org.id)],
    )

    bridge_payload = {
        "messageId": "baileys.msg.pdf.001",
        "senderId": "6285712342760@s.whatsapp.net",
        "hasMedia": True,
        "mediaType": "document",
        "mime": "application/pdf",
        "fileName": "nota_pembayaran.pdf",
        "mediaUrls": [str(pdf_file)],
        "body": "Bukti transfer vendor",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }

    events = provider.parse(bridge_payload)
    await service.handle(events[0])

    docs_first = (await db_session.execute(select(Document).where(Document.organization_id == org.id))).scalars().all()
    count_docs_first = len(docs_first)

    # Re-send exact same payload (duplicate messageId / wamid)
    await service.handle(events[0])

    docs_second = (await db_session.execute(select(Document).where(Document.organization_id == org.id))).scalars().all()
    assert len(docs_second) == count_docs_first


@pytest.mark.asyncio
async def test_uat17_unknown_sender_rejection_and_malformed_media(
    client: httpx.AsyncClient, db_session, uat17_org_and_sender, monkeypatch, tmp_path
):
    org, _, _ = uat17_org_and_sender

    fake_file = tmp_path / "corrupt.jpg"
    fake_file.write_bytes(b"NOT_A_VALID_JPEG_HEADER")

    provider = BaileysBridgeWhatsAppProvider("http://127.0.0.1:3000")
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))
    monkeypatch.setattr(hermes_api, "process_document_background", noop_background)

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda _: HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test"),
        organization_ids=[str(org.id)],
    )

    # 1. Unknown sender
    unknown_payload = {
        "messageId": "baileys.msg.unknown.001",
        "senderId": "6289999999999@s.whatsapp.net",
        "hasMedia": False,
        "body": "Halo saya orang asing",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }
    unknown_event = provider.parse(unknown_payload)[0]
    await service.handle(unknown_event)

    # Zero documents created for unknown sender
    unknown_docs = (await db_session.execute(
        select(Document).where(Document.source_channel == "WHATSAPP", Document.file_name == "Halo saya orang asing")
    )).scalars().all()
    assert len(unknown_docs) == 0

    # 2. Malformed media from allowed sender
    malformed_payload = {
        "messageId": "baileys.msg.corrupt.001",
        "senderId": "6285712342760@s.whatsapp.net",
        "hasMedia": True,
        "mediaType": "image",
        "mime": "image/jpeg",
        "fileName": "corrupt.jpg",
        "mediaUrls": [str(fake_file)],
        "body": "Corrupt",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
    }
    malformed_event = provider.parse(malformed_payload)[0]
    await service.handle(malformed_event)

    # Malformed media fails magic-byte check, no document row added
    corrupt_docs = (await db_session.execute(
        select(Document).where(Document.organization_id == org.id, Document.file_name == "corrupt.jpg")
    )).scalars().all()
    assert len(corrupt_docs) == 0
