import hashlib
import hmac

import pytest
from pydantic import SecretStr

from src.core.config import Settings
from src.services.integrations.whatsapp.security import valid_signature, valid_handshake
from src.services.integrations.whatsapp.meta_provider import MetaCloudWhatsAppProvider
from src.services.integrations.whatsapp.provider import ProviderError


def test_signature_covers_exact_raw_bytes():
    body = b'{"entry":[]}'
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert valid_signature(body, signature, "test-secret")
    assert not valid_signature(body + b" ", signature, "test-secret")
    assert not valid_signature(body, signature, "other-secret")
    for bad in (None, "", "sha256=abc", "sha1=" + "0" * 64, "\u2603"):
        assert not valid_signature(body, bad, "test-secret")
    assert not valid_signature(body, signature, None)


def test_handshake_and_secrets_fail_closed():
    assert valid_handshake("subscribe", "test", "test")
    assert not valid_handshake("unsubscribe", "test", "test")
    assert not valid_handshake("subscribe", "wrong", "test")
    assert not valid_handshake("subscribe", "", None)
    config = Settings(_env_file=None, WHATSAPP_API_TOKEN="not-a-real-token")
    assert "not-a-real-token" not in repr(config)
    assert config.WHATSAPP_PROVIDER == "mock"


@pytest.mark.parametrize("url", ["http://lookaside.fbsbx.com/a", "https://localhost/a", "https://127.0.0.1/a", "https://lookaside.fbsbx.com.evil.test/a", "https://user:password@lookaside.fbsbx.com/a", "https://lookaside.fbsbx.com:444/a"])
def test_provider_url_rejects_ssrf(url):
    with pytest.raises(ProviderError):
        MetaCloudWhatsAppProvider.validate_media_url(url)


def test_provider_prerequisites():
    with pytest.raises(ValueError):
        MetaCloudWhatsAppProvider(SecretStr(""), "123")
    MetaCloudWhatsAppProvider.validate_media_url("https://lookaside.fbsbx.com/whatsapp_business/attachments/a")


async def test_http_handshake_and_auth_before_payload(client, monkeypatch):
    from src.core.config import settings
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", SecretStr("test-verify"))
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_APP_SECRET", SecretStr("test-secret"))
    response = await client.get("/api/v1/integrations/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify", "hub.challenge": "88991122"})
    assert response.status_code == 200 and response.text == "88991122"
    assert (await client.get("/api/v1/integrations/whatsapp/webhook")).status_code == 403
    response = await client.post("/api/v1/integrations/whatsapp/webhook", content=b"not-json")
    assert response.status_code == 401
    body = b"{}"
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = await client.post("/api/v1/integrations/whatsapp/webhook", content=body, headers={"X-Hub-Signature-256": signature})
    assert response.status_code == 503  # No accidental provider activation.


async def test_mock_provider_and_meta_contract_offline():
    import httpx
    from src.schemas.whatsapp import OutboundMessage
    from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
    mock = MockWhatsAppProvider()
    mock.media["1"] = ("image/png", b"png-bytes")
    reference = await mock.media_reference("1")
    assert b"".join([chunk async for chunk in mock.stream_media(reference)]) == b"png-bytes"
    message = OutboundMessage(recipient_phone="+6281234567890", body_text="Received")
    assert (await mock.send(message)).startswith("mock.")
    assert mock.outbound == [message]

    def handle(request):
        assert request.headers["Authorization"] == "Bearer test-provider-secret"
        if request.url.path.endswith("messages"):
            return httpx.Response(200, json={"messages": [{"id": "out.1"}]})
        if request.url.host == "graph.facebook.com":
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/media", "mime_type": "image/png", "file_size": 3})
        return httpx.Response(200, content=b"png", headers={"content-type": "image/png"})
    meta = MetaCloudWhatsAppProvider(SecretStr("test-provider-secret"), "123", transport=httpx.MockTransport(handle))
    reference = await meta.media_reference("1")
    assert b"".join([chunk async for chunk in meta.stream_media(reference)]) == b"png"
    assert await meta.send(message) == "out.1"
