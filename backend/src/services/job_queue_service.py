import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.background_job import BackgroundJob


class JobQueueService:
    """
    Manages persistent PostgreSQL-backed background jobs.
    Ensures safe concurrency and crash recovery on local Windows PC.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        organization_id: Optional[uuid.UUID] = None,
        max_attempts: int = 3,
        delay_seconds: int = 0
    ) -> BackgroundJob:
        available_at = datetime.now() + timedelta(seconds=delay_seconds)
        job = BackgroundJob(
            organization_id=organization_id,
            job_type=job_type,
            payload=payload,
            max_attempts=max_attempts,
            status="PENDING",
            available_at=available_at
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def acquire_job(
        self,
        worker_id: str,
        lock_seconds: int = 300
    ) -> Optional[BackgroundJob]:
        now = datetime.now()
        stmt = (
            select(BackgroundJob)
            .where(
                and_(
                    or_(
                        BackgroundJob.status == "PENDING",
                        and_(
                            BackgroundJob.status == "RUNNING",
                            BackgroundJob.locked_until < now
                        )
                    ),
                    BackgroundJob.available_at <= now,
                    BackgroundJob.attempt_count < BackgroundJob.max_attempts
                )
            )
            .order_by(BackgroundJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = await self.session.scalar(stmt)
        if not job:
            return None

        job.status = "RUNNING"
        job.locked_by = worker_id
        job.locked_until = now + timedelta(seconds=lock_seconds)
        job.attempt_count += 1
        await self.session.flush()
        return job

    async def complete_job(
        self,
        job_id: uuid.UUID
    ) -> None:
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        job = await self.session.scalar(stmt)
        if job:
            job.status = "COMPLETED"
            job.completed_at = datetime.now()
            job.locked_by = None
            job.locked_until = None
            await self.session.flush()

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error_message: str,
        retry_delay_seconds: int = 60
    ) -> None:
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        job = await self.session.scalar(stmt)
        if not job:
            return

        job.last_error = error_message
        job.locked_by = None
        job.locked_until = None

        if job.attempt_count >= job.max_attempts:
            job.status = "FAILED"
        else:
            job.status = "PENDING"
            job.available_at = datetime.now() + timedelta(seconds=retry_delay_seconds)
        await self.session.flush()
