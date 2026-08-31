"""Feature 008 strict tenant-isolation acceptance coverage."""

import pytest
from sqlalchemy import func, select
from uuid import UUID

from src.models.ai_insight import AIConversationMessage, AIConversationSession, AIInsightLog
from src.models.document import Document
from src.models.enums import DocumentProcessingStatus, DocumentType
from tests.integration.test_ai_executive_summary_api import URL
from tests.integration.test_ai_project_health_api import project_fixture


@pytest.mark.asyncio
async def test_ai_endpoints_and_cache_never_cross_tenant_boundaries(client, db_session):
    org_a, _, headers_a, project_a = await project_fixture(db_session, "isolation-a")
    org_b, _, headers_b, project_b = await project_fixture(db_session, "isolation-b")
    db_session.add(
        Document(
            organization_id=org_b.id,
            document_code="DOC-ISOLATION-B",
            document_type=DocumentType.RECEIPT,
            file_name="tenant-b.pdf",
            mime_type="application/pdf",
            file_size_bytes=1,
            file_hash="b" * 64,
            storage_path="tenant-b/document.pdf",
            source_channel="WEB_UPLOAD",
            processing_status=DocumentProcessingStatus.FAILED,
        )
    )
    await db_session.commit()

    executive_a = await client.get(URL, headers=headers_a)
    executive_b = await client.get(URL, headers=headers_b)
    assert executive_a.status_code == executive_b.status_code == 200
    assert executive_a.json()["organization_id"] == str(org_a.id)
    assert executive_b.json()["organization_id"] == str(org_b.id)
    assert str(org_b.id) not in executive_a.text
    assert str(org_a.id) not in executive_b.text

    cached_a = await client.get(URL, headers=headers_a)
    assert cached_a.status_code == 200
    assert cached_a.json()["organization_id"] == str(org_a.id)
    assert cached_a.json()["provider_metadata"]["cached"] is True
    cache_owners = set((await db_session.scalars(select(AIInsightLog.organization_id))).all())
    assert cache_owners == {org_a.id, org_b.id}
    assert await db_session.scalar(
        select(func.count()).select_from(AIInsightLog).where(AIInsightLog.organization_id == org_a.id)
    ) == 1

    project_response_a = await client.get(f"/api/v1/insights/projects/{project_a.id}", headers=headers_a)
    assert project_response_a.status_code == 200
    assert project_response_a.json()["organization_id"] == str(org_a.id)
    assert (await client.get(f"/api/v1/insights/projects/{project_b.id}", headers=headers_a)).status_code == 404
    assert (await client.get(f"/api/v1/insights/projects/{project_a.id}", headers=headers_b)).status_code == 404

    qa_a = await client.post(
        "/api/v1/insights/query",
        headers=headers_a,
        json={"query_text": "Piutang mana yang paling mendesak ditagih?", "end_date": "2026-08-31"},
    )
    qa_b = await client.post(
        "/api/v1/insights/query",
        headers=headers_b,
        json={"query_text": "Piutang mana yang paling mendesak ditagih?", "end_date": "2026-08-31"},
    )
    assert qa_a.status_code == qa_b.status_code == 200
    assert "INV-isolation-a" in qa_a.json()["answer_text"]
    assert "INV-isolation-b" not in qa_a.json()["answer_text"]
    assert "INV-isolation-b" in qa_b.json()["answer_text"]
    assert "INV-isolation-a" not in qa_b.json()["answer_text"]
    assert (
        await client.post(
            "/api/v1/insights/query",
            headers=headers_b,
            json={"query_text": "Bagaimana piutang?", "session_id": qa_a.json()["session_id"]},
        )
    ).status_code == 404

    session_a = await db_session.scalar(
        select(AIConversationSession).where(AIConversationSession.id == UUID(qa_a.json()["session_id"]))
    )
    assert session_a is not None and session_a.organization_id == org_a.id
    messages_a = (
        await db_session.scalars(
            select(AIConversationMessage).where(AIConversationMessage.session_id == session_a.id)
        )
    ).all()
    assert messages_a and all("INV-isolation-b" not in message.message_text for message in messages_a)

    anomalies_a = await client.get("/api/v1/insights/anomalies", headers=headers_a)
    anomalies_b = await client.get("/api/v1/insights/anomalies", headers=headers_b)
    assert anomalies_a.status_code == anomalies_b.status_code == 200
    assert not any(item["code"] == "DOCUMENT_PROCESSING_EXCEPTIONS" for item in anomalies_a.json()["anomalies"])
    assert any(item["code"] == "DOCUMENT_PROCESSING_EXCEPTIONS" for item in anomalies_b.json()["anomalies"])

    mismatched_headers = {**headers_a, "X-Organization-ID": str(org_b.id)}
    assert (await client.get(URL, headers=mismatched_headers)).status_code == 403
