"""Integration tests for Real Meta WhatsApp Cloud API Sandbox Pilot (UAT #16)."""
import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from src.api.v1 import hermes
from src.core.config import Settings, settings
from src.core.database import get_db
from src.models.coa import ChartOfAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.hermes import HermesSubmission
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.project import Project
from src.models.user import User
from src.models.whatsapp import WhatsAppSenderMapping
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.integrations.whatsapp.meta_provider import MetaCloudWhatsAppProvider
from src.services.integrations.whatsapp.provider import MediaReference, ProviderError
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.reporting.integrity_service import IntegrityService


def make_hub_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_uat16_webhook_verification_handshake(client: httpx.AsyncClient, monkeypatch):
    """GET webhook must process Meta hub.challenge verification correctly and fail-closed on invalid token."""
    verify_secret = "meta-sandbox-verify-secret-token-123"
    monkeypatch.setattr(settings, "META_VERIFY_TOKEN", SecretStr(verify_secret))
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", None)

    # 1. Valid handshake
    res = await client.get(
        "/api/v1/integrations/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": verify_secret,
            "hub.challenge": "1158201444",
        },
    )
    assert res.status_code == 200
    assert res.text == "1158201444"

    # 2. Invalid verify token
    res_bad = await client.get(
        "/api/v1/integrations/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "1158201444",
        },
    )
    assert res_bad.status_code == 403

    # 3. Invalid mode
    res_bad_mode = await client.get(
        "/api/v1/integrations/whatsapp/webhook",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": verify_secret,
            "hub.challenge": "1158201444",
        },
    )
    assert res_bad_mode.status_code == 403


@pytest.mark.asyncio
async def test_uat16_webhook_signature_validation_and_fail_closed(client: httpx.AsyncClient, monkeypatch):
    """POST webhook must verify x-hub-signature-256 using META_APP_SECRET and fail-closed on tampered signatures."""
    app_secret = "meta-sandbox-app-secret-abc-xyz-789"
    monkeypatch.setattr(settings, "META_APP_SECRET", SecretStr(app_secret))
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_APP_SECRET", None)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10000001",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550234567",
                                "phone_number_id": "10987654321",
                            },
                            "messages": [
                                {
                                    "from": "628111111111",
                                    "id": "wamid.HBgLMjAyNjA5MDMAAgASGBQzQUExMjM0NTY3ODkwMTIzNDU2NwA=",
                                    "timestamp": "1788426000",
                                    "type": "text",
                                    "text": {"body": "SALDO"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # 1. Missing signature -> 401
    res_missing = await client.post("/api/v1/integrations/whatsapp/webhook", content=raw_body)
    assert res_missing.status_code == 401

    # 2. Tampered / invalid signature -> 401
    res_tampered = await client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
    )
    assert res_tampered.status_code == 401

    # 3. Malformed signature header -> 401
    res_malformed = await client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_body,
        headers={"X-Hub-Signature-256": "invalid_sig_without_prefix"},
    )
    assert res_malformed.status_code == 401


@pytest.mark.asyncio
async def test_uat16_real_meta_cloud_api_adapter_media_intake_and_review_hardstop(
    client: httpx.AsyncClient, db_session, monkeypatch, tmp_path
):
    """Verify real Meta Cloud API adapter: media download, hash, intake, zero journal creation."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    # Tenant setup
    org = Organization(slug=f"uat16-org-{uuid.uuid4().hex[:6]}", legal_name="PT Meta Sandbox Pilot")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"pilot-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="test-hash",
        full_name="Sandbox Operator",
        role="OPERATOR",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6281234567890",
        display_name="Sandbox Field Operator",
        role_in_org="OPERATOR",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    # Meta config
    app_secret = "meta-test-app-secret-123456"
    verify_token = "meta-test-verify-token-abcdef"
    api_token = "EAABtest-meta-cloud-access-token"
    phone_id = "109876543210123"

    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
    monkeypatch.setattr(settings, "META_APP_SECRET", SecretStr(app_secret))
    monkeypatch.setattr(settings, "META_VERIFY_TOKEN", SecretStr(verify_token))
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", SecretStr(api_token))
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", phone_id)
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-secret-token"))
    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-secret-token")})

    # Fake Meta Cloud API Graph Transport
    fake_jpg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    media_id = "998877665544332"
    wamid = f"wamid.HBgLMjAyNjA5MDMAAgASGBQ{uuid.uuid4().hex[:20]}A="

    async def mock_meta_graph_handler(request: httpx.Request):
        url_str = str(request.url)
        # Graph API media metadata query
        if f"/v26.0/{media_id}" in url_str:
            assert request.headers.get("Authorization") == f"Bearer {api_token}"
            return httpx.Response(
                200,
                json={
                    "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/sandbox_transfer_proof.jpg",
                    "mime_type": "image/jpeg",
                    "sha256": hashlib.sha256(fake_jpg_content).hexdigest(),
                    "file_size": len(fake_jpg_content),
                    "id": media_id,
                    "messaging_product": "whatsapp",
                },
            )
        # Media binary download from lookaside CDN
        if "lookaside.fbsbx.com" in url_str:
            assert request.headers.get("Authorization") == f"Bearer {api_token}"
            return httpx.Response(
                200,
                content=fake_jpg_content,
                headers={"Content-Type": "image/jpeg"},
            )
        # Outbound receipt message
        if f"/v26.0/{phone_id}/messages" in url_str:
            return httpx.Response(
                200,
                json={"messaging_product": "whatsapp", "contacts": [{"input": "6281234567890", "wa_id": "6281234567890"}], "messages": [{"id": f"wamid.outbound.{uuid.uuid4().hex}"}]},
            )
        return httpx.Response(404)

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

    # Initialize Meta provider with MockTransport
    mock_transport = httpx.MockTransport(mock_meta_graph_handler)
    meta_provider = MetaCloudWhatsAppProvider(
        SecretStr(api_token), phone_id, version="v26.0", transport=mock_transport
    )

    saas_transport = HttpxHermesTransport("https://saas.test", transport=httpx.ASGITransport(app=app))
    gateway = HermesApiClient(saas_transport, lambda: "adapter-secret-token", "https://saas.test")
    def tenant_client_fn(org_id_str):
        return HermesApiClient(saas_transport, lambda: "tenant-secret-token", "https://saas.test")

    service = WhatsAppWebhookService(
        meta_provider, gateway, tenant_client_fn, [str(org.id)], 200
    )
    app.state.whatsapp_service = service

    # Record baseline journals
    initial_journals = (await db_session.execute(select(JournalEntry).where(JournalEntry.organization_id == org.id))).scalars().all()
    assert len(initial_journals) == 0

    timestamp_now = str(int(datetime.now(timezone.utc).timestamp()))
    # Inbound Webhook Payload
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10000001",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550234567",
                                "phone_number_id": phone_id,
                            },
                            "messages": [
                                {
                                    "from": "6281234567890",
                                    "id": wamid,
                                    "timestamp": timestamp_now,
                                    "type": "image",
                                    "image": {
                                        "caption": "Bukti Transfer Pembayaran Material Proyek",
                                        "mime_type": "image/jpeg",
                                        "sha256": hashlib.sha256(fake_jpg_content).hexdigest(),
                                        "id": media_id,
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    valid_sig = make_hub_signature(raw_payload_bytes, app_secret)

    # Post to Webhook
    res = await client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_payload_bytes,
        headers={"X-Hub-Signature-256": valid_sig},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "success"}

    # Assert Document and HermesSubmission created with source_channel=WHATSAPP
    docs = (await db_session.execute(select(Document).where(Document.organization_id == org.id))).scalars().all()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.source_channel == "WHATSAPP"
    assert doc.file_hash == hashlib.sha256(fake_jpg_content).hexdigest()
    assert doc.processing_status in {"PENDING_REVIEW", "UNPROCESSED", "EXTRACTING"}

    submissions = (await db_session.execute(select(HermesSubmission).where(HermesSubmission.organization_id == org.id))).scalars().all()
    assert len(submissions) == 1
    assert submissions[0].outcome_status == "ACCEPTED"
    assert submissions[0].document_id == doc.id

    # HARD STOP: Verify Journal delta == 0
    after_journals = (await db_session.execute(select(JournalEntry).where(JournalEntry.organization_id == org.id))).scalars().all()
    assert len(after_journals) == 0, "Hard stop violated: journal created directly from WhatsApp webhook!"


@pytest.mark.asyncio
async def test_uat16_replay_deduplication_and_zero_duplicate_journals(
    client: httpx.AsyncClient, db_session, monkeypatch, tmp_path
):
    """Replaying the same Meta webhook must be idempotent: 0 duplicate docs, 0 duplicate journals."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    org = Organization(slug=f"uat16-dup-{uuid.uuid4().hex[:6]}", legal_name="PT Replay Deduplication Pilot")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"dup-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="test-hash",
        full_name="Duplicate Tester",
        role="OPERATOR",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6281987654321",
        display_name="Replay Tester",
        role_in_org="OPERATOR",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    app_secret = "meta-dup-secret"
    api_token = "EAABdup-token"
    phone_id = "109876543210999"

    monkeypatch.setattr(settings, "WHATSAPP_PROVIDER", "meta")
    monkeypatch.setattr(settings, "META_APP_SECRET", SecretStr(app_secret))
    monkeypatch.setattr(settings, "META_ACCESS_TOKEN", SecretStr(api_token))
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", phone_id)
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-secret-token"))
    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-secret-token")})

    fake_pdf = b"%PDF-1.4\n1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n2 0 obj<</Type /Pages /Kids[3 0 R] /Count 1>>endobj\n3 0 obj<</Type /Page /Parent 2 0 R /MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
    media_id = "554433221100"
    wamid = f"wamid.HBgLMjAyNjA5MDMAAgASGBQ{uuid.uuid4().hex[:20]}A="

    async def mock_meta_graph_handler(request: httpx.Request):
        url_str = str(request.url)
        if f"/v26.0/{media_id}" in url_str:
            return httpx.Response(
                200,
                json={
                    "url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/sandbox_invoice.pdf",
                    "mime_type": "application/pdf",
                    "sha256": hashlib.sha256(fake_pdf).hexdigest(),
                    "file_size": len(fake_pdf),
                    "id": media_id,
                },
            )
        if "lookaside.fbsbx.com" in url_str:
            return httpx.Response(200, content=fake_pdf, headers={"Content-Type": "application/pdf"})
        if f"/v26.0/{phone_id}/messages" in url_str:
            return httpx.Response(200, json={"messages": [{"id": f"wamid.outbound.{uuid.uuid4().hex}"}]})
        return httpx.Response(404)

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

    mock_transport = httpx.MockTransport(mock_meta_graph_handler)
    meta_provider = MetaCloudWhatsAppProvider(SecretStr(api_token), phone_id, version="v26.0", transport=mock_transport)

    saas_transport = HttpxHermesTransport("https://saas.test", transport=httpx.ASGITransport(app=app))
    gateway = HermesApiClient(saas_transport, lambda: "adapter-secret-token", "https://saas.test")
    def tenant_client_fn(org_id_str):
        return HermesApiClient(saas_transport, lambda: "tenant-secret-token", "https://saas.test")

    service = WhatsAppWebhookService(meta_provider, gateway, tenant_client_fn, [str(org.id)], 200)
    app.state.whatsapp_service = service

    timestamp_now = str(int(datetime.now(timezone.utc).timestamp()))
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "10000001",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550234567", "phone_number_id": phone_id},
                            "messages": [
                                {
                                    "from": "6281987654321",
                                    "id": wamid,
                                    "timestamp": timestamp_now,
                                    "type": "document",
                                    "document": {
                                        "caption": "Invoice Pembelian Semen",
                                        "filename": "invoice_semen.pdf",
                                        "mime_type": "application/pdf",
                                        "sha256": hashlib.sha256(fake_pdf).hexdigest(),
                                        "id": media_id,
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_payload_bytes = json.dumps(webhook_payload).encode("utf-8")
    valid_sig = make_hub_signature(raw_payload_bytes, app_secret)

    # First delivery
    res1 = await client.post("/api/v1/integrations/whatsapp/webhook", content=raw_payload_bytes, headers={"X-Hub-Signature-256": valid_sig})
    assert res1.status_code == 200

    docs1 = (await db_session.execute(select(Document).where(Document.organization_id == org.id))).scalars().all()
    assert len(docs1) == 1

    # Replay identical webhook
    res2 = await client.post("/api/v1/integrations/whatsapp/webhook", content=raw_payload_bytes, headers={"X-Hub-Signature-256": valid_sig})
    assert res2.status_code == 200

    docs2 = (await db_session.execute(select(Document).where(Document.organization_id == org.id))).scalars().all()
    assert len(docs2) == 1, "Duplicate document created on identical wamid replay"

    journals = (await db_session.execute(select(JournalEntry).where(JournalEntry.organization_id == org.id))).scalars().all()
    assert len(journals) == 0, "Duplicate journal created on replay"


def test_uat16_pc_offline_model_and_production_edge_architecture():
    """Verify offline model documentation and edge gateway requirement specifications."""
    guide_path = "docs/meta-whatsapp-sandbox-pilot-guide.md"
    with open(guide_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "cloudflared tunnel" in content or "ngrok" in content
    assert "Review Queue Hard-Stop" in content
    assert "hub.challenge" in content
    assert "x-hub-signature-256" in content
    assert "PC Offline & Production Architecture Guidance" in content
