import asyncio
import logging
import os
import signal
import socket
import uuid
from typing import Callable, Coroutine, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.background_job import BackgroundJob
from src.services.job_queue_service import JobQueueService

logger = logging.getLogger("background_worker")

JobHandler = Callable[[Dict[str, Any], AsyncSession], Coroutine[Any, Any, None]]


class JobWorker:
    """
    PostgreSQL-backed Background Job Worker for Financial SaaS modular monolith.
    Runs on local Windows PC without Redis or Celery.
    Supports:
    - Atomic job claim with SKIP LOCKED
    - Lease timeout recovery
    - Configurable retry backoff
    - Graceful shutdown
    - Idempotency & failure visibility
    """
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval_seconds: float = 2.0,
        lock_seconds: int = 300,
        session_factory = None,
    ):
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:4]}"
        self.poll_interval = poll_interval_seconds
        self.lock_seconds = lock_seconds
        self.session_factory = session_factory or AsyncSessionLocal
        self.is_running = False
        self._handlers: Dict[str, JobHandler] = {}

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler
        logger.info(f"Registered job handler for '{job_type}' on worker {self.worker_id}")

    async def execute_one_job(self) -> bool:
        """
        Attempts to acquire and execute a single job from the database queue.
        Returns True if a job was processed, False if queue was empty.
        """
        async with self.session_factory() as session:
            queue_svc = JobQueueService(session)
            job = await queue_svc.acquire_job(self.worker_id, lock_seconds=self.lock_seconds)
            if not job:
                return False

            job_id = job.id
            job_type = job.job_type
            payload = dict(job.payload)
            await session.commit()

        logger.info(f"Acquired job {job_id} ({job_type}) by worker {self.worker_id}")

        handler = self._handlers.get(job_type)
        if not handler:
            err_msg = f"No registered handler for job type '{job_type}'"
            logger.error(err_msg)
            async with self.session_factory() as session:
                queue_svc = JobQueueService(session)
                await queue_svc.fail_job(job_id, error_message=err_msg, retry_delay_seconds=300)
                await session.commit()
            return True

        try:
            async with self.session_factory() as session:
                await handler(payload, session)
                await session.commit()

            async with self.session_factory() as session:
                queue_svc = JobQueueService(session)
                await queue_svc.complete_job(job_id)
                await session.commit()

            logger.info(f"Successfully completed job {job_id} ({job_type})")
            return True

        except Exception as exc:
            err_msg = str(exc)
            logger.exception(f"Job {job_id} ({job_type}) failed: {err_msg}")
            async with self.session_factory() as session:
                queue_svc = JobQueueService(session)
                # Exponential-like delay: 30s * attempt_count
                await queue_svc.fail_job(job_id, error_message=err_msg, retry_delay_seconds=30)
                await session.commit()
            return True

    async def run(self) -> None:
        """
        Main worker loop.
        """
        self.is_running = True
        logger.info(f"Starting Background Job Worker {self.worker_id}...")

        while self.is_running:
            try:
                processed = await self.execute_one_job()
                if not processed:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected worker loop exception: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info(f"Background Job Worker {self.worker_id} stopped.")

    def stop(self) -> None:
        self.is_running = False
