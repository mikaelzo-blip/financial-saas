import io

import pytest

from src.core.exceptions import DuplicateEntityException
from src.models.enums import DocumentType
from src.models.organization import Organization
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
