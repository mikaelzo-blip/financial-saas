import uuid
import base64
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.inbox import InboxMessage, DocumentSession
from src.models.document import Document
from src.models.background_job import BackgroundJob
from src.models.enums import (
    InboxMessageStatus,
    SessionMatchStatus,
    ProcessingPolicyDecision,
    DocumentProcessingStatus
)
from src.schemas.inbox import RemoteInboxPayload
from src.services.remote_inbox_service import RemoteInboxService
from src.services.job_worker import JobWorker
from src.worker import handle_document_deferred_analysis


@pytest.mark.asyncio
async def test_deferred_analysis_runtime_pipeline(db_session: AsyncSession):
    """
    Test R4 end-to-end deferred analysis pipeline:
    Remote capture -> sync backlog -> enqueues job -> worker acquires and analyzes session -> DocumentSession updated.
    """
    org = Organization(slug=f"r4-org-{uuid.uuid4().hex[:6]}", legal_name="R4 Pipeline PT")
    db_session.add(org)
    await db_session.flush()

    raw_pdf = b"%PDF-1.4 Fake invoice content for deferred analysis test"
    pdf_base64 = base64.b64encode(raw_pdf).decode("ascii")

    # 1. Capture message via RemoteInboxService
    service = RemoteInboxService(db_session)
    payload = RemoteInboxPayload(
        external_message_id=f"WAMID-R4-{uuid.uuid4().hex[:6]}",
        sender_phone="628123456789",
        sender_name="Pak Mandor",
        caption="Kwitansi material proyek gedung olahraga",
        received_at=datetime.now(timezone.utc),
        file_name="kwitansi_material.pdf",
        mime_type="application/pdf",
        file_content_base64=pdf_base64
    )
    msg = await service.ingest_remote_capture(org.id, payload)
    assert msg.status == InboxMessageStatus.RECEIVED

    # 2. Sync backlog -> should create Document, DocumentSession, and enqueue BackgroundJob
    synced = await service.sync_backlog(org.id, auto_enqueue=True)
    assert len(synced) == 1
    assert synced[0].status == InboxMessageStatus.SYNCED

    # Verify BackgroundJob was enqueued
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_DEFERRED_ANALYSIS"
        )
    )
    assert job is not None
    assert job.status == "PENDING"
    assert job.payload["organization_id"] == str(org.id)

    session_id = uuid.UUID(job.payload["session_id"])
    doc_session = await db_session.scalar(
        select(DocumentSession).where(DocumentSession.id == session_id)
    )
    assert doc_session is not None
    assert doc_session.status == SessionMatchStatus.PENDING

    # 3. Simulate JobWorker executing the handler
    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = JobWorker(worker_id="test-worker-r4", poll_interval_seconds=0.1, session_factory=test_factory)
    worker.register_handler("DOCUMENT_DEFERRED_ANALYSIS", handle_document_deferred_analysis)

    processed = await worker.execute_one_job()
    assert processed is True

    # 4. Verify job completed and DocumentSession was analyzed
    await db_session.refresh(job)
    assert job.status == "COMPLETED"

    await db_session.refresh(doc_session)
    # Since vendor is unknown, policy requires review
    assert doc_session.status == SessionMatchStatus.REVIEW_REQUIRED
    assert len(doc_session.evidences) > 0
