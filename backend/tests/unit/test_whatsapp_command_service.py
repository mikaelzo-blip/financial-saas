from unittest.mock import AsyncMock
from types import SimpleNamespace

from src.services.integrations.whatsapp.command_service import WhatsAppCommandService


async def test_safe_command_allowlist_and_authorization():
    client = AsyncMock()
    client.channel_request.return_value = {"documents": 7, "pending_review": 3, "active_projects": 2}
    commands = WhatsAppCommandService()
    operator = SimpleNamespace(role_in_org="OPERATOR", phone_number="+6281234567890")
    assert "izin" in await commands.reply("STATUS", operator, client)
    client.channel_request.assert_not_awaited()
    manager = SimpleNamespace(role_in_org="PROJECT_MANAGER", phone_number=operator.phone_number)
    assert "3" in await commands.reply("  ringkasan ", manager, client)
    client.reset_mock()
    for command in ("POST", "APPROVE", "DELETE HISTORY", "debit 100 credit 100", "STATUS; DROP TABLE"):
        assert "SaaS" in await commands.reply(command, manager, client)
    client.channel_request.assert_not_awaited()
