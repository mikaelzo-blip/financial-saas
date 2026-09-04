import pytest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from pydantic import SecretStr
from sqlalchemy import select, func

from src.core.config import settings
from src.models.document import Document
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.whatsapp import WhatsAppSenderMapping
from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.schemas.whatsapp import InboundMessage
from src.services.integrations.whatsapp.baileys_provider import BaileysBridgeWhatsAppProvider
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.api.v1 import hermes as hermes_api


# 1. normal phone JID -> canonical phone works
def test_parse_normal_phone_jid():
    provider = BaileysBridgeWhatsAppProvider()
    payload = {
        "messageId": "msg_phone_1",
        "senderId": "6285712342760@s.whatsapp.net",
        "senderNumber": "6285712342760",
        "timestamp": 1725494400,
        "body": "Normal phone message",
        "hasMedia": False,
    }
    events = provider.parse(payload)
    assert len(events) == 1
    assert events[0].wamid == "msg_phone_1"
    assert events[0].sender_phone == "+6285712342760"


# 2. known LID -> canonical registered phone works (resolved senderPhone provided by bridge)
def test_parse_known_lid_with_resolved_phone():
    provider = BaileysBridgeWhatsAppProvider()
    payload = {
        "messageId": "msg_lid_1",
        "senderId": "241798068883662@lid",
        "senderNumber": "241798068883662",
        "senderPhone": "6285712342760",
        "timestamp": 1725494400,
        "body": "Known LID message",
        "hasMedia": False,
    }
    events = provider.parse(payload)
    assert len(events) == 1
    assert events[0].wamid == "msg_lid_1"
    assert events[0].sender_phone == "+6285712342760"


# 3. unknown/unresolved LID -> rejected (no senderPhone emitted or unresolved)
def test_parse_unknown_unresolved_lid_rejected():
    provider = BaileysBridgeWhatsAppProvider()
    payload = {
        "messageId": "msg_lid_unresolved",
        "senderId": "999999999999999@lid",
        "senderNumber": "999999999999999",
        "senderPhone": None,
        "timestamp": 1725494400,
        "body": "Unknown LID message",
        "hasMedia": False,
    }
    events = provider.parse(payload)
    assert len(events) == 0


# 4. malformed JID -> rejected
def test_parse_malformed_jid_rejected():
    provider = BaileysBridgeWhatsAppProvider()
    payloads = [
        {"messageId": "m1", "senderId": "invalid_jid", "body": "test"},
        {"messageId": "m2", "senderId": "@s.whatsapp.net", "body": "test"},
        {"messageId": "m3", "senderId": "abc@lid", "body": "test"},
    ]
    for p in payloads:
        assert len(provider.parse(p)) == 0


@pytest.fixture
async def test_org_and_sender(db_session):
    org = Organization(
        legal_name="PT Kontraktor Utama Indonesia",
        slug=f"pt-kontraktor-{uuid.uuid4().hex[:8]}",
        tax_id="01.234.567.8-901.000",
    )
    db_session.add(org)
    await db_session.flush()

    user = User(
        email=f"user-{uuid.uuid4().hex[:6]}@kontraktor.test",
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


# 5. allowlist remains enforced (sender service rejection when not registered)
@pytest.mark.asyncio
async def test_sender_authorization_rejects_unregistered_phone(
    client: httpx.AsyncClient, db_session, test_org_and_sender, monkeypatch
):
    org, _, _ = test_org_and_sender
    sent_outbound = []

    async def handle_bridge(request: httpx.Request):
        if request.url.path == "/send":
            sent_outbound.append(request.read())
            return httpx.Response(200, json={"success": True, "messageId": "ack.001"})
        return httpx.Response(404)

    mock_bridge_transport = httpx.MockTransport(handle_bridge)
    provider = BaileysBridgeWhatsAppProvider(bridge_url="http://127.0.0.1:3000", transport=mock_bridge_transport)
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")
    tenant_client_map = {str(org.id): HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test")}

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda org_id: tenant_client_map[org_id],
        organization_ids=[str(org.id)],
    )

    unregistered_event = InboundMessage(
        wamid="wamid.unregistered.001",
        sender_phone="+999999999999",
        timestamp=datetime.now(timezone.utc),
        message_type="TEXT",
        text="Halo",
    )

    await service.handle(unregistered_event)
    assert len(sent_outbound) == 1
    assert b"belum terdaftar" in sent_outbound[0]


# 6. no cross-tenant sender resolution
@pytest.mark.asyncio
async def test_no_cross_tenant_sender_resolution(
    client: httpx.AsyncClient, db_session, test_org_and_sender, monkeypatch
):
    org, _, _ = test_org_and_sender

    # Create another org
    other_org = Organization(
        legal_name="Other Org",
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(other_org)
    await db_session.flush()

    tenant_calls = []

    def tracking_tenant_client(org_id: str):
        tenant_calls.append(org_id)
        return HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test")

    async def handle_bridge(request: httpx.Request):
        return httpx.Response(200, json={"success": True, "messageId": "ack.001"})

    mock_bridge_transport = httpx.MockTransport(handle_bridge)
    provider = BaileysBridgeWhatsAppProvider(bridge_url="http://127.0.0.1:3000", transport=mock_bridge_transport)
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")

    monkeypatch.setattr(
        settings,
        "WHATSAPP_TENANT_TOKENS",
        {str(org.id): SecretStr("tenant-token"), str(other_org.id): SecretStr("other-token")},
    )
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=tracking_tenant_client,
        organization_ids=[str(org.id), str(other_org.id)],
    )

    valid_event = InboundMessage(
        wamid="wamid.valid.001",
        sender_phone="+6285712342760",
        timestamp=datetime.now(timezone.utc),
        message_type="TEXT",
        text="Status",
    )

    await service.handle(valid_event)
    # The call must target org.id, NEVER other_org.id
    assert str(org.id) in tenant_calls
    assert str(other_org.id) not in tenant_calls


# 7. duplicate events remain idempotent
@pytest.mark.asyncio
async def test_duplicate_events_idempotent(
    client: httpx.AsyncClient, db_session, test_org_and_sender, monkeypatch
):
    org, _, _ = test_org_and_sender
    sent_outbound = []

    async def handle_bridge(request: httpx.Request):
        if request.url.path == "/send":
            sent_outbound.append(request.read())
            return httpx.Response(200, json={"success": True, "messageId": "ack.001"})
        return httpx.Response(404)

    mock_bridge_transport = httpx.MockTransport(handle_bridge)
    provider = BaileysBridgeWhatsAppProvider(bridge_url="http://127.0.0.1:3000", transport=mock_bridge_transport)
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")
    tenant_client_map = {str(org.id): HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test")}

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda org_id: tenant_client_map[org_id],
        organization_ids=[str(org.id)],
    )

    event = InboundMessage(
        wamid="wamid.idempotent.test.001",
        sender_phone="+6285712342760",
        timestamp=datetime.now(timezone.utc),
        message_type="TEXT",
        text="Hello",
    )

    await service.handle(event)
    first_count = len(sent_outbound)

    # Process identical message again
    await service.handle(event)
    second_count = len(sent_outbound)

    # Must not send duplicate outbound reply or duplicate claim
    assert second_count == first_count


# 8. no direct accounting mutation occurs
@pytest.mark.asyncio
async def test_no_direct_accounting_mutation(
    client: httpx.AsyncClient, db_session, test_org_and_sender, monkeypatch
):
    org, _, _ = test_org_and_sender

    tx_count_before = await db_session.scalar(select(func.count(Transaction.id)))
    je_count_before = await db_session.scalar(select(func.count(JournalEntry.id)))
    jl_count_before = await db_session.scalar(select(func.count(JournalLine.id)))

    async def handle_bridge(request: httpx.Request):
        return httpx.Response(200, json={"success": True, "messageId": "ack.001"})

    mock_bridge_transport = httpx.MockTransport(handle_bridge)
    provider = BaileysBridgeWhatsAppProvider(bridge_url="http://127.0.0.1:3000", transport=mock_bridge_transport)
    saas_transport = HttpxHermesTransport("https://saas.test", transport=client._transport)
    gateway_client = HermesApiClient(saas_transport, lambda: "test-adapter-token", "https://saas.test")
    tenant_client_map = {str(org.id): HermesApiClient(saas_transport, lambda: "tenant-token", "https://saas.test")}

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-token")})
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter-token"))

    service = WhatsAppWebhookService(
        provider=provider,
        gateway=gateway_client,
        tenant_client=lambda org_id: tenant_client_map[org_id],
        organization_ids=[str(org.id)],
    )

    msg = InboundMessage(
        wamid="wamid.accounting.safety.001",
        sender_phone="+6285712342760",
        timestamp=datetime.now(timezone.utc),
        message_type="TEXT",
        text="Beli semen 50 sak Rp 2.500.000",
    )
    await service.handle(msg)

    tx_count_after = await db_session.scalar(select(func.count(Transaction.id)))
    je_count_after = await db_session.scalar(select(func.count(JournalEntry.id)))
    jl_count_after = await db_session.scalar(select(func.count(JournalLine.id)))

    assert tx_count_before == tx_count_after
    assert je_count_before == je_count_after
    assert jl_count_before == jl_count_after
