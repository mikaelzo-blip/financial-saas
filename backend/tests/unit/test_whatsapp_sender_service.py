from unittest.mock import AsyncMock
from uuid import uuid4

from src.services.integrations.whatsapp.sender_service import WhatsAppSenderService


async def test_sender_resolution_is_api_only():
    gateway = AsyncMock()
    gateway.channel_request.return_value = {"sender": None}
    assert await WhatsAppSenderService(gateway).resolve("+6281234567890") is None
    gateway.channel_request.assert_awaited_once_with("resolve", {"phone_number": "+6281234567890"})
    gateway.channel_request.return_value = {"sender": {"id": str(uuid4()), "organization_id": str(uuid4()), "user_id": str(uuid4()), "phone_number": "+6281234567890", "display_name": "Operator", "role_in_org": "OPERATOR", "is_active": True, "created_at": "2026-08-30T00:00:00Z"}}
    sender = await WhatsAppSenderService(gateway).resolve("+6281234567890")
    assert sender.role_in_org == "OPERATOR"
