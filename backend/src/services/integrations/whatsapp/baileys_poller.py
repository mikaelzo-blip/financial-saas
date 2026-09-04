"""Hermes Baileys Poller Worker.
Long-polls local Baileys bridge GET /messages and delivers events to WhatsAppWebhookService.
Pure transport: never touches PostgreSQL, ledger, or accounting engine.
"""
import asyncio
import logging
from typing import Any

import httpx

from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.integrations.whatsapp.baileys_provider import BaileysBridgeWhatsAppProvider

logger = logging.getLogger(__name__)


class BaileysBridgePoller:
    def __init__(
        self,
        service: WhatsAppWebhookService,
        bridge_url: str = "http://127.0.0.1:3000",
        poll_interval_seconds: float = 1.0,
        *,
        transport=None,
    ):
        self.service = service
        self.bridge_url = bridge_url.rstrip("/")
        self.poll_interval = poll_interval_seconds
        self._transport = transport
        self._running = False
        self._task: asyncio.Task | None = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=35.0)

    async def poll_once(self) -> list[dict[str, Any]]:
        async with self._client() as client:
            res = await client.get(f"{self.bridge_url}/messages")
            res.raise_for_status()
            data = res.json()
            return data if isinstance(data, list) else []

    async def run_loop(self):
        self._running = True
        logger.info("Baileys bridge poller started for %s", self.bridge_url)
        while self._running:
            try:
                messages = await self.poll_once()
                for raw_msg in messages:
                    if not isinstance(self.service.provider, BaileysBridgeWhatsAppProvider):
                        continue
                    events = self.service.provider.parse(raw_msg)
                    for event in events:
                        await self.service.handle(event)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Baileys bridge poller cycle failed: %s", type(exc).__name__)
                await asyncio.sleep(2.0)
            await asyncio.sleep(self.poll_interval)
        self._running = False

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run_loop())
        return self._task

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
