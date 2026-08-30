import pytest

from src.schemas.whatsapp import InboundMessage
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
from src.services.integrations.whatsapp.media_service import WhatsAppMediaService
from src.services.integrations.whatsapp.provider import ProviderError


def media_event(mime="image/png"):
    return InboundMessage(wamid="wamid.media-test", sender_phone="+6281234567890", timestamp="2026-08-30T00:00:00Z", message_type="IMAGE", media_id="1", mime_type=mime, file_name="../../evil.png")


async def test_media_limits_signature_and_filename():
    provider = MockWhatsAppProvider()
    provider.media["1"] = ("image/png", b"\x89PNG\r\n\x1a\nbytes")
    media = await WhatsAppMediaService(provider).download(media_event())
    assert media.file_name == "evil.png" and media.content.startswith(b"\x89PNG")
    with pytest.raises(ProviderError):
        await WhatsAppMediaService(provider, max_bytes=2).download(media_event())
    provider.media["1"] = ("image/png", b"executable")
    with pytest.raises(ProviderError):
        await WhatsAppMediaService(provider).download(media_event())
    provider.media["1"] = ("application/x-msdownload", b"MZ")
    with pytest.raises(ProviderError):
        await WhatsAppMediaService(provider).download(media_event("application/x-msdownload"))


@pytest.mark.parametrize("mime,content", [("image/jpeg", b"\xff\xd8\xffjpeg"), ("image/webp", b"RIFF0000WEBPdata"), ("application/pdf", b"%PDF-1.4")])
async def test_supported_media(mime, content):
    provider = MockWhatsAppProvider()
    provider.media["1"] = (mime, content)
    assert (await WhatsAppMediaService(provider).download(media_event(mime))).content == content
