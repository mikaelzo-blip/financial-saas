import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.document import Document
from src.models.enums import CandidateStatus, DocumentProcessingStatus
from src.schemas.document import StructuredExtraction
from src.services.documents.candidate import build_candidate, derive_flags
from src.services.documents.confidence import below_threshold
from src.services.documents.extraction import ExtractionProvider, get_extraction_provider
from src.services.documents.matching import match_entities
from src.services.document_service import DocumentService
from src.services.duplicate_service import DuplicateDetectionService
from src.services.audit_service import AuditService
from src.models.enums import ReviewFlag


def document_status_for(candidate, flags: list[str]) -> DocumentProcessingStatus:
    if (flags or not candidate or not candidate.proposed_transaction_type
            or candidate.status == CandidateStatus.REVIEW_REQUIRED):
        return DocumentProcessingStatus.REVIEW_REQUIRED
    return DocumentProcessingStatus.READY_FOR_APPROVAL


class DocumentPipeline:
    def __init__(self, session: AsyncSession, provider: ExtractionProvider):
        self.session, self.provider = session, provider

    async def process(self, document: Document, path: Path) -> Document:
        if document.processing_status == DocumentProcessingStatus.PROCESSED:
            return document
        document.processing_status = DocumentProcessingStatus.EXTRACTING
        document.processing_attempts += 1
        document.failure_code = document.failure_message = None
        try:
            result = await self.provider.extract(path, document.mime_type)
            data = StructuredExtraction.model_validate(result.data)
            document.provider_name, document.provider_version = result.provider_name, result.provider_version
            effective_type = (document.document_type if result.document_type.value == "UNKNOWN"
                              and document.document_type.value != "UNKNOWN" else result.document_type)
            document.document_type = effective_type
            document.extracted_data = data.model_dump(mode="json")
            document.confidence_scores = result.confidence.model_dump(mode="json")
            document.processing_status = DocumentProcessingStatus.MATCHING
            matches = await match_entities(self.session, document.organization_id, data)
            document.matching_results = matches
            required = ("ocr_confidence", "amount_confidence")
            flags = derive_flags(effective_type, data, matches, below_threshold(result.confidence, required))
            candidate = build_candidate(document.id, effective_type, data, matches, flags)
            if candidate and candidate.transaction_date and candidate.amount:
                duplicate = await DuplicateDetectionService(self.session).check_duplicate_candidate(
                    document.organization_id, candidate.transaction_date, candidate.amount,
                    candidate.counterparty_id, candidate.payment_account_id,
                    reference_no=candidate.external_reference)
                if duplicate:
                    flags.append(ReviewFlag.DUPLICATE_SUSPECTED.value)
                    matches["duplicate_transaction_ids"] = [str(duplicate.id)]
                    candidate.status = candidate.status.REVIEW_REQUIRED
            document.review_flags = flags
            document.candidate_transaction = candidate.model_dump(mode="json") if candidate else {}
            document.processing_status = document_status_for(candidate, flags)
            audit = AuditService(self.session)
            await audit.log_event(document.organization_id, "Document", document.id, "DOCUMENT_CLASSIFIED",
                new_values={"document_type": effective_type.value,
                            "confidence": str(result.confidence.document_type_confidence)})
            await audit.log_event(document.organization_id, "Document", document.id, "DOCUMENT_EXTRACTED",
                new_values={"provider_name": result.provider_name, "provider_version": result.provider_version,
                            "fields": sorted(data.model_dump(exclude_none=True, exclude={"raw_text"}))})
            if candidate:
                await audit.log_event(document.organization_id, "Document", document.id, "CANDIDATE_PROPOSED",
                    new_values={"candidate_id": str(candidate.id),
                                "transaction_type": (candidate.proposed_transaction_type.value
                                                     if candidate.proposed_transaction_type else None),
                                "review_flags": flags})
        except Exception as exc:
            document.processing_status = DocumentProcessingStatus.FAILED
            document.failure_code = type(exc).__name__
            document.failure_message = str(exc)[:1000]
        await self.session.flush()
        return document


async def process_document_background(document_id: uuid.UUID, provider_name: str | None = None) -> None:
    """Process an already-ingested document in an isolated background session.

    The identifier is internal work metadata created after an authenticated
    upload; all externally visible access remains organization scoped in the
    API. Processing failures are captured by ``DocumentPipeline`` instead of
    escaping to the request lifecycle.
    """
    async with AsyncSessionLocal() as session:
        document = await session.scalar(select(Document).where(Document.id == document_id))
        if not document:
            return
        service = DocumentService(session)
        try:
            provider = get_extraction_provider(provider_name)
        except Exception as exc:
            document.processing_status = DocumentProcessingStatus.FAILED
            document.failure_code = type(exc).__name__
            document.failure_message = str(exc)[:1000]
            await session.commit()
            return
        await DocumentPipeline(session, provider).process(
            document, service.storage.get_file_path(document.storage_path)
        )
        await session.commit()
