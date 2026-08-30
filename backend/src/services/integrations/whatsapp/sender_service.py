"""Resolve senders exclusively over the authenticated Hermes SaaS client."""
from src.schemas.whatsapp import SenderResponse


class WhatsAppSenderService:
    def __init__(self, gateway):
        self.gateway = gateway

    async def resolve(self, phone):
        result = await self.gateway.channel_request("resolve", {"phone_number": phone})
        return SenderResponse.model_validate(result["sender"]) if result["sender"] else None
