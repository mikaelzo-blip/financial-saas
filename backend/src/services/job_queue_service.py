import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.background_job import BackgroundJob


class JobQueueService:
    """
    Manages persistent PostgreSQL-backed background jobs.
    Ensures safe concurrency and crash recovery on local Windows PC.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_job_by_idempotency_key(
        self,
        idempotency_key: str,
        organization_id: Optional[uuid.UUID] = None,
        job_type: Optional[str] = None,
    ) -> Optional[BackgroundJob]:
        filters = [
            BackgroundJob.idempotency_key == idempotency_key,
            BackgroundJob.status.in_(["PENDING", "RUNNING"]),
        ]
        if organization_id is not None:
            filters.append(BackgroundJob.organization_id == organization_id)
        if job_type is not None:
            filters.append(BackgroundJob.job_type == job_type)

        stmt = (
            select(BackgroundJob)
            .where(and_(*filters))
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        organization_id: Optional[uuid.UUID] = None,
        max_attempts: int = 3,
        delay_seconds: int = 0,
        idempotency_key: Optional[str] = None,
    ) -> BackgroundJob:
        available_at = datetime.now() + timedelta(seconds=delay_seconds)
        if idempotency_key:
            # Check for any existing job with this idempotency key to prevent duplicates
            filters = [BackgroundJob.idempotency_key == idempotency_key]
            if organization_id is not None:
                filters.append(BackgroundJob.organization_id == organization_id)
            if job_type is not None:
                filters.append(BackgroundJob.job_type == job_type)
            existing = await self.session.scalar(
                select(BackgroundJob).where(and_(*filters)).limit(1)
            )
            if existing:
                if existing.status in ("PENDING", "RUNNING"):
                    return existing
                if existing.status == "FAILED":
                    # Rearm existing failed job to prevent duplicate failed job accumulation
                    existing.status = "PENDING"
                    existing.attempt_count = 0
                    existing.max_attempts = max_attempts
                    existing.available_at = available_at
                    existing.locked_by = None
                    existing.locked_until = None
                    existing.completed_at = None
                    existing.last_error = None
                    existing.payload = payload
                    await self.session.flush()
                    return existing

        job = BackgroundJob(
            organization_id=organization_id,
            idempotency_key=idempotency_key,
            job_type=job_type,
            payload=payload,
            max_attempts=max_attempts,
            status="PENDING",
            available_at=available_at
        )

        if idempotency_key:
            try:
                async with self.session.begin_nested():
                    self.session.add(job)
                    await self.session.flush()
                return job
            except IntegrityError:
                active = await self.get_active_job_by_idempotency_key(
                    idempotency_key,
                    organization_id=organization_id,
                    job_type=job_type,
                )
                if active:
                    return active
                raise
        else:
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
            # Synchronize Document state if this is a document job so it does not stay misleadingly QUEUED
            if job.job_type == "DOCUMENT_PROCESS":
                doc_id_str = (job.payload or {}).get("document_id")
                if doc_id_str:
                    try:
                        doc_id = uuid.UUID(str(doc_id_str))
                        from src.models.document import Document
                        from src.models.enums import DocumentProcessingStatus
                        doc = await self.session.scalar(select(Document).where(Document.id == doc_id))
                        if doc and doc.processing_status in (
                            DocumentProcessingStatus.QUEUED,
                            DocumentProcessingStatus.EXTRACTING,
                            DocumentProcessingStatus.MATCHING,
                        ):
                            doc.processing_status = DocumentProcessingStatus.FAILED
                            doc.failure_code = "JOB_FAILED"
                            doc.failure_message = error_message
                            doc.processing_attempts = job.attempt_count
                            await self.session.flush()
                    except Exception:
                        pass
        else:
            job.status = "PENDING"
            job.available_at = datetime.now() + timedelta(seconds=retry_delay_seconds)
        await self.session.flush()

    async def recover_orphaned_queued_documents(self) -> int:
        """
        Ensures invariant: QUEUED document must have a viable PENDING/RUNNING DOCUMENT_PROCESS job.
        Finds any document with status == QUEUED that does not have an active (PENDING or unexpired RUNNING)
        DOCUMENT_PROCESS job, and rearms or enqueues its job without creating duplicate job rows.
        Returns the number of recovered documents.
        """
        from src.models.document import Document
        from src.models.enums import DocumentProcessingStatus

        stmt = select(Document).where(Document.processing_status == DocumentProcessingStatus.QUEUED)
        queued_docs = (await self.session.scalars(stmt)).all()
        recovered = 0
        now = datetime.now()

        for doc in queued_docs:
            idempotency_key = f"DOCUMENT_PROCESS:{doc.id}"
            job_stmt = select(BackgroundJob).where(
                BackgroundJob.idempotency_key == idempotency_key,
                BackgroundJob.job_type == "DOCUMENT_PROCESS",
            )
            job = await self.session.scalar(job_stmt)

            if job is None:
                # No job exists for this QUEUED document: enqueue one
                await self.enqueue(
                    job_type="DOCUMENT_PROCESS",
                    payload={"document_id": str(doc.id)},
                    organization_id=doc.organization_id,
                    idempotency_key=idempotency_key,
                )
                recovered += 1
                continue

            if job.status == "PENDING":
                # Viable pending job already exists, leave it viable
                continue

            if job.status == "RUNNING":
                if job.locked_until and job.locked_until > now:
                    # Active running job, do not duplicate
                    continue
                # Stale running job
                if job.attempt_count < job.max_attempts:
                    job.status = "PENDING"
                    job.available_at = now
                    job.locked_by = None
                    job.locked_until = None
                    # Do NOT reset attempt_count to 0, preserve bounded attempts
                    await self.session.flush()
                    recovered += 1
                else:
                    # Exhausted attempts
                    job.status = "FAILED"
                    doc.processing_status = DocumentProcessingStatus.FAILED
                    doc.failure_code = "JOB_FAILED"
                    doc.failure_message = job.last_error or "Processing attempts exhausted"
                    doc.processing_attempts = job.attempt_count
                    await self.session.flush()
                    recovered += 1
                continue

            if job.status == "COMPLETED":
                # COMPLETED job must not be reset by recovery scan
                continue

            if job.status == "FAILED":
                # FAILED/exhausted job: document must not remain QUEUED indefinitely.
                # Must NOT reset attempt_count indefinitely across restarts.
                doc.processing_status = DocumentProcessingStatus.FAILED
                doc.failure_code = "JOB_FAILED"
                doc.failure_message = job.last_error or "Processing attempts exhausted"
                doc.processing_attempts = job.attempt_count
                await self.session.flush()
                recovered += 1
                continue

        return recovered
