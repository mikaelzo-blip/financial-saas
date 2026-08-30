"""Provider-neutral transport. It has no persistence or accounting dependency."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

from src.schemas.whatsapp import InboundMessage, OutboundMessage


class ProviderError(Exception):
    """Safe code only: never include tokens, URLs, or provider response bodies."""


@dataclass(frozen=True)
class MediaReference:
    media_id: str
    mime_type: str
    size_bytes: int
    url: str = ""


class WhatsAppProvider(ABC):
    @abstractmethod
    async def media_reference(self, media_id: str) -> MediaReference: ...

    @abstractmethod
    def stream_media(self, reference: MediaReference) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> str: ...

    def parse(self, payload: dict) -> list[InboundMessage]:
        if payload.get("object") != "whatsapp_business_account":
            raise ValueError("Unsupported webhook object")
        events = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for item in change.get("value", {}).get("messages", []):
                    kind = item["type"]
                    if kind not in {"image", "document", "text", "interactive", "button"}:
                        continue
                    media = item.get(kind, {})
                    text = media.get("caption", "") if kind in {"image", "document"} else media.get("body", "")
                    if kind == "interactive":
                        text = (media.get("button_reply") or media.get("list_reply") or {}).get("id", "")
                    if kind == "button":
                        text = media.get("payload", "")
                    events.append(InboundMessage(
                        wamid=item["id"], sender_phone="+" + item["from"].lstrip("+"),
                        timestamp=datetime.fromtimestamp(int(item["timestamp"]), timezone.utc),
                        message_type="INTERACTIVE_REPLY" if kind in {"interactive", "button"} else kind.upper(),
                        text=text, media_id=media.get("id") if kind in {"image", "document"} else None,
                        mime_type=media.get("mime_type"), file_name=media.get("filename", "document"),
                        reply_to=item.get("context", {}).get("id"),
                    ))
        return events
