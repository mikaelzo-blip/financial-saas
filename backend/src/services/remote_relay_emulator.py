import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any


class RemoteRelayEmulator:
    """
    In-memory / local emulator for Cloudflare Worker + D1 + R2 Edge Relay.
    Allows testing and simulating durable PC-OFF capture without requiring external credentials.
    """

    def __init__(self, relay_api_key: str = "dev-relay-secret"):
        self.relay_api_key = relay_api_key
        self.allowlist: Dict[str, Dict[str, Any]] = {}
        self.messages: Dict[str, Dict[str, Any]] = {}  # id -> message dict
        self.wamid_index: Dict[str, str] = {}  # wamid -> id
        self.media_storage: Dict[str, bytes] = {}  # r2_key -> bytes

    def set_allowlist(self, phone_numbers: List[str]):
        """Sets the active authorized sender phone numbers."""
        self.allowlist = {
            phone: {"phone": phone, "is_active": True}
            for phone in phone_numbers
        }

    def simulate_inbound_whatsapp(
        self,
        wamid: str,
        sender_phone: str,
        sender_name: str,
        caption: str = "",
        file_name: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = "application/pdf",
    ) -> Dict[str, Any]:
        """
        Simulates receiving a WhatsApp webhook at the edge while Finance PC may be OFF.
        """
        # 1. Allowlist check
        if self.allowlist and sender_phone not in self.allowlist:
            return {"status": "rejected", "reason": "SENDER_NOT_ALLOWLISTED"}

        # 2. WAMID Idempotency
        if wamid in self.wamid_index:
            existing_id = self.wamid_index[wamid]
            return {"status": "deduplicated", "message_id": existing_id}

        msg_id = str(uuid.uuid4())
        attachments = []

        if file_bytes is not None and file_name is not None:
            sha256_hash = hashlib.sha256(file_bytes).hexdigest()
            r2_key = f"media/{msg_id}/{file_name}"
            self.media_storage[r2_key] = file_bytes
            attachments.append({
                "id": str(uuid.uuid4()),
                "message_id": msg_id,
                "r2_key": r2_key,
                "file_name": file_name,
                "mime_type": mime_type or "application/octet-stream",
                "size_bytes": len(file_bytes),
                "sha256_hash": sha256_hash,
            })

        message_record = {
            "id": msg_id,
            "wamid": wamid,
            "sender_phone": sender_phone,
            "sender_name": sender_name,
            "caption": caption,
            "status": "PENDING_LOCAL",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "leased_at": None,
            "lease_expires_at": None,
            "synced_at": None,
            "retry_count": 0,
            "attachments": attachments,
        }

        self.messages[msg_id] = message_record
        self.wamid_index[wamid] = msg_id

        return {"status": "captured", "message_id": msg_id}

    def pull_pending(self, limit: int = 10, lease_seconds: int = 300) -> List[Dict[str, Any]]:
        """
        Simulates /api/v1/remote-inbox/pull called by RemoteInboxClient when PC is ON.
        Acquires a lease on un-synced or expired-leased items.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        lease_expires = (now + timedelta(seconds=lease_seconds)).isoformat()

        pulled: List[Dict[str, Any]] = []
        for msg in self.messages.values():
            if len(pulled) >= limit:
                break
            if msg["status"] == "PENDING_LOCAL":
                msg["status"] = "LEASED"
                msg["leased_at"] = now_iso
                msg["lease_expires_at"] = lease_expires
                msg["retry_count"] += 1
                pulled.append(msg)
            elif msg["status"] == "LEASED" and msg["lease_expires_at"]:
                # Check if lease expired
                exp = datetime.fromisoformat(msg["lease_expires_at"])
                if exp < now:
                    msg["leased_at"] = now_iso
                    msg["lease_expires_at"] = lease_expires
                    msg["retry_count"] += 1
                    pulled.append(msg)

        return pulled

    def get_media(self, r2_key: str) -> Optional[bytes]:
        """Simulates downloading media bytes from R2."""
        return self.media_storage.get(r2_key)

    def ack(self, message_ids: List[str]) -> int:
        """Simulates /api/v1/remote-inbox/ack."""
        count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for mid in message_ids:
            if mid in self.messages and self.messages[mid]["status"] == "LEASED":
                self.messages[mid]["status"] = "SYNCED"
                self.messages[mid]["synced_at"] = now_iso
                count += 1
        return count

    def expire_all_leases(self):
        """Forces all leases to expire (for testing retry and crash recovery)."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        for msg in self.messages.values():
            if msg["status"] == "LEASED":
                msg["lease_expires_at"] = past
