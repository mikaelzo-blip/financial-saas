import uuid
import hashlib
import re
from pathlib import Path
from typing import BinaryIO, Optional, Dict, Any, List
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document, ProjectDocumentLink
from src.models.project import Project
from src.models.enums import DocumentType, DocumentProcessingStatus
from src.services.storage_service import StorageService
from src.services.audit_service import AuditService
from src.core.exceptions import EntityNotFoundException, DuplicateEntityException
from src.core.config import settings

ALLOWED_MIME_SIGNATURES = {
    "image/jpeg": (bytes.fromhex("ffd8ff"),),
    "image/png": (bytes.fromhex("89504e470d0a1a0a"),),
    "image/webp": (b"RIFF",),
    "image/heic": (bytes.fromhex("0000"),),
    "application/pdf": (b"%PDF-",),
}
MIME_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/webp": {".webp"},
    "image/heic": {".heic"}, "application/pdf": {".pdf"},
}


def safe_original_filename(file_name: str) -> str:
    name = Path(file_name.replace("\\", "/")).name
    name = re.sub(r"[^\w. ()\-]", "_", name, flags=re.UNICODE).strip(". ")[:255]
    return name or "document"


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

        stmt = select(Document.document_code).where(
            and_(
                Document.organization_id == organization_id,
                Document.document_code.like(f"{prefix}%")
            )
        )
        codes = (await self.session.execute(stmt)).scalars().all()
        max_seq = 0
        for code in codes:
            suffix = code[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
        next_seq = max_seq + 1
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
        document_id: uuid.UUID,
        for_update: bool = False,
    ) -> Document:
        stmt = select(Document).where(
            and_(
                Document.organization_id == organization_id,
                Document.id == document_id
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
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
        if source_channel == "WEB_UPLOAD":
            source_channel = "WEB"
        if source_channel not in {"WEB", "API", "WHATSAPP"}:
            raise ValueError("source_channel must be WEB, API or WHATSAPP")
        file_name = safe_original_filename(file_name)
        extension = Path(file_name).suffix.casefold()
        if mime_type not in ALLOWED_MIME_SIGNATURES:
            raise ValueError(f"Unsupported document MIME type: {mime_type}")
        if extension and extension not in MIME_EXTENSIONS[mime_type]:
            raise ValueError("File extension does not match declared MIME type")
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
        if file_size < 1 or file_size > settings.DOCUMENT_MAX_SIZE_BYTES:
            raise ValueError(f"Document size must be between 1 and {settings.DOCUMENT_MAX_SIZE_BYTES} bytes")
        header = file_obj.read(16)
        file_obj.seek(0)
        if mime_type == "image/webp":
            valid_signature = header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        elif mime_type == "image/heic":
            valid_signature = b"ftyp" in header
        else:
            valid_signature = any(header.startswith(sig) for sig in ALLOWED_MIME_SIGNATURES[mime_type])
        if not valid_signature:
            raise ValueError("File content does not match declared MIME type")
        project = None
        if project_id:
            project = await self.session.scalar(select(Project).where(
                and_(Project.id == project_id, Project.organization_id == organization_id)
            ))
            if not project:
                raise ValueError("Project is not available in this organization")

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
            created_by=created_by,
            processing_status=DocumentProcessingStatus.HASHED,
        )
        self.session.add(document)
        await self.session.flush()
        await AuditService(self.session).log_event(
            organization_id, "Document", document.id, "DOCUMENT_RECEIVED", created_by,
            new_values={"source_channel": source_channel, "file_hash": file_hash,
                        "mime_type": mime_type, "file_size_bytes": file_size},
        )

        # Link to the already validated tenant-scoped project if provided.
        if project:
            self.session.add(ProjectDocumentLink(project_id=project.id, document_id=document.id))
            await self.session.flush()

        return document

    async def list_documents(
        self,
        organization_id: uuid.UUID,
        document_type: Optional[DocumentType] = None,
        processing_status: Optional[DocumentProcessingStatus] = None,
    ) -> List[Document]:
        filters = [Document.organization_id == organization_id]
        if document_type:
            filters.append(Document.document_type == document_type)
        if processing_status:
            filters.append(Document.processing_status == processing_status)

        stmt = select(Document).where(and_(*filters)).order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
