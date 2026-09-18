import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.main import lifespan
from src.services.integrations.whatsapp import runtime
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider


@pytest.mark.asyncio
async def test_lifespan_closes_whatsapp_service_on_shutdown(monkeypatch):
    async def idle_loop(app):
        await asyncio.Event().wait()

    monkeypatch.setattr(runtime, "notification_loop", idle_loop)
    monkeypatch.setattr(runtime, "baileys_poller_loop", idle_loop)

    service = SimpleNamespace(close=AsyncMock())
    app = SimpleNamespace(state=SimpleNamespace(whatsapp_service=service))

    async with lifespan(app):
        pass

    service.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_service_close_contract_idempotent_and_safe_called_twice():
    """Section 7: close() is idempotent, safe if no tasks exist, safe if called twice."""
    provider = MockWhatsAppProvider()
    service = WhatsAppWebhookService(
        provider=provider,
        gateway=None,
        tenant_client=lambda org: None,
        organization_ids=[],
    )

    # 1. Safe if no tasks exist
    assert len(service._tasks) == 0
    await service.close()
    assert len(service._tasks) == 0

    # 2. Schedule a delayed task
    service._schedule_quiet_finalization(delay_seconds=100.0)
    assert len(service._tasks) == 1

    # 3. First close awaits and cancels
    await service.close()
    assert len(service._tasks) == 0

    # 4. Second close is safe and idempotent
    await service.close()
    assert len(service._tasks) == 0


@pytest.mark.asyncio
async def test_service_close_awaits_task_cancellation_no_pending_tasks():
    """Section 6 & 7: Startup schedules delayed task, shutdown cancels/awaits cleanly with 0 pending tasks."""
    provider = MockWhatsAppProvider()
    service = WhatsAppWebhookService(
        provider=provider,
        gateway=None,
        tenant_client=lambda org: None,
        organization_ids=[],
    )

    # Schedule multiple tasks
    service._schedule_quiet_finalization(delay_seconds=60.0)
    service._schedule_quiet_finalization(delay_seconds=120.0)
    assert len(service._tasks) == 2

    # Close service
    await service.close()

    # Verify all tasks are cancelled and done
    assert len(service._tasks) == 0


@pytest.mark.asyncio
async def test_service_close_does_not_swallow_unexpected_task_exceptions_silently(caplog):
    """Section 7: close() logs warnings on unexpected task exceptions without crashing."""
    provider = MockWhatsAppProvider()
    service = WhatsAppWebhookService(
        provider=provider,
        gateway=None,
        tenant_client=lambda org: None,
        organization_ids=[],
    )

    async def faulty_task():
        await asyncio.sleep(0.01)
        raise ValueError("Simulated unexpected task failure")

    task = asyncio.create_task(faulty_task())
    service._tasks.add(task)
    task.add_done_callback(service._on_task_done)

    with caplog.at_level(logging.WARNING):
        # Give faulty_task a chance to fail
        await asyncio.sleep(0.02)
        await service.close()

    assert any("unexpected exception" in record.message.lower() or "simulated unexpected" in record.message.lower() for record in caplog.records)
