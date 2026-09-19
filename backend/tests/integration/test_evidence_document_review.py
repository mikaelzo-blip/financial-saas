import io

import pytest
from httpx import AsyncClient

from src.models.enums import DocumentProcessingStatus, DocumentType, UserRole
from src.models.organization import Organization
from src.models.user import User
from src.services.document_service import DocumentService


@pytest.fixture
async def evidence_env(db_session):
    org = Organization(slug="evidence-org", legal_name="Evidence Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="m@evidence.test",
        full_name="Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.commit()
    return {"org": org, "manager": manager}


@pytest.mark.asyncio
async def test_correcting_evidence_document_does_not_500(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.review_flags = ["OCR_LOW_CONFIDENCE"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"document_type": "BANK_STATEMENT"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert resp.json()["processing_status"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_approving_evidence_document_is_rejected_clearly(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 409
    assert "Dokumen pendukung" in resp.json()["detail"]
