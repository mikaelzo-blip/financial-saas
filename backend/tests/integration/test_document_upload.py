import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import date
from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.enums import DocumentProcessingStatus, DocumentType, ProjectStatus, UserRole
from src.models.user import User
from src.models.project import Project
from src.services.document_service import DocumentService
from src.core.exceptions import DuplicateEntityException
from src.api.v1 import documents as document_api


@pytest.mark.asyncio
async def test_document_ingest_and_duplicate_rejection(db_session: AsyncSession):
    """Test document ingestion, SHA-256 code generation, and rejection of exact duplicate uploads."""
    org = Organization(slug="org-doc-test", legal_name="Org Doc Test")
    db_session.add(org)
    await db_session.flush()
    service = DocumentService(db_session)
    content = b"%PDF-1.4\nINVOICE-NO-2026-999-EVIDENTIARY-DATA"

    # Ingest file 1
    doc1 = await service.ingest_document(
        organization_id=org.id,
        file_obj=io.BytesIO(content),
        file_name="invoice_999.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE
    )
    await db_session.commit()

    assert doc1.id is not None
    assert doc1.document_code == "DOC-2026-000001"
    assert len(doc1.file_hash) == 64

    # Attempt to ingest exact same file content in same organization -> MUST FAIL
    with pytest.raises(DuplicateEntityException) as exc:
        await service.ingest_document(
            organization_id=org.id,
            file_obj=io.BytesIO(content),
            file_name="invoice_duplicate.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.VENDOR_INVOICE
        )
    assert "Exact duplicate document detected" in str(exc.value)


@pytest.mark.asyncio
async def test_document_api_upload_and_linking(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Test multipart file upload via REST endpoint and project association."""
    org = Organization(slug="org-doc-api-test", legal_name="Org Doc API Test")
    db_session.add(org)
    await db_session.flush()

    customer = Counterparty(organization_id=org.id, name="PT Pelanggan Kontrak", is_customer=True)
    uploader = User(organization_id=org.id, email="upload@doc.test", full_name="Uploader", password_hash="x", role=UserRole.OPERATOR)
    db_session.add_all([customer, uploader])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-099",
        project_name="Gedung Olahraga",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    scheduled_document_ids: list[uuid.UUID] = []

    async def record_scheduled_document(document_id: uuid.UUID) -> None:
        scheduled_document_ids.append(document_id)

    monkeypatch.setattr(document_api, "process_document_background", record_scheduled_document)

    file_content = b"%PDF-1.4\nPDF-SPK-KONTRAK-DOKUMEN-RESMI"
    files = {"file": ("kontrak_spk.pdf", io.BytesIO(file_content), "application/pdf")}
    data = {
        "document_type": "SPK",
        "source_channel": "WEB_UPLOAD",
        "project_id": str(project.id)
    }

    response = await client.post(
        "/api/v1/documents/upload",
        files=files,
        data=data,
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(uploader.id)}
    )
    assert response.status_code == 202
    doc = response.json()
    assert doc["document_type"] == "SPK"
    assert doc["file_name"] == "kontrak_spk.pdf"
    assert "file_hash" in doc
    assert doc["processing_status"] == "EXTRACTING"
    assert scheduled_document_ids == [uuid.UUID(doc["id"])]


@pytest.mark.asyncio
async def test_document_retry_is_scheduled_as_background_work(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    org = Organization(slug="org-document-retry", legal_name="Document Retry Org")
    db_session.add(org)
    await db_session.flush()
    user = User(organization_id=org.id, email="retry@doc.test", full_name="Retry User", password_hash="x",
                role=UserRole.OPERATOR)
    db_session.add(user)
    await db_session.flush()
    document = await DocumentService(db_session).ingest_document(
        organization_id=org.id,
        file_obj=io.BytesIO(b"%PDF-1.4\nretry-document"),
        file_name="retry.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        created_by=user.id,
    )
    document.processing_status = DocumentProcessingStatus.FAILED
    await db_session.commit()

    scheduled_document_ids: list[uuid.UUID] = []

    async def record_scheduled_document(document_id: uuid.UUID) -> None:
        scheduled_document_ids.append(document_id)

    monkeypatch.setattr(document_api, "process_document_background", record_scheduled_document)
    response = await client.post(
        f"/api/v1/documents/{document.id}/retry",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)},
    )
    assert response.status_code == 202
    assert response.json()["processing_status"] == "EXTRACTING"
    assert scheduled_document_ids == [document.id]
