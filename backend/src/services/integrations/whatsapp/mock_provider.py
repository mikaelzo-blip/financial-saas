"""Offline provider with deterministic media and captured outbound messages."""
from uuid import uuid4

from src.schemas.whatsapp import OutboundMessage
from .provider import MediaReference, ProviderError, WhatsAppProvider


class MockWhatsAppProvider(WhatsAppProvider):
    def __init__(self):
        self.media: dict[str, tuple[str, bytes]] = {}
        self.outbound: list[OutboundMessage] = []
        self.downloads = 0

    async def media_reference(self, media_id: str) -> MediaReference:
        if media_id not in self.media:
            raise ProviderError("DOWNLOAD_FAILED")
        mime, content = self.media[media_id]
        return MediaReference(media_id, mime, len(content))

    async def stream_media(self, reference: MediaReference):
        self.downloads += 1
        content = self.media[reference.media_id][1]
        for offset in range(0, len(content), 65536):
            yield content[offset:offset + 65536]

    async def send(self, message: OutboundMessage) -> str:
        self.outbound.append(message)
        return "mock." + str(uuid4())
