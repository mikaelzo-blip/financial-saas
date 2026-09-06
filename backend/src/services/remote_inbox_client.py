import base64
from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional, Protocol, Union
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.inbox import RemoteInboxPayload
from src.services.remote_inbox_service import RemoteInboxService
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)


class RemoteRelayBackend(Protocol):
    """Protocol satisfied by either HTTP client or in-memory RemoteRelayEmulator."""
    def pull_pending(self, limit: int = 10) -> List[Dict[str, Any]]: ...
    def get_media(self, r2_key: str) -> Optional[bytes]: ...
    def ack(self, message_ids: List[str]) -> int: ...


class HttpRemoteRelayBackend:
    """HTTP client communicating with Cloudflare Worker Edge Relay."""
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.timeout = timeout

    def pull_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/api/v1/remote-inbox/pull?limit={limit}", headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("items", [])

    def get_media(self, r2_key: str) -> Optional[bytes]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(f"{self.base_url}/api/v1/remote-inbox/media/{r2_key}", headers=self.headers)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content

    def ack(self, message_ids: List[str]) -> int:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/v1/remote-inbox/ack", json={"message_ids": message_ids}, headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("acknowledged", 0)


class RemoteInboxClient:
    """
    Local Finance PC client that synchronizes captured WhatsApp messages from
    the remote edge relay (Cloudflare Worker / Emulator) down to the local PostgreSQL database.
    """

    def __init__(
        self,
        relay: Union[RemoteRelayBackend, Any],
        storage_service: Optional[StorageService] = None,
    ):
        self.relay = relay
        self.storage_service = storage_service or StorageService()

    async def sync_remote_to_local(
        self,
        session: AsyncSession,
        organization_id: UUID,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Executes one synchronization cycle:
        1. Pulls leased messages from relay.
        2. Verifies media SHA-256 integrity.
        3. Ingests into local PostgreSQL via RemoteInboxService.
        4. Syncs backlog into Document and DocumentSession.
        5. Acknowledges successfully synced messages to remote relay.
        """
        pulled = self.relay.pull_pending(limit=limit)
        if not pulled:
            return {"pulled": 0, "ingested": 0, "synced_to_documents": 0, "acknowledged": 0, "errors": []}

        successful_ids = []
        errors = []
        inbox_service = RemoteInboxService(session=session, storage_service=self.storage_service)

        for item in pulled:
            remote_id = item["id"]
            wamid = item.get("wamid") or remote_id
            sender = item.get("sender_phone", "")

            # Process attachments
            attachments = item.get("attachments", [])
            file_name = None
            mime_type = None
            file_bytes = None
            expected_hash = None
            media_verified = True

            if attachments:
                att = attachments[0]
                r2_key = att["r2_key"]
                expected_hash = att["sha256_hash"]
                file_name = att.get("file_name", "attachment.bin")
                mime_type = att.get("mime_type", "application/octet-stream")

                # Fetch media bytes from relay
                file_bytes = self.relay.get_media(r2_key)
                if file_bytes is None:
                    errors.append(f"Missing media for remote message {remote_id}, key: {r2_key}")
                    media_verified = False
                else:
                    # Verify SHA-256 integrity
                    actual_hash = hashlib.sha256(file_bytes).hexdigest()
                    if actual_hash != expected_hash:
                        errors.append(f"SHA-256 hash mismatch for {r2_key}: expected {expected_hash}, got {actual_hash}")
                        media_verified = False

            if not media_verified:
                continue

            raw_received_at = item.get("received_at")
            if raw_received_at:
                try:
                    received_at = datetime.fromisoformat(raw_received_at.replace("Z", "+00:00"))
                except Exception:
                    received_at = datetime.now(timezone.utc)
            else:
                received_at = datetime.now(timezone.utc)

            payload = RemoteInboxPayload(
                external_message_id=wamid,
                sender_phone=sender,
                sender_name=item.get("sender_name"),
                caption=item.get("caption"),
                received_at=received_at,
                file_name=file_name,
                mime_type=mime_type,
                file_content_base64=base64.b64encode(file_bytes).decode("ascii") if file_bytes else None,
                file_hash_sha256=expected_hash if file_bytes else None,
            )

            try:
                # Ingest to local InboxMessage
                await inbox_service.ingest_remote_capture(
                    organization_id=organization_id,
                    payload=payload,
                )
                successful_ids.append(remote_id)
            except Exception as exc:
                logger.error(f"Error ingesting remote message {remote_id}: {exc}")
                errors.append(f"Ingest error for {remote_id}: {str(exc)}")

        # Sync backlog to convert eligible items into Document & DocumentSession
        synced_messages = await inbox_service.sync_backlog(organization_id=organization_id, auto_enqueue=False)
        synced_doc_count = len(synced_messages)
        await session.commit()

        # ACK successfully ingested items back to relay
        acked_count = 0
        if successful_ids:
            acked_count = self.relay.ack(successful_ids)

        return {
            "pulled": len(pulled),
            "ingested": len(successful_ids),
            "synced_to_documents": synced_doc_count,
            "acknowledged": acked_count,
            "errors": errors,
        }
