from unittest.mock import AsyncMock
from uuid import uuid4
from types import SimpleNamespace

from src.services.integrations.whatsapp.clarification_service import WhatsAppClarificationService


async def test_session_bound_button_and_expiry_use_api():
    session_id = str(uuid4())
    service = WhatsAppClarificationService()
    assert service.parse_reply(session_id + ":1") == (session_id, "1")
    assert service.parse_reply("invalid:1") == (None, "invalid:1")
    client = AsyncMock()
    client.channel_request.return_value = {"reply": "Updated"}
    event = SimpleNamespace(sender_phone="+6281234567890", text=session_id + ":1")
    assert await service.reply(event, client) == "Updated"
    client.channel_request.assert_awaited_with("clarifications/reply", {"phone_number": event.sender_phone, "text": "1", "session_id": session_id})
    await service.expire(client)
    client.channel_request.assert_awaited_with("clarifications/expire", {})
