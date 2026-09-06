import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.background_job import BackgroundJob
from src.services.job_queue_service import JobQueueService
from src.services.job_worker import JobWorker


@pytest.mark.asyncio
async def test_job_worker_claim_execute_complete(db_session: AsyncSession):
    queue_svc = JobQueueService(db_session)
    job = await queue_svc.enqueue(
        job_type="TEST_SUCCESS_JOB",
        payload={"message": "hello", "count": 42},
    )
    await db_session.commit()

    executed_payloads = []

    async def sample_handler(payload: Dict[str, Any], session: AsyncSession):
        executed_payloads.append(payload)

    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = JobWorker(worker_id="test-worker-1", poll_interval_seconds=0.1, session_factory=test_factory)
    worker.register_handler("TEST_SUCCESS_JOB", sample_handler)

    processed = await worker.execute_one_job()
    assert processed is True
    assert len(executed_payloads) == 1
    assert executed_payloads[0]["count"] == 42

    # Verify job status in database
    job_after = await db_session.scalar(select(BackgroundJob).where(BackgroundJob.id == job.id))
    assert job_after.status == "COMPLETED"
    assert job_after.completed_at is not None
    assert job_after.locked_by is None


@pytest.mark.asyncio
async def test_job_worker_retry_and_failure_visibility(db_session: AsyncSession):
    queue_svc = JobQueueService(db_session)
    job = await queue_svc.enqueue(
        job_type="TEST_FAIL_JOB",
        payload={"task": "will_fail"},
        max_attempts=2,
    )
    await db_session.commit()

    async def failing_handler(payload: Dict[str, Any], session: AsyncSession):
        raise ValueError("Simulated job execution error")

    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker = JobWorker(worker_id="test-worker-fail", poll_interval_seconds=0.1, session_factory=test_factory)
    worker.register_handler("TEST_FAIL_JOB", failing_handler)

    # Attempt 1: Should fail and become PENDING with backoff
    processed = await worker.execute_one_job()
    assert processed is True

    await db_session.refresh(job)
    assert job.status == "PENDING"
    assert job.attempt_count == 1
    assert "Simulated job execution error" in job.last_error

    # Force available_at to now for immediate attempt 2
    job.available_at = datetime.now() - timedelta(seconds=1)
    await db_session.commit()

    # Attempt 2: Reaches max_attempts (2) -> Should transition to FAILED
    processed_2 = await worker.execute_one_job()
    assert processed_2 is True

    await db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.attempt_count == 2
    assert "Simulated job execution error" in job.last_error


@pytest.mark.asyncio
async def test_job_worker_lease_expiration_recovery(db_session: AsyncSession):
    queue_svc = JobQueueService(db_session)
    job = await queue_svc.enqueue(
        job_type="TEST_LEASE_JOB",
        payload={"data": "lease_test"},
    )
    await db_session.commit()

    # Worker 1 crashes after acquiring lock
    job.status = "RUNNING"
    job.locked_by = "crashed-worker"
    job.locked_until = datetime.now() - timedelta(seconds=10)  # Expired lease
    await db_session.commit()

    # Worker 2 acquires the expired job
    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    test_factory = lambda: TestSessionFactory(db_session)
    worker_2 = JobWorker(worker_id="worker-recovery", poll_interval_seconds=0.1, session_factory=test_factory)
    recovered = []

    async def recovery_handler(payload: Dict[str, Any], session: AsyncSession):
        recovered.append(payload)

    worker_2.register_handler("TEST_LEASE_JOB", recovery_handler)

    processed = await worker_2.execute_one_job()
    assert processed is True
    assert len(recovered) == 1

    await db_session.refresh(job)
    assert job.status == "COMPLETED"
