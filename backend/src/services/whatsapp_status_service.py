"""Operational health and status service for WhatsApp integration."""
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.whatsapp import WhatsAppMessageLog
from src.models.background_job import BackgroundJob
from src.schemas.whatsapp import WhatsAppIntegrationStatusResponse
from src.services.document_operations_service import sanitize_error_message


class WhatsAppStatusService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_status(
        self,
        organization_id: uuid.UUID,
        client: Optional[httpx.AsyncClient] = None,
    ) -> WhatsAppIntegrationStatusResponse:
        provider = settings.WHATSAPP_PROVIDER or "disabled"
        enabled = provider.lower() not in {"disabled", "none", ""}

        connection_state = "DISCONNECTED"
        bridge_error: Optional[str] = None
        last_connected_at: Optional[datetime] = None

        if not enabled:
            connection_state = "DISCONNECTED"
        elif provider == "mock":
            connection_state = "CONNECTED"
            last_connected_at = datetime.now(timezone.utc)
        elif provider == "baileys":
            bridge_url = (settings.WHATSAPP_BAILEYS_BRIDGE_URL or "http://127.0.0.1:3000").rstrip("/")
            try:
                if client:
                    res = await client.get(f"{bridge_url}/health", timeout=1.5)
                else:
                    async with httpx.AsyncClient(timeout=1.5) as http_client:
                        res = await http_client.get(f"{bridge_url}/health")

                if res.status_code == 200:
                    data = res.json() if "application/json" in (res.headers.get("content-type") or "") else {}
                    raw_status = str(data.get("status") or "").lower()
                    if raw_status == "connected":
                        connection_state = "CONNECTED"
                        last_connected_at = datetime.now(timezone.utc)
                    elif raw_status == "connecting":
                        connection_state = "CONNECTING"
                    else:
                        connection_state = "DISCONNECTED"
                        bridge_error = data.get("error") or "Bridge reported disconnected state"
                else:
                    connection_state = "ERROR"
                    bridge_error = f"Bridge health check failed with HTTP {res.status_code}"
            except Exception:
                connection_state = "DISCONNECTED"
                bridge_error = "WhatsApp bridge is not running or unreachable"
        elif provider == "meta":
            connection_state = "CONNECTED" if settings.WHATSAPP_API_TOKEN else "DEGRADED"

        # Tenant-scoped database metrics
        # 1. Last message at
        last_msg_stmt = (
            select(func.max(WhatsAppMessageLog.created_at))
            .where(WhatsAppMessageLog.organization_id == organization_id)
        )
        last_message_at = await self.session.scalar(last_msg_stmt)

        # 2. Last successful ingestion at
        last_ingest_stmt = (
            select(func.max(WhatsAppMessageLog.created_at))
            .where(
                and_(
                    WhatsAppMessageLog.organization_id == organization_id,
                    WhatsAppMessageLog.delivery_status == "DELIVERED",
                    WhatsAppMessageLog.document_id.isnot(None),
                )
            )
        )
        last_successful_ingestion_at = await self.session.scalar(last_ingest_stmt)

        # 3. Pending handoff count:
        pending_logs_stmt = (
            select(func.count(WhatsAppMessageLog.id))
            .where(
                and_(
                    WhatsAppMessageLog.organization_id == organization_id,
                    WhatsAppMessageLog.delivery_status == "PROCESSING",
                )
            )
        )
        pending_logs_count = await self.session.scalar(pending_logs_stmt) or 0

        pending_jobs_stmt = (
            select(func.count(BackgroundJob.id))
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.job_type == "DOCUMENT_PROCESS",
                    BackgroundJob.status.in_(["PENDING", "RUNNING"]),
                )
            )
        )
        pending_jobs_count = await self.session.scalar(pending_jobs_stmt) or 0
        pending_handoff_count = pending_logs_count + pending_jobs_count

        # 4. Error reporting
        last_error_code: Optional[str] = None
        last_error_message_safe: Optional[str] = None

        if bridge_error and connection_state in {"DISCONNECTED", "ERROR"}:
            last_error_code = "BRIDGE_UNAVAILABLE" if connection_state == "DISCONNECTED" else "BRIDGE_ERROR"
            last_error_message_safe = sanitize_error_message(bridge_error)
        else:
            latest_failed_stmt = (
                select(WhatsAppMessageLog)
                .where(
                    and_(
                        WhatsAppMessageLog.organization_id == organization_id,
                        WhatsAppMessageLog.delivery_status.in_(["FAILED", "DOWNLOAD_FAILED", "REJECTED"]),
                    )
                )
                .order_by(WhatsAppMessageLog.created_at.desc())
                .limit(1)
            )
            failed_log = await self.session.scalar(latest_failed_stmt)
            if failed_log:
                last_error_code = failed_log.delivery_status
                raw_err = failed_log.error_message or failed_log.delivery_status
                last_error_message_safe = sanitize_error_message(raw_err)

        return WhatsAppIntegrationStatusResponse(
            enabled=enabled,
            connection_state=connection_state,
            last_connected_at=last_connected_at,
            last_message_at=last_message_at,
            last_successful_ingestion_at=last_successful_ingestion_at,
            last_error_code=last_error_code,
            last_error_message_safe=last_error_message_safe,
            pending_handoff_count=pending_handoff_count,
            integration_version="1.0.0",
            provider=provider,
        )
