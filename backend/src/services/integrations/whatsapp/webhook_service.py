"""API-only orchestration: provider -> Hermes -> authenticated SaaS intake."""
import asyncio
import uuid
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)

from src.schemas.hermes import HermesSubmissionRequest
from src.services.hermes.retry import HermesApiError
from .media_service import WhatsAppMediaService
from .sender_service import WhatsAppSenderService
from .outbound_service import WhatsAppOutboundService
from .provider import ProviderError
from .command_service import WhatsAppCommandService
from .clarification_service import WhatsAppClarificationService
from .rate_limiter import SlidingWindowRateLimiter


class WhatsAppWebhookService:
    def __init__(self, provider, gateway, tenant_client, organization_ids=None, org_limit=200):
        self.provider, self.gateway, self.tenant_client = provider, gateway, tenant_client
        self.senders, self.media = WhatsAppSenderService(gateway), WhatsAppMediaService(provider)
        self.outbound = WhatsAppOutboundService(provider)
        self._rejected = {}
        self.organization_ids = organization_ids or []
        self.clarifications = WhatsAppClarificationService()
        self.commands = WhatsAppCommandService()
        self._tasks = set()
        self.limiter = SlidingWindowRateLimiter()
        self.org_limit = org_limit

    async def _send_and_finish(self, event, client, finish, body):
        if body:
            finish["outbound_text"] = body
            try:
                finish["outbound_wamid"] = await self.outbound.text(event.sender_phone, body)
            except ProviderError:
                # A send timeout is ambiguous: record the attempt, never send again blindly.
                finish["outbound_wamid"] = "attempt-" + str(uuid.uuid4())
                finish["outbound_status"] = "FAILED"
                finish["delivery_status"] = "FAILED"
        await client.channel_request("messages/finish", finish)

    async def deliver_pending_notifications(self, as_of: Optional[datetime] = None):
        for org in self.organization_ids:
            client = self.tenant_client(org)
            if as_of:
                try:
                    await client.channel_request("sessions/finalize", {"as_of": as_of.isoformat()})
                except Exception:
                    pass
            await self.clarifications.expire(client)
            result = await client.channel_request("notifications", {})
            for notice in result["notices"]:
                claim = await client.channel_request("notifications/claim", {k: notice[k] for k in ("key", "phone_number", "document_id", "body")})
                if not claim.get("claimed"):
                    continue
                delivered = True
                outbound_wamid = None
                error_message = None
                try:
                    outbound_wamid = await self.outbound.text(notice["phone_number"], notice["body"], notice.get("buttons") or [])
                except ProviderError as pe:
                    delivered = False
                    error_message = str(pe)
                except Exception as exc:
                    delivered = False
                    error_message = str(type(exc).__name__)
                await client.channel_request("notifications/finish", {
                    "key": notice["key"],
                    "delivered": delivered,
                    "outbound_wamid": outbound_wamid,
                    "error_message": error_message,
                })

    def _on_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled():
            try:
                exc = task.exception()
                if exc is not None:
                    logger.warning("WhatsApp task ended with unexpected exception: %s", exc)
            except (asyncio.CancelledError, asyncio.InvalidStateError):
                pass

    def _schedule_quiet_finalization(self, delay_seconds: float = 60.0):
        async def _delayed_deliver():
            try:
                await asyncio.sleep(delay_seconds)
                await self.deliver_pending_notifications()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("Scheduled WhatsApp finalization failed: %s", exc)
        try:
            task = asyncio.create_task(_delayed_deliver())
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)
        except RuntimeError:
            pass

    async def close(self):
        tasks = list(self._tasks)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception) and not isinstance(res, asyncio.CancelledError):
                    logger.warning("WhatsApp task ended with unexpected exception: %s", res)
        self._tasks.clear()

    @asynccontextmanager
    async def batch_scope(self, senders: List[str]):
        """Coordinate backlog batch boundary across configured organizations."""
        from src.services.documents.whatsapp_session_service import WhatsAppSessionService
        for org in self.organization_ids:
            try:
                org_uuid = uuid.UUID(org) if isinstance(org, str) else org
                WhatsAppSessionService.begin_batch(org_uuid, senders)
            except Exception:
                pass
        try:
            yield
        finally:
            for org in self.organization_ids:
                try:
                    org_uuid = uuid.UUID(org) if isinstance(org, str) else org
                    WhatsAppSessionService.end_batch(org_uuid, senders)
                except Exception:
                    pass
            await self.deliver_pending_notifications()

    async def handle(self, event):
        age = (datetime.now(timezone.utc) - event.timestamp).total_seconds()
        if age > 86400 or age < -300:
            return
        sender = await self.senders.resolve(event.sender_phone)
        if not sender:
            key = hashlib.sha256((event.sender_phone + event.wamid).encode()).hexdigest()
            now = datetime.now(timezone.utc).timestamp()
            self._rejected = {k: expiry for k, expiry in self._rejected.items() if expiry > now}
            if key not in self._rejected:
                allowed, _ = self.limiter.check("unknown:" + event.sender_phone, 20)
                if not allowed or len(self._rejected) >= 10000:
                    return
                self._rejected[key] = now + 86400
                data = {"phone_number": event.sender_phone, "wamid": event.wamid, "message_type": event.message_type}
                if not (await self.gateway.channel_request("rejections/claim", data))["claimed"]:
                    return
                delivered = True
                try:
                    outbound_id = await self.outbound.text(event.sender_phone, "Nomor Anda belum terdaftar pada sistem keuangan. Silakan hubungi Administrator organisasi Anda.")
                except ProviderError:
                    outbound_id, delivered = "attempt-" + str(uuid.uuid4()), False
                await self.gateway.channel_request("rejections/finish", {**data, "outbound_wamid": outbound_id, "delivered": delivered})
            return
        client = self.tenant_client(str(sender.organization_id))
        claim = await client.channel_request("messages/claim", event.model_dump(mode="json"))
        if not claim["claimed"]:
            return
        finish = {"phone_number": event.sender_phone, "wamid": event.wamid, "delivery_status": "DELIVERED"}
        allowed, warn = self.limiter.check("sender:" + event.sender_phone, 20)
        org_allowed, org_warn = self.limiter.check("org:" + str(sender.organization_id), self.org_limit)
        if not allowed or not org_allowed:
            finish["delivery_status"] = "REJECTED"
            body = None
            if warn or org_warn:
                body = "Mohon tunggu beberapa saat sebelum mengirimkan dokumen berikutnya."
            await self._send_and_finish(event, client, finish, body)
            return
        try:
            if event.message_type in {"IMAGE", "DOCUMENT"}:
                # Silent download and submission into session pipeline (Section 10)
                # No immediate ACK per file: one ACK delivered when session finalizes.
                media = await self.media.download(event)
                outcome = await client.submit_document(
                    HermesSubmissionRequest(
                        idempotency_key="wa-msg-" + hashlib.sha256(event.wamid.encode()).hexdigest()
                    ),
                    file_name=media.file_name,
                    mime_type=media.mime_type,
                    content=media.content,
                    source_metadata={
                        "wamid": event.wamid,
                        "sender_phone": event.sender_phone,
                        "caption": event.text,
                        "timestamp": event.timestamp.isoformat(),
                        "media_id": event.media_id,
                    },
                )
                finish.update(
                    document_id=str(outcome.document_id),
                    hermes_submission_id=str(outcome.correlation_id) if outcome.correlation_id else None,
                    media_size_bytes=len(media.content),
                )
                await client.channel_request("messages/finish", finish)
                self._schedule_quiet_finalization(60.0)
                return
            else:
                body = await self.clarifications.reply(event, client)
                if body is None:
                    body = await self.commands.reply(event.text, sender, client)
                if body is not None:
                    await self._send_and_finish(event, client, finish, body)
                else:
                    # Informational / caption text recorded into session silently
                    await client.channel_request("messages/finish", finish)
                    self._schedule_quiet_finalization(60.0)
                return
        except ProviderError as pe:
            finish["delivery_status"] = "DOWNLOAD_FAILED"
            finish["error_message"] = str(pe.args[0]) if pe.args else "DOWNLOAD_FAILED"
            await client.channel_request("messages/finish", finish)
            return
        except HermesApiError as hae:
            finish["delivery_status"] = "FAILED"
            finish["error_message"] = str(getattr(hae, "code", hae))
            await client.channel_request("messages/finish", finish)
            return
