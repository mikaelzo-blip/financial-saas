"""Hermes native Baileys WhatsApp Web bridge transport provider.
Interacts with local Node.js Baileys bridge via HTTP endpoints.
Never touches accounting, database, or posting logic.
"""
from collections.abc import AsyncIterator
from datetime import datetime, timezone
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from src.schemas.whatsapp import InboundMessage, OutboundMessage
from .provider import MediaReference, ProviderError, WhatsAppProvider


class BaileysBridgeWhatsAppProvider(WhatsAppProvider):
    def __init__(self, bridge_url: str = "http://127.0.0.1:3000", *, transport=None):
        self._bridge_url = bridge_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=30.0)

    async def media_reference(self, media_id: str) -> MediaReference:
        """Resolve media reference from local file path or cache saved by Baileys bridge."""
        media_path = Path(media_id)
        if not media_path.is_absolute() or not media_path.exists():
            raise ProviderError("INVALID_MEDIA_ID")
        try:
            stat = media_path.stat()
            size = stat.st_size
            mime_type, _ = mimetypes.guess_type(str(media_path))
            if not mime_type:
                ext = media_path.suffix.lower()
                mime_map = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".pdf": "application/pdf",
                }
                mime_type = mime_map.get(ext, "application/octet-stream")
            return MediaReference(media_id=str(media_path), mime_type=mime_type, size_bytes=size, url=str(media_path))
        except Exception:
            raise ProviderError("DOWNLOAD_FAILED") from None

    async def stream_media(self, reference: MediaReference) -> AsyncIterator[bytes]:
        """Stream bytes directly from local file path cached by Baileys bridge."""
        path = Path(reference.media_id)
        if not path.is_file():
            raise ProviderError("DOWNLOAD_FAILED")
        chunk_size = 65536
        try:
            with open(path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk
        except Exception:
            raise ProviderError("DOWNLOAD_FAILED") from None

    async def send(self, message: OutboundMessage) -> str:
        """Send outbound text or interactive reply through Baileys HTTP bridge /send endpoint."""
        phone = message.recipient_phone.lstrip("+")
        chat_id = f"{phone}@s.whatsapp.net"
        payload: dict[str, Any] = {
            "chatId": chat_id,
            "message": message.body_text,
        }
        try:
            async with self._client() as client:
                res = await client.post(f"{self._bridge_url}/send", json=payload)
                res.raise_for_status()
                data = res.json()
                return str(data.get("messageId") or "baileys.msg")
        except httpx.HTTPError:
            raise ProviderError("DELIVERY_UNCONFIRMED") from None

    def parse(self, payload: dict) -> list[InboundMessage]:
        """Parse raw event payload from Baileys bridge into normalized InboundMessage DTOs."""
        raw_events = payload.get("messages")
        if raw_events is None:
            raw_events = [payload] if "messageId" in payload else []

        events: list[InboundMessage] = []
        for item in raw_events:
            msg_id = item.get("messageId")
            sender_id = item.get("senderId", "")
            if not msg_id or not sender_id:
                continue

            phone = sender_id.split("@")[0].split(":")[0]
            if not phone.isdigit():
                continue
            sender_phone = f"+{phone}"

            ts_raw = item.get("timestamp")
            if ts_raw:
                try:
                    ts = datetime.fromtimestamp(int(ts_raw), timezone.utc)
                except Exception:
                    ts = datetime.now(timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            has_media = item.get("hasMedia", False)
            media_type = (item.get("mediaType") or "").lower()
            media_urls = item.get("mediaUrls") or []
            file_name = item.get("fileName") or "document"
            mime_type = item.get("mime") or None

            if has_media:
                media_path = media_urls[0] if media_urls else None
                if not mime_type and media_path:
                    ext = Path(media_path).suffix.lower()
                    if ext in [".jpg", ".jpeg"]:
                        mime_type = "image/jpeg"
                    elif ext == ".png":
                        mime_type = "image/png"
                    elif ext == ".webp":
                        mime_type = "image/webp"
                    elif ext == ".pdf":
                        mime_type = "application/pdf"

                if "image" in media_type or mime_type in ["image/jpeg", "image/png", "image/webp"]:
                    msg_kind = "IMAGE"
                else:
                    msg_kind = "DOCUMENT"

                events.append(
                    InboundMessage(
                        wamid=msg_id,
                        sender_phone=sender_phone,
                        timestamp=ts,
                        message_type=msg_kind,
                        text=item.get("body", "") or "",
                        media_id=media_path,
                        mime_type=mime_type,
                        file_name=file_name,
                        reply_to=item.get("quotedMessageId"),
                    )
                )
            else:
                events.append(
                    InboundMessage(
                        wamid=msg_id,
                        sender_phone=sender_phone,
                        timestamp=ts,
                        message_type="TEXT",
                        text=item.get("body", "") or "",
                        media_id=None,
                        mime_type=None,
                        file_name="document",
                        reply_to=item.get("quotedMessageId"),
                    )
                )
        return events
