"""Dormant Meta transport. Construction requires explicit runtime credentials."""
import re
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from src.schemas.whatsapp import OutboundMessage
from .provider import MediaReference, ProviderError, WhatsAppProvider


class MetaCloudWhatsAppProvider(WhatsAppProvider):
    def __init__(self, token: SecretStr, phone_number_id: str, version: str = "v20.0", *, transport=None):
        if not token.get_secret_value() or not phone_number_id.isdigit() or not re.fullmatch(r"v[0-9]+\.0", version):
            raise ValueError("Meta provider prerequisites are missing or invalid")
        self._token, self._phone, self._version = token, phone_number_id, version
        self._transport = transport

    def _client(self):
        return httpx.AsyncClient(transport=self._transport, timeout=10, follow_redirects=False)

    def _headers(self):
        return {"Authorization": "Bearer " + self._token.get_secret_value()}

    @staticmethod
    def validate_media_url(url: str):
        parsed = urlsplit(url)
        # Exact provider host, not arbitrary URLs supplied in webhook payloads.
        if parsed.scheme != "https" or parsed.hostname != "lookaside.fbsbx.com" or parsed.port not in {None, 443} or parsed.username or parsed.password or parsed.fragment:
            raise ProviderError("UNSAFE_MEDIA_URL")

    async def media_reference(self, media_id: str) -> MediaReference:
        if not media_id.isdigit():
            raise ProviderError("INVALID_MEDIA_ID")
        try:
            async with self._client() as client:
                response = await client.get(f"https://graph.facebook.com/{self._version}/{media_id}", headers=self._headers())
                response.raise_for_status()
                data = response.json()
                self.validate_media_url(data["url"])
                return MediaReference(media_id, data["mime_type"], int(data["file_size"]), data["url"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError("DOWNLOAD_FAILED") from None

    async def stream_media(self, reference: MediaReference):
        self.validate_media_url(reference.url)
        try:
            async with self._client() as client:
                async with client.stream("GET", reference.url, headers=self._headers()) as response:
                    response.raise_for_status()
                    if response.headers.get("content-type", "").split(";")[0] != reference.mime_type:
                        raise ProviderError("MIME_MISMATCH")
                    async for chunk in response.aiter_bytes(65536):
                        yield chunk
        except httpx.HTTPError:
            raise ProviderError("DOWNLOAD_FAILED") from None

    async def send(self, message: OutboundMessage) -> str:
        payload = {"messaging_product": "whatsapp", "to": message.recipient_phone, "type": "text", "text": {"body": message.body_text}}
        if message.buttons:
            payload = {"messaging_product": "whatsapp", "to": message.recipient_phone, "type": "interactive", "interactive": {
                "type": "button", "body": {"text": message.body_text},
                "action": {"buttons": [{"type": "reply", "reply": b} for b in message.buttons]},
            }}
        try:
            async with self._client() as client:
                response = await client.post(f"https://graph.facebook.com/{self._version}/{self._phone}/messages", headers=self._headers(), json=payload)
                response.raise_for_status()
                return response.json()["messages"][0]["id"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            # Do not blindly retry outbound POST: a timeout may mean it was sent.
            raise ProviderError("DELIVERY_UNCONFIRMED") from None
