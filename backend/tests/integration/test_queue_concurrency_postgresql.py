import asyncio
import os
import uuid
import pytest
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.models.organization import Organization
from src.models.background_job import BackgroundJob
from src.services.job_queue_service import JobQueueService

PG_URL = os.environ.get(
    "LIVE_POSTGRES_URL",
    "postgresql+asyncpg://financial:financial_dev_2026@localhost:5432/financial_saas"
)


@pytest.mark.asyncio
async def test_concurrent_enqueue_same_idempotency_key_postgresql():
    """
    Verify PostgreSQL concurrency contract:
    Two concurrent enqueue attempts for the same (organization_id, job_type, idempotency_key)
    must produce exactly ONE active actionable job.
    The losing call must return/reuse the existing job deterministically
    without producing an unhandled IntegrityError or broken transaction.
    """
    engine = create_async_engine(PG_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"Live PostgreSQL not reachable: {e}")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Create a test organization
    async with session_factory() as setup_session:
        org_slug = f"pg-queue-race-{uuid.uuid4().hex[:6]}"
        org = Organization(slug=org_slug, legal_name="PT Queue Concurrency Test")
        setup_session.add(org)
        await setup_session.commit()
        org_id = org.id

    doc_id = uuid.uuid4()
    idempotency_key = f"DOCUMENT_PROCESS:{doc_id}"
    barrier = asyncio.Barrier(2)
    results = []

    async def worker_enqueue(worker_id: int):
        async with session_factory() as session:
            queue = JobQueueService(session)
            # Synchronize both workers right before enqueue
            await barrier.wait()
            job = await queue.enqueue(
                job_type="DOCUMENT_PROCESS",
                payload={"document_id": str(doc_id), "worker_attempt": worker_id},
                organization_id=org_id,
                idempotency_key=idempotency_key,
            )
            await session.commit()
            results.append((worker_id, job.id))

    try:
        # Run two concurrent enqueue attempts
        await asyncio.gather(
            worker_enqueue(1),
            worker_enqueue(2),
        )

        assert len(results) == 2
        # Both workers should have received the exact same job ID
        assert results[0][1] == results[1][1], (
            f"Expected both workers to resolve to the same job ID, got {results[0][1]} vs {results[1][1]}"
        )

        # Query database directly to assert exactly ONE active job exists
        async with session_factory() as verify_session:
            jobs = (
                await verify_session.scalars(
                    select(BackgroundJob).where(
                        BackgroundJob.organization_id == org_id,
                        BackgroundJob.job_type == "DOCUMENT_PROCESS",
                        BackgroundJob.idempotency_key == idempotency_key,
                        BackgroundJob.status.in_(["PENDING", "RUNNING"]),
                    )
                )
            ).all()
            assert len(jobs) == 1, f"Expected exactly 1 active job, found {len(jobs)}"
            active_job = jobs[0]
            assert active_job.status == "PENDING"
            assert active_job.idempotency_key == idempotency_key

            # Simulate completion of this active job
            active_job.status = "COMPLETED"
            await verify_session.commit()

        # After completion, re-enqueuing must succeed and produce a new actionable job
        async with session_factory() as retry_session:
            queue = JobQueueService(retry_session)
            new_job = await queue.enqueue(
                job_type="DOCUMENT_PROCESS",
                payload={"document_id": str(doc_id), "retry": True},
                organization_id=org_id,
                idempotency_key=idempotency_key,
            )
            await retry_session.commit()

            assert new_job.id != results[0][1]
            assert new_job.status == "PENDING"

            # Total rows in DB: 1 COMPLETED + 1 PENDING = 2 total rows
            all_jobs = (
                await retry_session.scalars(
                    select(BackgroundJob).where(
                        BackgroundJob.organization_id == org_id,
                        BackgroundJob.job_type == "DOCUMENT_PROCESS",
                        BackgroundJob.idempotency_key == idempotency_key,
                    )
                )
            ).all()
            assert len(all_jobs) == 2
            statuses = {j.status for j in all_jobs}
            assert statuses == {"COMPLETED", "PENDING"}

    finally:
        # Cleanup test rows
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(
                text("DELETE FROM background_jobs WHERE organization_id = :org_id"),
                {"org_id": org_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM organizations WHERE id = :org_id"),
                {"org_id": org_id}
            )
            await cleanup_session.commit()
        await engine.dispose()
