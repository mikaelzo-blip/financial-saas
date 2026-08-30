import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1 import hermes as hermes_api
from src.core.config import settings
from src.models.audit import AuditLog
from src.models.hermes import HermesSubmission
from src.models.organization import Organization


@pytest.mark.asyncio
async def test_hermes_document_upload_is_tenant_bound_idempotent_and_audited(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    organization = Organization(slug="hermes-tenant", legal_name="Hermes Tenant")
    other_organization = Organization(slug="other-tenant", legal_name="Other Tenant")
    db_session.add_all([organization, other_organization])
    await db_session.commit()
    monkeypatch.setattr(settings, "HERMES_AGENT_TOKEN", "hermes-test-secret")
    monkeypatch.setattr(settings, "HERMES_ORGANIZATION_ID", str(organization.id))

    scheduled: list[uuid.UUID] = []

    async def record_background(document_id: uuid.UUID) -> None:
        scheduled.append(document_id)

    monkeypatch.setattr(hermes_api, "process_document_background", record_background)
    headers = {
        "Authorization": "Bearer hermes-test-secret",
        "Idempotency-Key": "logical-evidence-submission-0001",
        "X-Organization-ID": str(other_organization.id),
    }
    upload = await client.post(
        "/api/v1/hermes/documents/upload",
        headers=headers,
        files={"file": ("vendor.pdf", io.BytesIO(b"%PDF-1.4\nhermes-evidence"), "application/pdf")},
        data={"document_type": "VENDOR_INVOICE"},
    )
    assert upload.status_code == 202
    body = upload.json()
    assert body["organization_id"] == str(organization.id)
    assert body["source_channel"] == "API"
    assert scheduled == [uuid.UUID(body["id"])]
    correlation_id = upload.headers["X-Hermes-Correlation-ID"]

    replay = await client.post(
        "/api/v1/hermes/documents/upload",
        headers=headers,
        files={"file": ("different-name.pdf", io.BytesIO(b"%PDF-1.4\nhermes-evidence"), "application/pdf")},
        data={"document_type": "VENDOR_INVOICE"},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == body["id"]
    assert replay.headers["X-Hermes-Correlation-ID"] == correlation_id

    submissions = (await db_session.execute(select(HermesSubmission))).scalars().all()
    assert len(submissions) == 1
    assert submissions[0].idempotency_key_hash != headers["Idempotency-Key"]
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.entity_id == submissions[0].id))
    assert audit is not None
    assert audit.new_values["document_id"] == body["id"]
    assert headers["Idempotency-Key"] not in str(audit.new_values)


@pytest.mark.asyncio
async def test_hermes_document_upload_rejects_missing_machine_credential(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "HERMES_AGENT_TOKEN", "hermes-test-secret")
    monkeypatch.setattr(settings, "HERMES_ORGANIZATION_ID", str(uuid.uuid4()))
    response = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Idempotency-Key": "logical-evidence-submission-0002"},
        files={"file": ("vendor.pdf", io.BytesIO(b"%PDF-1.4\nhermes-evidence"), "application/pdf")},
    )
    assert response.status_code == 401
