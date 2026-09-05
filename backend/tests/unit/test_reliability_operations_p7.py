import uuid
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.services.job_queue_service import JobQueueService
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_job_queue_enqueue_acquire_complete(db_session: AsyncSession):
    org = Organization(slug=f"p7-org-{uuid.uuid4().hex[:6]}", legal_name="P7 Queue PT")
    db_session.add(org)
    await db_session.flush()

    queue_service = JobQueueService(db_session)

    # 1. Enqueue Job
    job = await queue_service.enqueue(
        job_type="DOCUMENT_DEFERRED_ANALYSIS",
        payload={"session_id": str(uuid.uuid4()), "priority": "HIGH"},
        organization_id=org.id
    )
    assert job.id is not None
    assert job.status == "PENDING"
    assert job.attempt_count == 0

    # 2. Acquire Job
    acquired = await queue_service.acquire_job(worker_id="worker-win-1", lock_seconds=60)
    assert acquired is not None
    assert acquired.id == job.id
    assert acquired.status == "RUNNING"
    assert acquired.locked_by == "worker-win-1"
    assert acquired.attempt_count == 1

    # 3. Complete Job
    await queue_service.complete_job(acquired.id)
    assert acquired.status == "COMPLETED"
    assert acquired.completed_at is not None
    assert acquired.locked_by is None


@pytest.mark.asyncio
async def test_job_queue_retry_and_fail(db_session: AsyncSession):
    queue_service = JobQueueService(db_session)

    job = await queue_service.enqueue(
        job_type="WHATSAPP_BACKLOG_SYNC",
        payload={"batch_size": 10},
        max_attempts=2
    )

    # Acquire attempt 1
    acq1 = await queue_service.acquire_job("worker-1")
    assert acq1 is not None

    # Fail attempt 1 -> becomes PENDING with retry
    await queue_service.fail_job(acq1.id, error_message="Network timeout", retry_delay_seconds=0)
    assert acq1.status == "PENDING"
    assert acq1.last_error == "Network timeout"

    # Acquire attempt 2
    acq2 = await queue_service.acquire_job("worker-2")
    assert acq2 is not None
    assert acq2.attempt_count == 2

    # Fail attempt 2 -> reaches max_attempts -> becomes FAILED
    await queue_service.fail_job(acq2.id, error_message="Crash on parsing", retry_delay_seconds=0)
    assert acq2.status == "FAILED"
    assert acq2.last_error == "Crash on parsing"


@pytest.mark.asyncio
async def test_document_sequential_numbering_safety(db_session: AsyncSession):
    org = Organization(slug=f"p7-seq-{uuid.uuid4().hex[:6]}", legal_name="P7 Sequence PT")
    db_session.add(org)
    await db_session.flush()

    doc_service = DocumentService(db_session)

    # First code generated
    code1 = await doc_service.generate_document_code(org.id)
    assert code1.startswith("DOC-")
    assert code1.endswith("000001")
