from src.schemas.whatsapp import OutboundMessage


class WhatsAppOutboundService:
    def __init__(self, provider):
        self.provider = provider

    async def text(self, phone, body, buttons=None):
        return await self.provider.send(OutboundMessage(recipient_phone=phone, body_text=body, buttons=buttons or []))

    @staticmethod
    def receipt(outcome=None):
        return "Oke, saya catat."
