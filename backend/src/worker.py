import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.services.job_worker import JobWorker
from src.services.deferred_analysis_service import DeferredAnalysisService
from src.services.documents.pipeline import DocumentPipeline
from src.services.documents.extraction import get_extraction_provider
from src.services.document_service import DocumentService
from src.models.document import Document
from src.models.enums import DocumentProcessingStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("financial_worker_entrypoint")


async def handle_document_deferred_analysis(payload: dict, session) -> None:
    """
    Worker handler for DOCUMENT_DEFERRED_ANALYSIS jobs:
    1. If Document requires extraction/OCR, processes DocumentPipeline.
    2. Runs DeferredAnalysisService to evaluate match evidence, counterparties, and processing policy.
    """
    import uuid
    from sqlalchemy import select

    org_id_str = payload.get("organization_id")
    session_id_str = payload.get("session_id")
    doc_id_str = payload.get("document_id")

    if not org_id_str or not session_id_str:
        logger.warning(f"Invalid payload for DOCUMENT_DEFERRED_ANALYSIS: {payload}")
        return

    org_id = uuid.UUID(org_id_str)
    session_id = uuid.UUID(session_id_str)

    # 1. Check if Document needs extraction pipeline first
    if doc_id_str:
        doc_id = uuid.UUID(doc_id_str)
        doc = await session.scalar(
            select(Document).where(
                Document.id == doc_id,
                Document.organization_id == org_id
            )
        )
        if doc and doc.processing_status in (DocumentProcessingStatus.UPLOADED, DocumentProcessingStatus.EXTRACTING):
            doc_service = DocumentService(session)
            file_path = doc_service.storage.get_file_path(doc.storage_path)
            if file_path.is_file():
                provider = get_extraction_provider()
                pipeline = DocumentPipeline(session, provider)
                await pipeline.process(doc, file_path)
                await session.flush()

    # 2. Run Deferred Analysis & Policy Gates
    analysis_svc = DeferredAnalysisService(session)
    doc_sess, decision = await analysis_svc.analyze_session(organization_id=org_id, session_id=session_id)
    logger.info(f"Analyzed session {session_id}: status={doc_sess.status.value}, decision={decision.value}")


def build_worker() -> JobWorker:
    worker = JobWorker(poll_interval_seconds=1.0)
    worker.register_handler("DOCUMENT_DEFERRED_ANALYSIS", handle_document_deferred_analysis)
    return worker



async def main():
    worker = build_worker()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("Received termination signal. Shutting down worker gracefully...")
        worker.stop()
        stop_event.set()

    # On Windows, signal registration can differ for SIGTERM / SIGINT
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal)
    except NotImplementedError:
        pass  # Windows event loop may not support add_signal_handler for all signals

    worker_task = asyncio.create_task(worker.run())

    try:
        await worker_task
    except (asyncio.CancelledError, KeyboardInterrupt):
        worker.stop()
        await worker_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
