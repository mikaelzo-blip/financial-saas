import io
from datetime import date
from decimal import Decimal

import pytest

from src.core.exceptions import DuplicateEntityException
from src.models.counterparty import Counterparty
from src.models.enums import DocumentType
from src.models.organization import Organization
from src.models.project import Project
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_extension_mime_mismatch_is_rejected_before_storage(db_session, tmp_path):
    org = Organization(slug="uat11-mime", legal_name="MIME")
    db_session.add(org); await db_session.flush()
    service = DocumentService(db_session)
    service.storage.base_dir = tmp_path
    with pytest.raises(ValueError, match="extension does not match"):
        await service.ingest_document(org.id, io.BytesIO(b"%PDF-1.4\nvalid"), "photo.jpg", "application/pdf", DocumentType.UNKNOWN)
    assert not list(tmp_path.rglob("*.*"))


@pytest.mark.asyncio
async def test_unsafe_filename_is_metadata_only_and_generated_storage_path(db_session, tmp_path):
    org = Organization(slug="uat11-path", legal_name="Path")
    db_session.add(org); await db_session.flush()
    service = DocumentService(db_session); service.storage.base_dir = tmp_path
    document = await service.ingest_document(org.id, io.BytesIO(b"%PDF-1.4\nvalid"), "../../evidence.pdf", "application/pdf", DocumentType.UNKNOWN)
    assert ".." not in document.storage_path
    assert document.file_name == "evidence.pdf"
    assert service.storage.get_file_path(document.storage_path).is_file()


@pytest.mark.asyncio
async def test_unsupported_empty_corrupt_and_duplicate_files_fail_closed(db_session, tmp_path):
    org = Organization(slug="uat11-invalid-files", legal_name="Invalid Files")
    db_session.add(org); await db_session.flush()
    service = DocumentService(db_session); service.storage.base_dir = tmp_path
    invalid = (
        (b"text", "evidence.txt", "text/plain", "Unsupported"),
        (b"", "empty.pdf", "application/pdf", "size"),
        (b"not-a-pdf", "corrupt.pdf", "application/pdf", "does not match"),
    )
    for content, name, mime, message in invalid:
        with pytest.raises(ValueError, match=message):
            await service.ingest_document(org.id, io.BytesIO(content), name, mime, DocumentType.UNKNOWN)
    content = b"%PDF-1.4\nunique-duplicate-check"
    await service.ingest_document(org.id, io.BytesIO(content), "first.pdf", "application/pdf", DocumentType.UNKNOWN)
    with pytest.raises(DuplicateEntityException):
        await service.ingest_document(org.id, io.BytesIO(content), "second.pdf", "application/pdf", DocumentType.UNKNOWN)
    assert len(list(tmp_path.rglob("*.pdf"))) == 1


@pytest.mark.asyncio
async def test_cross_tenant_project_reference_is_rejected_before_storage(db_session, tmp_path):
    owner = Organization(slug="uat14-project-owner", legal_name="Project Owner")
    uploader = Organization(slug="uat14-project-uploader", legal_name="Project Uploader")
    db_session.add_all([owner, uploader])
    await db_session.flush()
    customer = Counterparty(organization_id=owner.id, name="Project Customer", is_customer=True)
    db_session.add(customer)
    await db_session.flush()
    project = Project(
        organization_id=owner.id,
        customer_id=customer.id,
        project_code="PRJ-UAT14-FOREIGN",
        project_name="Foreign Project",
        start_date=date(2026, 1, 1),
        original_contract_value=Decimal("1.00"),
        revised_contract_value=Decimal("1.00"),
    )
    db_session.add(project)
    await db_session.flush()
    service = DocumentService(db_session)
    service.storage.base_dir = tmp_path

    with pytest.raises(ValueError, match="Project is not available"):
        await service.ingest_document(
            uploader.id,
            io.BytesIO(b"%PDF-1.4\ncross-tenant"),
            "cross-tenant.pdf",
            "application/pdf",
            DocumentType.SPK,
            project_id=project.id,
        )

    assert not list(tmp_path.rglob("*.*"))
