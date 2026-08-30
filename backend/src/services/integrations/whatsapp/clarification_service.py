"""API-only conversational state machine. SaaS validates and owns session state."""
import uuid


class WhatsAppClarificationService:
    @staticmethod
    def parse_reply(text):
        if ":" in text:
            session, choice = text.split(":", 1)
            try:
                return str(uuid.UUID(session)), choice
            except ValueError:
                return None, text
        return None, text.strip()

    async def reply(self, event, client):
        session, choice = self.parse_reply(event.text)
        result = await client.channel_request("clarifications/reply", {"phone_number": event.sender_phone, "text": choice, "session_id": session})
        return result.get("reply")

    async def expire(self, client):
        return await client.channel_request("clarifications/expire", {})
