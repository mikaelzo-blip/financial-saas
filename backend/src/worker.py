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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("financial_worker_entrypoint")


def build_worker() -> JobWorker:
    worker = JobWorker(poll_interval_seconds=1.0)
    # Register default job handlers here
    # (e.g. DEFERRED_DOCUMENT_ANALYSIS, INBOX_SYNC)
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
