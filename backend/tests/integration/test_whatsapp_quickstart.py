"""Executable acceptance scenarios A-F; all provider and HTTP traffic is local."""
import asyncio
import uuid
import time

from pydantic import SecretStr
from sqlalchemy import select, func

from tests.integration.test_whatsapp_intake_flow import wa, send
from tests.integration.test_whatsapp_clarification_flow import review_document
from src.core.config import settings
from src.models import Document, WhatsAppClarificationSession, JournalEntry, WhatsAppMessageLog


async def test_quickstart_a_handshake(wa, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", SecretStr("test_verify_token_123"))
    response = await wa["client"].get("/api/v1/integrations/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "test_verify_token_123", "hub.challenge": "88991122"})
    assert response.status_code == 200 and response.text == "88991122"


async def test_quickstart_b_intake_and_c_replay(wa, db_session):
    started = time.monotonic()
    responses = await asyncio.gather(send(wa), send(wa))
    assert time.monotonic() - started < 3  # Approved local/mock normal-network acceptance budget.
    assert all(response.status_code == 200 for response in responses)
    docs = (await db_session.scalars(select(Document))).all()
    assert len(docs) == 1
    assert docs[0].source_channel == "WHATSAPP"
    assert docs[0].source_metadata["caption"] == "Nota 50 sak semen Proyek Ruko Thamrin"
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].downloads == 1


async def test_quickstart_d_unknown_sender(wa, db_session):
    await send(wa, phone="+6289999999999")
    await send(wa, phone="+6289999999999")
    assert len(wa["provider"].outbound) == 1
    assert "belum terdaftar" in wa["provider"].outbound[0].body_text
    assert await db_session.scalar(select(func.count()).select_from(Document)) == 0
    logs = (await db_session.scalars(select(WhatsAppMessageLog))).all()
    assert len(logs) == 2
    assert all(log.organization_id is None and log.document_id is None for log in logs)
    wa["service"]._rejected.clear()  # A process restart cannot replay the persisted notice.
    await send(wa, phone="+6289999999999")
    assert len(wa["provider"].outbound) == 1


async def test_quickstart_e_clarification(wa, db_session):
    doc, project = await review_document(wa, db_session)
    await send(wa, wamid="wamid.quickstart-e", text="1")
    session = await db_session.scalar(select(WhatsAppClarificationSession))
    assert session.status == "ANSWERED"
    await db_session.refresh(doc)
    assert doc.candidate_transaction["project_id"] == str(project.id)
    assert "proyek berhasil diperbarui" in wa["provider"].outbound[-1].body_text
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0


async def test_quickstart_f_simultaneous_tenants(wa, db_session):
    responses = await asyncio.gather(*(send(wa, phone=phone, wamid="wamid.quickstart-f") for phone in wa["phones"]))
    assert all(response.status_code == 200 for response in responses)
    docs = (await db_session.scalars(select(Document))).all()
    assert len(docs) == 2
    assert {doc.organization_id for doc in docs} == {org.id for org in wa["orgs"]}
    alpha_doc = next(doc for doc in docs if doc.organization_id == wa["orgs"][0].id)
    authorized = await wa["client"].post("/api/v1/hermes/whatsapp/documents/get", headers={"Authorization": "Bearer test-tenant-0"}, json={"document_id": str(alpha_doc.id), "phone_number": wa["phones"][0]})
    assert authorized.status_code == 200 and authorized.json()["document_id"] == str(alpha_doc.id)
    response = await wa["client"].post("/api/v1/hermes/whatsapp/documents/get", headers={"Authorization": "Bearer test-tenant-1", "X-Organization-ID": str(alpha_doc.organization_id)}, json={"document_id": str(alpha_doc.id), "phone_number": wa["phones"][1]})
    assert response.status_code == 404
