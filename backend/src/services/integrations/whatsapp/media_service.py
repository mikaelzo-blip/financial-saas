"""Bounded binary download. Only provider media IDs, never inbound URLs."""
import asyncio
from dataclasses import dataclass
import re

from .provider import ProviderError, WhatsAppProvider

PERMANENT_ERROR_CODES = {
    "UNSUPPORTED_MEDIA",
    "MEDIA_TOO_LARGE",
    "MIME_MISMATCH",
    "INVALID_MEDIA_ID",
}


@dataclass(frozen=True)
class DownloadedMedia:
    file_name: str
    mime_type: str
    content: bytes


class WhatsAppMediaService:
    TYPES = {
        "image/png": bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
        "image/jpeg": b"\xff\xd8\xff",
        "image/webp": b"RIFF",
        "application/pdf": b"%PDF-",
    }

    def __init__(self, provider: WhatsAppProvider, max_bytes: int = 25 * 1024 * 1024, max_attempts: int = 3, retry_delay: float = 0.05):
        self.provider = provider
        self.max_bytes = max_bytes
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay

    async def download(self, event, max_attempts: int | None = None, retry_delay: float | None = None) -> DownloadedMedia:
        if not event.media_id:
            raise ProviderError("DOWNLOAD_FAILED")

        attempts = max_attempts if max_attempts is not None else self.max_attempts
        delay = retry_delay if retry_delay is not None else self.retry_delay
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
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
            except ProviderError as pe:
                if pe.args and pe.args[0] in PERMANENT_ERROR_CODES:
                    raise
                last_error = pe
                if attempt < attempts:
                    await asyncio.sleep(delay * (2 ** (attempt - 1)))
            except Exception as exc:
                last_error = exc
                if attempt < attempts:
                    await asyncio.sleep(delay * (2 ** (attempt - 1)))

        raise ProviderError("DOWNLOAD_FAILED") from last_error
