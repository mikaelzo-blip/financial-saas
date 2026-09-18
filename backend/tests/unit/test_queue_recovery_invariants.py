import asyncio
import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Document, BackgroundJob, Organization
from src.models.enums import DocumentProcessingStatus, DocumentType, DocumentSourceChannel
from src.services.job_queue_service import JobQueueService
from src.services.job_worker import JobWorker


@pytest.mark.asyncio
async def test_enqueue_rearms_existing_failed_or_completed_job_without_duplicates(db_session: AsyncSession):
    """Enqueueing with the same idempotency key rearms existing non-active job instead of creating duplicate rows."""
    queue_svc = JobQueueService(db_session)
    org_id = uuid.uuid4()
    key = f"TEST_DEDUP:{uuid.uuid4()}"

    # 1. First enqueue
    job1 = await queue_svc.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"data": "first"},
        organization_id=org_id,
        idempotency_key=key,
    )
    await db_session.commit()
    assert job1.status == "PENDING"
    assert job1.attempt_count == 0

    # 2. Simulate job execution failure to FAILED
    job1.status = "FAILED"
    job1.attempt_count = 3
    job1.last_error = "Permanent simulated failure"
    await db_session.commit()

    # 3. Second enqueue with same idempotency key
    job2 = await queue_svc.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"data": "retry_payload"},
        organization_id=org_id,
        idempotency_key=key,
    )
    await db_session.commit()

    # Must be the exact same job row, re-armed to PENDING
    assert job2.id == job1.id
    assert job2.status == "PENDING"
    assert job2.attempt_count == 0
    assert job2.last_error is None
    assert job2.payload == {"data": "retry_payload"}

    # Must have exactly 1 job in database with this key
    count = await db_session.scalar(
        select(func.count(BackgroundJob.id)).where(BackgroundJob.idempotency_key == key)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_failed_job_exhaustion_marks_document_failed(db_session: AsyncSession):
    """When a DOCUMENT_PROCESS job permanently exhausts attempts, document must not remain QUEUED."""
    queue_svc = JobQueueService(db_session)
    org = Organization(id=uuid.uuid4(), legal_name="Test Org", slug=f"test-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    doc = Document(
        organization_id=org.id,
        document_code=f"DOC-TEST-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="a" * 64,
        storage_path="storage/test.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc)
    await db_session.flush()

    job = await queue_svc.enqueue(
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc.id)},
        organization_id=org.id,
        max_attempts=3,
        idempotency_key=f"DOCUMENT_PROCESS:{doc.id}",
    )
    await db_session.commit()

    # Attempt 1: Fails, becomes PENDING
    job.attempt_count = 1
    await queue_svc.fail_job(job.id, "Attempt 1 failed")
    await db_session.commit()
    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.QUEUED

    # Attempt 3: Exhausted, becomes FAILED
    job.attempt_count = 3
    await queue_svc.fail_job(job.id, "Attempt 3 failed permanently")
    await db_session.commit()

    await db_session.refresh(doc)
    assert doc.processing_status == DocumentProcessingStatus.FAILED
    assert doc.failure_code == "JOB_FAILED"
    assert "Attempt 3 failed permanently" in doc.failure_message


@pytest.mark.asyncio
async def test_recover_orphaned_queued_documents_all_invariants(db_session: AsyncSession):
    """
    Verifies the 6 queue recovery invariants:
    1. QUEUED + viable PENDING -> leave job viable
    2. QUEUED + active RUNNING -> do not duplicate
    3. QUEUED + stale RUNNING -> bounded recovery (attempt_count preserved, NOT reset to 0)
    4. FAILED / exhausted job -> document transitions to FAILED, does not remain QUEUED
    5. COMPLETED job -> not reset by recovery scan
    6. No job -> enqueues exactly one job
    """
    queue_svc = JobQueueService(db_session)
    org = Organization(id=uuid.uuid4(), legal_name="Test Org Recovery", slug=f"test-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    # 1. No job exists -> enqueues job
    doc_no_job = Document(
        organization_id=org.id,
        document_code=f"DOC-NOJOB-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="nojob.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="1" * 64,
        storage_path="storage/nojob.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_no_job)

    # 2. Viable PENDING job -> left viable
    doc_pending = Document(
        organization_id=org.id,
        document_code=f"DOC-PEND-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="pending.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="2" * 64,
        storage_path="storage/pending.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_pending)
    await db_session.flush()
    job_pending = BackgroundJob(
        organization_id=org.id,
        idempotency_key=f"DOCUMENT_PROCESS:{doc_pending.id}",
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_pending.id)},
        status="PENDING",
        attempt_count=1,
        max_attempts=3,
    )
    db_session.add(job_pending)

    # 3. Active RUNNING job (unexpired lock) -> left untouched
    doc_running = Document(
        organization_id=org.id,
        document_code=f"DOC-RUN-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="running.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="3" * 64,
        storage_path="storage/running.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_running)
    await db_session.flush()
    job_running = BackgroundJob(
        organization_id=org.id,
        idempotency_key=f"DOCUMENT_PROCESS:{doc_running.id}",
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_running.id)},
        status="RUNNING",
        attempt_count=1,
        max_attempts=3,
        locked_by="worker-live",
        locked_until=datetime.now() + timedelta(minutes=5),
    )
    db_session.add(job_running)

    # 4. Stale RUNNING job (expired lock, attempt 1/3) -> bounded recovery to PENDING (attempt_count NOT reset to 0)
    doc_stale = Document(
        organization_id=org.id,
        document_code=f"DOC-STALE-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="stale.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="4" * 64,
        storage_path="storage/stale.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_stale)
    await db_session.flush()
    job_stale = BackgroundJob(
        organization_id=org.id,
        idempotency_key=f"DOCUMENT_PROCESS:{doc_stale.id}",
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_stale.id)},
        status="RUNNING",
        attempt_count=1,
        max_attempts=3,
        locked_by="worker-dead",
        locked_until=datetime.now() - timedelta(minutes=5),
    )
    db_session.add(job_stale)

    # 5. FAILED / exhausted job -> document transitions to FAILED, job not reset to attempt_count=0
    doc_failed = Document(
        organization_id=org.id,
        document_code=f"DOC-FAIL-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="failed.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="5" * 64,
        storage_path="storage/failed.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_failed)
    await db_session.flush()
    job_failed = BackgroundJob(
        organization_id=org.id,
        idempotency_key=f"DOCUMENT_PROCESS:{doc_failed.id}",
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_failed.id)},
        status="FAILED",
        attempt_count=3,
        max_attempts=3,
        last_error="OCR engine crash",
    )
    db_session.add(job_failed)

    # 6. COMPLETED job -> not reset by recovery scan
    doc_completed = Document(
        organization_id=org.id,
        document_code=f"DOC-COMPL-{uuid.uuid4().hex[:4]}",
        document_type=DocumentType.UNKNOWN,
        file_name="completed.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1000,
        file_hash="6" * 64,
        storage_path="storage/completed.jpg",
        source_channel=DocumentSourceChannel.WHATSAPP,
        processing_status=DocumentProcessingStatus.QUEUED,
    )
    db_session.add(doc_completed)
    await db_session.flush()
    job_completed = BackgroundJob(
        organization_id=org.id,
        idempotency_key=f"DOCUMENT_PROCESS:{doc_completed.id}",
        job_type="DOCUMENT_PROCESS",
        payload={"document_id": str(doc_completed.id)},
        status="COMPLETED",
        attempt_count=1,
        max_attempts=3,
    )
    db_session.add(job_completed)

    await db_session.commit()

    # Execute recovery scan
    recovered_count = await queue_svc.recover_orphaned_queued_documents()
    await db_session.commit()

    # 3 items recovered/reconciled: doc_no_job, doc_stale, doc_failed
    assert recovered_count == 3

    # Assert 1: doc_no_job now has a new PENDING job
    job_no_job = await db_session.scalar(
        select(BackgroundJob).where(BackgroundJob.idempotency_key == f"DOCUMENT_PROCESS:{doc_no_job.id}")
    )
    assert job_no_job is not None
    assert job_no_job.status == "PENDING"
    assert job_no_job.attempt_count == 0

    # Assert 2: viable PENDING job untouched
    await db_session.refresh(job_pending)
    assert job_pending.status == "PENDING"
    assert job_pending.attempt_count == 1

    # Assert 3: active RUNNING job untouched
    await db_session.refresh(job_running)
    assert job_running.status == "RUNNING"
    assert job_running.attempt_count == 1

    # Assert 4: stale RUNNING job recovered to PENDING without resetting attempt_count to 0
    await db_session.refresh(job_stale)
    assert job_stale.status == "PENDING"
    assert job_stale.attempt_count == 1
    assert job_stale.locked_by is None

    # Assert 5: FAILED job document marked FAILED, job not reset to attempt_count=0
    await db_session.refresh(doc_failed)
    await db_session.refresh(job_failed)
    assert doc_failed.processing_status == DocumentProcessingStatus.FAILED
    assert doc_failed.failure_code == "JOB_FAILED"
    assert job_failed.status == "FAILED"
    assert job_failed.attempt_count == 3

    # Assert 6: COMPLETED job untouched and not reset
    await db_session.refresh(job_completed)
    assert job_completed.status == "COMPLETED"
    assert job_completed.attempt_count == 1
