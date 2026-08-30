import uuid
import hashlib
from typing import BinaryIO, Optional, Dict, Any, List
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document, ProjectDocumentLink
from src.models.project import Project
from src.models.enums import DocumentType
from src.services.storage_service import StorageService
from src.core.exceptions import EntityNotFoundException, DuplicateEntityException


def compute_sha256(file_obj: BinaryIO) -> str:
    """Computes SHA-256 hash of binary stream and resets seek pointer."""
    hasher = hashlib.sha256()
    file_obj.seek(0)
    while chunk := file_obj.read(65536):
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()


class DocumentService:
    def __init__(self, session: AsyncSession, storage_service: Optional[StorageService] = None):
        self.session = session
        self.storage = storage_service or StorageService()

    async def generate_document_code(self, organization_id: uuid.UUID) -> str:
        """Generates sequential document code in format DOC-YYYY-###### (e.g. DOC-2026-000001)."""
        year = date.today().year
        prefix = f"DOC-{year}-"

        stmt = select(func.count()).select_from(Document).where(
            and_(
                Document.organization_id == organization_id,
                Document.document_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:06d}"

    async def get_document_by_hash(
        self,
        organization_id: uuid.UUID,
        file_hash: str
    ) -> Optional[Document]:
        stmt = select(Document).where(
            and_(
                Document.organization_id == organization_id,
                Document.file_hash == file_hash
            )
        )
        return await self.session.scalar(stmt)

    async def get_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID
    ) -> Document:
        stmt = select(Document).where(
            and_(
                Document.organization_id == organization_id,
                Document.id == document_id
            )
        )
        doc = await self.session.scalar(stmt)
        if not doc:
            raise EntityNotFoundException("Document", document_id)
        return doc

    async def ingest_document(
        self,
        organization_id: uuid.UUID,
        file_obj: BinaryIO,
        file_name: str,
        mime_type: str,
        document_type: DocumentType,
        source_channel: str = "WEB_UPLOAD",
        source_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None
    ) -> Document:
        """
        Ingests a source document: computes SHA-256, verifies uniqueness, stores file, and creates DB record.
        """
        file_hash = compute_sha256(file_obj)

        # Exact duplicate detection
        existing = await self.get_document_by_hash(organization_id, file_hash)
        if existing:
            raise DuplicateEntityException(
                f"Exact duplicate document detected (matches {existing.document_code}).",
                details={
                    "document_code": existing.document_code,
                    "existing_document_id": str(existing.id),
                    "file_hash": file_hash
                }
            )

        # Measure file size
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(0)

        # Save to storage
        storage_path = self.storage.save_file(organization_id, file_obj, file_name)

        # Generate code
        doc_code = await self.generate_document_code(organization_id)

        document = Document(
            organization_id=organization_id,
            document_code=doc_code,
            document_type=document_type,
            file_name=file_name,
            mime_type=mime_type,
            file_size_bytes=file_size,
            file_hash=file_hash,
            storage_path=storage_path,
            source_channel=source_channel,
            source_metadata=source_metadata or {},
            created_by=created_by
        )
        self.session.add(document)
        await self.session.flush()

        # Link to project if provided
        if project_id:
            prj_stmt = select(Project).where(
                and_(
                    Project.id == project_id,
                    Project.organization_id == organization_id
                )
            )
            prj = await self.session.scalar(prj_stmt)
            if prj:
                link = ProjectDocumentLink(project_id=project_id, document_id=document.id)
                self.session.add(link)
                await self.session.flush()

        return document

    async def list_documents(
        self,
        organization_id: uuid.UUID,
        document_type: Optional[DocumentType] = None
    ) -> List[Document]:
        filters = [Document.organization_id == organization_id]
        if document_type:
            filters.append(Document.document_type == document_type)

        stmt = select(Document).where(and_(*filters)).order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
