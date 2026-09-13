import uuid
from typing import BinaryIO, Optional, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.enums import DocumentType, DocumentProcessingStatus
from src.services.document_service import DocumentService
from src.services.storage_service import StorageService
from src.services.job_queue_service import JobQueueService


@dataclass
class InboundDocumentInput:
    organization_id: uuid.UUID
    file_obj: BinaryIO
    file_name: str
    mime_type: str
    document_type: DocumentType = DocumentType.UNKNOWN
    source_channel: str = "WEB"
    source_message_id: Optional[str] = None
    caption: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None
    created_by: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None


class InboundDocumentAdapter:
    def __init__(self, session: AsyncSession, storage_service: Optional[StorageService] = None):
        self.session = session
        self.storage = storage_service or StorageService()
        self.doc_service = DocumentService(self.session, self.storage)
        self.queue_service = JobQueueService(self.session)

    async def ingest_and_enqueue(
        self,
        payload: InboundDocumentInput,
        enqueue_job: bool = True,
    ) -> Document:
        metadata = dict(payload.source_metadata or {})
        if payload.source_message_id:
            metadata["source_message_id"] = payload.source_message_id
        if payload.caption:
            metadata["caption"] = payload.caption

        document = await self.doc_service.ingest_document(
            organization_id=payload.organization_id,
            file_obj=payload.file_obj,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            document_type=payload.document_type,
            source_channel=payload.source_channel,
            source_metadata=metadata,
            created_by=payload.created_by,
            project_id=payload.project_id,
        )

        if enqueue_job:
            try:
                document.processing_status = DocumentProcessingStatus.QUEUED
                await self.session.flush()

                await self.queue_service.enqueue(
                    job_type="DOCUMENT_PROCESS",
                    payload={"document_id": str(document.id)},
                    organization_id=payload.organization_id,
                    idempotency_key=f"DOCUMENT_PROCESS:{document.id}",
                )
                await self.session.flush()
            except Exception:
                if document.file_path:
                    try:
                        self.storage.delete_file(document.file_path)
                    except OSError:
                        pass
                raise

        return document
