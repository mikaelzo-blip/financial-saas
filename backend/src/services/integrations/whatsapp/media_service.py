"""Bounded binary download. Only provider media IDs, never inbound URLs."""
from dataclasses import dataclass
import re

from .provider import ProviderError, WhatsAppProvider


@dataclass(frozen=True)
class DownloadedMedia:
    file_name: str
    mime_type: str
    content: bytes


class WhatsAppMediaService:
    TYPES = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff", "image/webp": b"RIFF", "application/pdf": b"%PDF-"}

    def __init__(self, provider: WhatsAppProvider, max_bytes=25 * 1024 * 1024):
        self.provider, self.max_bytes = provider, max_bytes

    async def download(self, event) -> DownloadedMedia:
        if not event.media_id:
            raise ProviderError("DOWNLOAD_FAILED")
        reference = await self.provider.media_reference(event.media_id)
        if reference.mime_type not in self.TYPES or reference.mime_type != event.mime_type:
            raise ProviderError("UNSUPPORTED_MEDIA")
        if not 0 < reference.size_bytes <= self.max_bytes:
            raise ProviderError("MEDIA_TOO_LARGE")
        content = bytearray()
        async for chunk in self.provider.stream_media(reference):
            if len(content) + len(chunk) > self.max_bytes:
                raise ProviderError("MEDIA_TOO_LARGE")
            content.extend(chunk)
        if len(content) != reference.size_bytes or not content.startswith(self.TYPES[reference.mime_type]):
            raise ProviderError("MIME_MISMATCH")
        if reference.mime_type == "image/webp" and content[8:12] != b"WEBP":
            raise ProviderError("MIME_MISMATCH")
        name = event.file_name.replace("\\", "/").split("/")[-1]
        name = re.sub(r"[^\w. -]", "_", name).strip(". ")[:128] or "document"
        return DownloadedMedia(name, reference.mime_type, bytes(content))
