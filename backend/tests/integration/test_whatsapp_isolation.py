import ast
from pathlib import Path
import time

from sqlalchemy import select, func

from tests.integration.test_whatsapp_intake_flow import wa, send
from tests.integration.test_whatsapp_clarification_flow import review_document
from src.models import Document, WhatsAppMessageLog, JournalEntry, WhatsAppSenderMapping


async def test_replay_window_and_rate_limit(wa, db_session):
    await send(wa, timestamp=int(time.time()) - 86401)
    await send(wa, timestamp=int(time.time()) + 400)
    assert not wa["provider"].outbound
    for i in range(22):
        await send(wa, wamid=f"wamid.rate-test-{i:04}", text="HELP")
    assert len(wa["provider"].outbound) == 21
    assert "tunggu" in wa["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0


async def test_cross_tenant_references_are_rejected(wa, db_session):
    doc, project = await review_document(wa, db_session)
    await send(wa, phone=wa["phones"][1], wamid="wamid.beta-text-0001", text="HELP")
    response = await wa["client"].post("/api/v1/hermes/whatsapp/messages/finish", headers={"Authorization": "Bearer test-tenant-1"}, json={
        "phone_number": wa["phones"][1], "wamid": "wamid.beta-text-0001", "delivery_status": "DELIVERED", "document_id": str(doc.id)})
    assert response.status_code == 404
    response = await wa["client"].post("/api/v1/hermes/whatsapp/notifications/claim", headers={"Authorization": "Bearer test-tenant-1"}, json={
        "phone_number": wa["phones"][1], "key": "result-" + str(doc.id), "document_id": str(doc.id), "body": "Forged"})
    assert response.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


def test_adapter_has_no_database_or_ledger_dependency():
    root = Path(__file__).parents[2] / "src/services/integrations/whatsapp"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any(any(term in name for term in ("sqlalchemy", "asyncpg", "psycopg", "core.database", "src.models", "accounting_engine", "transaction_service", "storage_service")) for name in imports), path


async def test_organization_limit_and_unconfirmed_send_not_retried(wa, db_session, monkeypatch):
    from src.services.integrations.whatsapp.provider import ProviderError
    wa["service"].org_limit = 1
    await send(wa, wamid="one", text="HELP")
    await send(wa, wamid="two", text="HELP")
    assert "tunggu" in wa["provider"].outbound[-1].body_text
    calls = []
    async def uncertain(message):
        calls.append(message)
        raise ProviderError("DELIVERY_UNCONFIRMED")
    monkeypatch.setattr(wa["provider"], "send", uncertain)
    wa["service"].org_limit = 200
    await send(wa, wamid="uncertain", text="HELP")
    await send(wa, wamid="uncertain", text="HELP")
    assert len(calls) == 1
    failed = await db_session.scalar(select(WhatsAppMessageLog).where(WhatsAppMessageLog.direction == "OUTBOUND", WhatsAppMessageLog.delivery_status == "FAILED"))
    assert failed is not None
