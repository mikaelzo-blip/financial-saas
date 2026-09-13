import io
import uuid
from datetime import datetime
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.document import Document
from src.models.background_job import BackgroundJob
from src.models.enums import DocumentProcessingStatus, DocumentType
from src.services.documents.inbound_adapter import InboundDocumentAdapter, InboundDocumentInput


@pytest.mark.asyncio
async def test_inbound_adapter_ingests_and_enqueues_durable_job(db_session: AsyncSession):
    org = Organization(slug="org-adapter-test", legal_name="Org Adapter Test")
    db_session.add(org)
    await db_session.flush()

    file_content = b"%PDF-1.4\nEvidentiary-Slice-1-Test-Content"
    adapter = InboundDocumentAdapter(db_session)
    payload = InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(file_content),
        file_name="invoice_inbound.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
        caption="Invoice for site materials",
        source_message_id="msg-web-001",
    )

    doc = await adapter.ingest_and_enqueue(payload)
    await db_session.commit()

    assert doc.id is not None
    assert doc.organization_id == org.id
    assert doc.document_code.startswith("DOC-")
    assert doc.processing_status == DocumentProcessingStatus.QUEUED
    assert doc.source_channel == "WEB"
    assert doc.source_metadata.get("caption") == "Invoice for site materials"
    assert doc.source_metadata.get("source_message_id") == "msg-web-001"

    # Verify BackgroundJob was enqueued in PostgreSQL queue
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_PROCESS"
        )
    )
    assert job is not None
    assert job.status == "PENDING"
    assert job.payload["document_id"] == str(doc.id)
    assert job.idempotency_key == f"DOCUMENT_PROCESS:{doc.id}"


@pytest.mark.asyncio
async def test_inbound_adapter_rejects_exact_duplicate_and_creates_no_job(db_session: AsyncSession):
    from src.core.exceptions import DuplicateEntityException

    org = Organization(slug="org-dup-test", legal_name="Org Dup Test")
    db_session.add(org)
    await db_session.flush()

    file_content = b"%PDF-1.4\nDuplicate-Detection-Target-Bytes"
    adapter = InboundDocumentAdapter(db_session)
    payload1 = InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(file_content),
        file_name="invoice_orig.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
    )
    doc1 = await adapter.ingest_and_enqueue(payload1)
    await db_session.commit()

    # Second submission of identical file content -> must raise DuplicateEntityException
    payload2 = InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(file_content),
        file_name="invoice_duplicate.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
    )
    with pytest.raises(DuplicateEntityException):
        await adapter.ingest_and_enqueue(payload2)

    # Verify only 1 BackgroundJob exists
    jobs = (await db_session.scalars(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_PROCESS"
        )
    )).all()
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_queue_idempotency_prevents_duplicate_actionable_jobs(db_session: AsyncSession):
    from src.services.job_queue_service import JobQueueService

    org = Organization(slug="org-queue-idem", legal_name="Org Queue Idem")
    db_session.add(org)
    await db_session.flush()

    queue = JobQueueService(db_session)
    doc_id = uuid.uuid4()
    key = f"DOCUMENT_PROCESS:{doc_id}"

    # First enqueue: creates PENDING job
    job1 = await queue.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_id)},
        organization_id=org.id,
        idempotency_key=key,
    )
    await db_session.flush()
    assert job1.status == "PENDING"

    # Second enqueue with same key while first is PENDING: returns job1, no new row
    job2 = await queue.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_id)},
        organization_id=org.id,
        idempotency_key=key,
    )
    assert job2.id == job1.id

    # Verify only 1 job exists in DB
    jobs = (await db_session.scalars(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.idempotency_key == key
        )
    )).all()
    assert len(jobs) == 1

    # Simulate job1 completing
    job1.status = "COMPLETED"
    await db_session.flush()

    # Third enqueue after completion: creates new actionable job (retry supported)
    job3 = await queue.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_id)},
        organization_id=org.id,
        idempotency_key=key,
    )
    await db_session.flush()
    assert job3.id != job1.id
    assert job3.status == "PENDING"


@pytest.mark.asyncio
async def test_worker_offline_acceptance_and_claim_document_process(db_session: AsyncSession):
    from src.worker import build_worker

    org = Organization(slug="org-worker-offline", legal_name="Org Worker Offline")
    db_session.add(org)
    await db_session.flush()

    # Step 1 & 2: Worker is OFF; Ingest document
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf_stream = io.BytesIO()
    writer.write(pdf_stream)
    file_content = pdf_stream.getvalue()

    adapter = InboundDocumentAdapter(db_session)
    payload = InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(file_content),
        file_name="offline_receipt.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.RECEIPT,
        source_channel="WEB",
    )
    doc = await adapter.ingest_and_enqueue(payload)
    await db_session.commit()

    # Step 3 & 4: Document is QUEUED, Job is PENDING
    assert doc.processing_status == DocumentProcessingStatus.QUEUED
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_PROCESS"
        )
    )
    assert job is not None
    assert job.status == "PENDING"
    assert job.attempt_count == 0

    # Step 5 & 6: Worker starts later, claims and executes the job
    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = build_worker()
    worker.session_factory = test_factory

    processed = await worker.execute_one_job()
    assert processed is True

    # Step 7 & 8: BackgroundJob COMPLETED, Document processed
    await db_session.refresh(job)
    await db_session.refresh(doc)

    assert job.status == "COMPLETED"
    assert doc.processing_status in {
        DocumentProcessingStatus.READY_FOR_APPROVAL,
        DocumentProcessingStatus.REVIEW_REQUIRED,
        DocumentProcessingStatus.PROCESSED
    }
    assert doc.processing_attempts >= 1


@pytest.mark.asyncio
async def test_worker_document_process_failure_and_retry_lifecycle(db_session: AsyncSession, monkeypatch):
    from src.worker import build_worker
    from src.services.documents.pipeline import DocumentPipeline
    from datetime import timedelta

    org = Organization(slug="org-worker-retry", legal_name="Org Worker Retry")
    db_session.add(org)
    await db_session.flush()

    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    pdf_stream = io.BytesIO()
    writer.write(pdf_stream)

    adapter = InboundDocumentAdapter(db_session)
    doc = await adapter.ingest_and_enqueue(InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(pdf_stream.getvalue()),
        file_name="failing_doc.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
    ))
    await db_session.commit()

    # Set max_attempts = 2 on the job for controlled testing
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.organization_id == org.id,
            BackgroundJob.job_type == "DOCUMENT_PROCESS"
        )
    )
    job.max_attempts = 2
    await db_session.commit()

    # Simulate extraction failure
    async def mock_failing_process(self, document, path):
        document.processing_status = DocumentProcessingStatus.FAILED
        document.failure_code = "SimulatedNetworkError"
        document.failure_message = "Transient connection reset"
        return document

    monkeypatch.setattr(DocumentPipeline, "process", mock_failing_process)

    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = build_worker()
    worker.session_factory = test_factory

    # Attempt 1: Should fail and return to PENDING for retry
    processed1 = await worker.execute_one_job()
    assert processed1 is True

    await db_session.refresh(job)
    await db_session.refresh(doc)
    assert job.status == "PENDING"
    assert job.attempt_count == 1
    assert "SimulatedNetworkError" in job.last_error
    assert doc.failure_code == "SimulatedNetworkError"
    assert doc.failure_message == "Transient connection reset"

    # Fast forward available_at to now
    job.available_at = datetime.now() - timedelta(seconds=5)
    await db_session.commit()

    # Attempt 2: Reaches max_attempts -> Transitions to FAILED
    processed2 = await worker.execute_one_job()
    assert processed2 is True

    await db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.attempt_count == 2


@pytest.mark.asyncio
async def test_two_workers_cannot_double_claim_same_document_job(db_session: AsyncSession):
    from src.services.job_queue_service import JobQueueService

    org = Organization(slug="org-concurrency-test", legal_name="Org Concurrency Test")
    db_session.add(org)
    await db_session.flush()

    queue1 = JobQueueService(db_session)
    doc_id = uuid.uuid4()
    job = await queue1.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_id)},
        organization_id=org.id,
    )
    await db_session.commit()

    # Worker 1 claims job
    claimed1 = await queue1.acquire_job(worker_id="worker-node-1", lock_seconds=300)
    assert claimed1 is not None
    assert claimed1.id == job.id
    assert claimed1.locked_by == "worker-node-1"
    await db_session.commit()

    # Worker 2 attempts to claim -> None (SKIP LOCKED / already locked)
    queue2 = JobQueueService(db_session)
    claimed2 = await queue2.acquire_job(worker_id="worker-node-2", lock_seconds=300)
    assert claimed2 is None


@pytest.mark.asyncio
async def test_worker_lease_expiration_recovery_for_document_job(db_session: AsyncSession):
    from src.services.job_queue_service import JobQueueService
    from datetime import timedelta

    org = Organization(slug="org-lease-recovery", legal_name="Org Lease Recovery")
    db_session.add(org)
    await db_session.flush()

    queue = JobQueueService(db_session)
    doc_id = uuid.uuid4()
    job = await queue.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_id)},
        organization_id=org.id,
    )
    await db_session.commit()

    # Worker 1 claims the job then crashes (lease expires)
    job.status = "RUNNING"
    job.locked_by = "crashed-worker-agent"
    job.locked_until = datetime.now() - timedelta(seconds=60)
    job.attempt_count = 1
    await db_session.commit()

    # Surviving Worker 2 re-acquires the job after expired lease
    reacquired = await queue.acquire_job(worker_id="surviving-worker", lock_seconds=300)
    assert reacquired is not None
    assert reacquired.id == job.id
    assert reacquired.locked_by == "surviving-worker"
    assert reacquired.attempt_count == 2


@pytest.mark.asyncio
async def test_inbox_filtering_by_status_and_source_channel(db_session: AsyncSession):
    from src.services.document_service import DocumentService

    org = Organization(slug="org-inbox-filter", legal_name="Org Inbox Filter")
    db_session.add(org)
    await db_session.flush()

    doc_service = DocumentService(db_session)

    # Ingest 3 documents with different channels and types
    d1 = await doc_service.ingest_document(
        organization_id=org.id,
        file_obj=io.BytesIO(b"%PDF-1.4\nDoc-Channel-1"),
        file_name="doc1.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
    )
    d1.processing_status = DocumentProcessingStatus.QUEUED

    d2 = await doc_service.ingest_document(
        organization_id=org.id,
        file_obj=io.BytesIO(b"%PDF-1.4\nDoc-Channel-2"),
        file_name="doc2.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.RECEIPT,
        source_channel="WHATSAPP",
    )
    d2.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED

    d3 = await doc_service.ingest_document(
        organization_id=org.id,
        file_obj=io.BytesIO(b"%PDF-1.4\nDoc-Channel-3"),
        file_name="doc3.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.VENDOR_INVOICE,
        source_channel="WEB",
    )
    d3.processing_status = DocumentProcessingStatus.PROCESSED
    await db_session.commit()

    # Filter by processing_status = QUEUED
    queued_docs = await doc_service.list_documents(org.id, processing_status=DocumentProcessingStatus.QUEUED)
    assert len(queued_docs) == 1
    assert queued_docs[0].id == d1.id

    # Filter by source_channel = WHATSAPP
    wa_docs = await doc_service.list_documents(org.id, source_channel="WHATSAPP")
    assert len(wa_docs) == 1
    assert wa_docs[0].id == d2.id

    # Filter by source_channel = WEB and document_type = VENDOR_INVOICE
    web_invoices = await doc_service.list_documents(org.id, document_type=DocumentType.VENDOR_INVOICE, source_channel="WEB")
    assert len(web_invoices) == 2
    assert {doc.id for doc in web_invoices} == {d1.id, d3.id}


@pytest.mark.asyncio
async def test_worker_document_process_file_not_found(db_session: AsyncSession):
    from src.worker import build_worker
    from src.services.job_queue_service import JobQueueService

    org = Organization(slug="org-worker-fnf", legal_name="Org Worker FNF")
    db_session.add(org)
    await db_session.flush()

    # Create document with missing storage path
    doc = Document(
        organization_id=org.id,
        document_code="DOC-2026-999999",
        document_type=DocumentType.RECEIPT,
        file_name="ghost.pdf",
        file_hash="dummy-hash-fnf",
        file_size_bytes=100,
        mime_type="application/pdf",
        storage_path="nonexistent/path/ghost.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc)
    await db_session.flush()

    queue = JobQueueService(db_session)
    job = await queue.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc.id)},
        organization_id=org.id,
    )
    await db_session.commit()

    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = build_worker()
    worker.session_factory = test_factory

    processed = await worker.execute_one_job()
    assert processed is True

    await db_session.refresh(job)
    await db_session.refresh(doc)

    assert doc.processing_status == DocumentProcessingStatus.FAILED
    assert doc.failure_code == "FileNotFound"
    assert doc.processing_attempts == 1
    assert job.status == "PENDING"  # Retriable
    assert job.attempt_count == 1
    assert "FileNotFound" in job.last_error


def test_migration_026_lineage():
    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "026_document_inbox_queue_slice1.py"
    )
    spec = importlib.util.spec_from_file_location("migration_026", migration_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "026_document_inbox_queue"
    assert mod.down_revision == "025_transaction_rejected"
