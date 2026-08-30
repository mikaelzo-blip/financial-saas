import hashlib
import hmac
import json
import time

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select, func

from src.core.config import settings
from src.core.security import create_access_token
from src.models import Organization, User, UserRole, Document, WhatsAppMessageLog
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService


@pytest.fixture
async def wa(client, db_session, monkeypatch, tmp_path):
    from src.api.v1 import hermes
    organizations, users = [], []
    for name in ("alpha", "beta"):
        org = Organization(slug="wa-" + name, legal_name=name)
        db_session.add(org)
        await db_session.flush()
        user = User(organization_id=org.id, email=name + "@example.test", full_name=name, password_hash="unused", role=UserRole.ADMIN)
        db_session.add(user)
        await db_session.flush()
        organizations.append(org)
        users.append(user)
    await db_session.commit()
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("test-adapter"))
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_APP_SECRET", SecretStr("test-webhook"))
    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("test-tenant-" + str(i)) for i, org in enumerate(organizations)})
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    async def background(document_id):
        pass
    monkeypatch.setattr(hermes, "process_document_background", background)
    app = client._transport.app
    transport = HttpxHermesTransport("https://saas.test", transport=httpx.ASGITransport(app=app))
    gateway = HermesApiClient(transport, lambda: "test-adapter", "https://saas.test")
    def tenant_client(org):
        return HermesApiClient(transport, lambda: settings.WHATSAPP_TENANT_TOKENS[org].get_secret_value(), "https://saas.test")
    provider = MockWhatsAppProvider()
    provider.media["123"] = ("image/png", b"\x89PNG\r\n\x1a\nunique-whatsapp-image")
    service = WhatsAppWebhookService(provider, gateway, tenant_client, [str(o.id) for o in organizations])
    app.state.whatsapp_service = service
    phones = ["+6281234567890", "+6282222222222"]
    for user, phone in zip(users, phones):
        response = await client.post("/api/v1/integrations/whatsapp/senders", headers={"Authorization": "Bearer " + create_access_token(user.id), "X-Organization-ID": str(user.organization_id)}, json={"user_id": str(user.id), "phone_number": phone, "display_name": user.full_name, "role_in_org": "PROJECT_MANAGER"})
        assert response.status_code == 201, response.text
    return {"client": client, "provider": provider, "orgs": organizations, "users": users, "phones": phones, "service": service}


async def send(wa, *, phone=None, wamid="wamid.intake-0001", text=None, timestamp=None):
    message = {"id": wamid, "from": (phone or wa["phones"][0]).lstrip("+"), "timestamp": str(timestamp or int(time.time())), "type": "text" if text is not None else "image"}
    if text is None:
        message["image"] = {"id": "123", "mime_type": "image/png", "caption": "Nota 50 sak semen Proyek Ruko Thamrin"}
    else:
        message["text"] = {"body": text}
    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [message]}}]}]}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"test-webhook", body, hashlib.sha256).hexdigest()
    return await wa["client"].post("/api/v1/integrations/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": signature})


async def test_intake_caption_metadata_replay_and_hash_duplicate(wa, db_session):
    response = await send(wa)
    assert response.status_code == 200, response.text
    doc = await db_session.scalar(select(Document))
    assert doc.source_channel == "WHATSAPP"
    assert doc.organization_id == wa["orgs"][0].id
    assert doc.source_metadata["caption"] == "Nota 50 sak semen Proyek Ruko Thamrin"
    assert doc.source_metadata["wamid"] == "wamid.intake-0001"
    assert "Nota diterima" in wa["provider"].outbound[0].body_text
    assert (await send(wa)).status_code == 200
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].downloads == 1
    assert (await send(wa, wamid="wamid.same-content-0002")).status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 1
    assert "sebelumnya" in wa["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(WhatsAppMessageLog)) == 4


async def test_unknown_sender_and_tenant_isolation(wa, db_session):
    assert (await send(wa, phone="+6289999999999")).status_code == 200
    assert "belum terdaftar" in wa["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0
    for phone in wa["phones"]:
        assert (await send(wa, phone=phone, wamid="wamid.same-id-two-tenants")).status_code == 200
    docs = (await db_session.scalars(select(Document))).all()
    assert {d.organization_id for d in docs} == {o.id for o in wa["orgs"]}
    assert len(docs) == 2


async def test_mapping_requires_real_admin_and_tenant_match(wa):
    client, user = wa["client"], wa["users"][0]
    url = "/api/v1/integrations/whatsapp/senders"
    assert (await client.get(url, headers={"X-Organization-ID": str(user.organization_id)})).status_code == 401
    headers = {"Authorization": "Bearer " + create_access_token(user.id), "X-Organization-ID": str(wa["orgs"][1].id)}
    assert (await client.get(url, headers=headers)).status_code == 403
    headers["X-Organization-ID"] = str(user.organization_id)
    body = {"user_id": str(wa["users"][1].id), "phone_number": "+6281111111111", "display_name": "Other", "role_in_org": "OPERATOR"}
    assert (await client.post(url, headers=headers, json=body)).status_code == 400
    mappings = (await client.get(url, headers=headers)).json()
    assert len(mappings) == 1
    assert (await client.delete(url + "/" + mappings[0]["id"], headers=headers)).status_code == 204
    assert (await send(wa)).status_code == 200
    assert "belum terdaftar" in wa["provider"].outbound[-1].body_text


async def test_tenant_token_cannot_claim_other_sender(wa):
    event = {"wamid": "wamid.forged-claim", "sender_phone": wa["phones"][1], "timestamp": "2026-08-30T00:00:00Z", "message_type": "TEXT"}
    response = await wa["client"].post("/api/v1/hermes/whatsapp/messages/claim", headers={"Authorization": "Bearer test-tenant-0", "X-Organization-ID": str(wa["orgs"][1].id)}, json=event)
    assert response.status_code == 403
