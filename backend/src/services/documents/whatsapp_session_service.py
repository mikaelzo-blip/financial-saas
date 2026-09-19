"""WhatsApp Candidate Document Session Grouping & Backlog Reconstruction Service.

Rules:
1. Online sliding quiet window of 60s, hard maximum 120s from first message in session.
2. Offline backlog reconstruction groups strictly by ORIGINAL provider_timestamp, not local receipt time.
3. Candidate sessions are context only, never authority to post accounting.
4. Exactly one ACK per finalized candidate session ("Oke, saya catat."). Retries and restarts never duplicate ACKs.
5. Late messages on unposted sessions enrich context; late messages on posted sessions preserve accounting and route to audit.
"""
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.whatsapp import WhatsAppDocumentSession, WhatsAppMessageLog
from src.models.document import Document
from src.models.enums import DocumentProcessingStatus
from src.services.documents.caption_hints import extract_caption_hints


# Financial keywords that qualify an inbound text as relevant to start a candidate session
_FINANCIAL_TEXT_PATTERN = re.compile(
    r"\b(?:"
    r"proyek|project|pembelian|beli|sparepart|material|sewa|upah|gaji|biaya|"
    r"bensin|solar|bbm|pertamax|pertalite|dexlite|spbu|pom\s+bensin|"
    r"atk|kertas|alat\s+tulis|marker|pulpen|spidol|nota|struk|kwitansi|kuitansi|"
    r"invoice|inv|faktur|tagihan|bill|bukti\s+transfer|transfer|tf|bayar|dp|pelunasan|termin|"
    r"spk|bast|surat\s+jalan|po|purchase\s+order|operasional|kantor|untuk|utk|buat"
    r")\b",
    re.IGNORECASE,
)


def is_relevant_message(
    message_type: str,
    text: Optional[str] = None,
    has_active_session: bool = False,
) -> bool:
    """Determine if an inbound message qualifies to join or start a financial document session."""
    mtype = (message_type or "").upper()
    if mtype in {"IMAGE", "DOCUMENT"}:
        return True
    if mtype == "TEXT":
        # Pure chat without active session does not start a financial session
        if text and _FINANCIAL_TEXT_PATTERN.search(text):
            return True
        # If an active session is already open with documents, user text joins as context/caption
        if has_active_session and text and text.strip():
            return True
    return False


def _normalize_session_tz(sess: Optional[WhatsAppDocumentSession]) -> Optional[WhatsAppDocumentSession]:
    if sess is None:
        return None
    if sess.first_message_at and sess.first_message_at.tzinfo is None:
        sess.first_message_at = sess.first_message_at.replace(tzinfo=timezone.utc)
    if sess.last_message_at and sess.last_message_at.tzinfo is None:
        sess.last_message_at = sess.last_message_at.replace(tzinfo=timezone.utc)
    if sess.window_expires_at and sess.window_expires_at.tzinfo is None:
        sess.window_expires_at = sess.window_expires_at.replace(tzinfo=timezone.utc)
    if sess.hard_max_at and sess.hard_max_at.tzinfo is None:
        sess.hard_max_at = sess.hard_max_at.replace(tzinfo=timezone.utc)
    if sess.ack_sent_at and sess.ack_sent_at.tzinfo is None:
        sess.ack_sent_at = sess.ack_sent_at.replace(tzinfo=timezone.utc)
    return sess


class WhatsAppSessionService:
    @staticmethod
    async def get_open_session(
        db: AsyncSession,
        organization_id: uuid.UUID,
        phone_number: str,
    ) -> Optional[WhatsAppDocumentSession]:
        """Fetch active OPEN session for a sender in an organization."""
        sess = await db.scalar(
            select(WhatsAppDocumentSession)
            .where(
                WhatsAppDocumentSession.organization_id == organization_id,
                WhatsAppDocumentSession.phone_number == phone_number,
                WhatsAppDocumentSession.status == "OPEN",
            )
            .order_by(WhatsAppDocumentSession.created_at.desc())
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        return _normalize_session_tz(sess)

    @staticmethod
    async def get_latest_session(
        db: AsyncSession,
        organization_id: uuid.UUID,
        phone_number: str,
    ) -> Optional[WhatsAppDocumentSession]:
        """Fetch latest session (OPEN or FINALIZED) for a sender."""
        sess = await db.scalar(
            select(WhatsAppDocumentSession)
            .where(
                WhatsAppDocumentSession.organization_id == organization_id,
                WhatsAppDocumentSession.phone_number == phone_number,
            )
            .order_by(WhatsAppDocumentSession.created_at.desc())
        )
        return _normalize_session_tz(sess)

    @classmethod
    async def record_inbound_message(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        phone_number: str,
        wamid: str,
        message_type: str,
        text: Optional[str],
        provider_timestamp: datetime,
        document_id: Optional[uuid.UUID] = None,
        media_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> Tuple[Optional[WhatsAppDocumentSession], bool]:
        """Record an inbound message into the appropriate candidate session.

        Returns:
            (session, is_new_session) or (None, False) if message is pure unrelated chat.
        """
        # Ensure timezone-aware timestamp
        ts = provider_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current_time = as_of or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        open_session = await cls.get_open_session(db, organization_id, phone_number)
        has_active = open_session is not None

        if not is_relevant_message(message_type, text, has_active_session=has_active):
            return None, False

        # If there is an open session, verify temporal eligibility
        if open_session:
            first_ts = open_session.first_message_at
            if first_ts.tzinfo is None:
                first_ts = first_ts.replace(tzinfo=timezone.utc)
            last_ts = open_session.last_message_at
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            hard_max_ts = open_session.hard_max_at
            if hard_max_ts.tzinfo is None:
                hard_max_ts = hard_max_ts.replace(tzinfo=timezone.utc)

            gap = (ts - last_ts).total_seconds()
            duration_from_first = (ts - first_ts).total_seconds()

            # Grouping window: 60s quiet window sliding, 120s hard max from first message
            # For backlog synchronization where messages can arrive at once, gap <= 120s is admissible
            is_backlog = cls.is_sender_batch_locked(organization_id, phone_number)
            max_gap = 120.0 if is_backlog else 60.0

            # Message fits into open session if:
            # 1. gap <= max_gap (and gap >= -10s for slight out of order)
            # 2. duration_from_first <= 120.0
            if -10.0 <= gap <= max_gap and duration_from_first <= 120.0:
                # Update existing session
                open_session.last_message_at = max(last_ts, ts)
                # Sliding window extension: min(hard_max, last + 60s)
                open_session.window_expires_at = min(
                    hard_max_ts,
                    open_session.last_message_at + timedelta(seconds=60),
                )
                if wamid not in open_session.message_wamids:
                    open_session.message_wamids = list(open_session.message_wamids) + [wamid]
                if document_id and str(document_id) not in open_session.document_ids:
                    open_session.document_ids = list(open_session.document_ids) + [str(document_id)]
                if text and text.strip():
                    open_session.captions = list(open_session.captions) + [{
                        "wamid": wamid,
                        "text": text.strip(),
                        "timestamp": ts.isoformat(),
                    }]

                # Update document source_metadata with session info
                if document_id:
                    await cls._link_document_session(db, document_id, open_session)

                await db.flush()
                return open_session, False
            else:
                # Does not fit: finalize the open session!
                open_session.status = "FINALIZED"
                # Fall through to create a new session

        # Check late message enrichment on recently finalized session (Section 22)
        # If pure text message arrives for recently finalized session (within 5 minutes)
        if message_type.upper() == "TEXT" and text and text.strip():
            latest = await cls.get_latest_session(db, organization_id, phone_number)
            if latest and latest.status == "FINALIZED":
                latest_last_ts = latest.last_message_at
                if latest_last_ts.tzinfo is None:
                    latest_last_ts = latest_last_ts.replace(tzinfo=timezone.utc)
                if (ts - latest_last_ts).total_seconds() <= 300:
                    enriched = await cls._handle_late_message_enrichment(
                        db, organization_id, latest, wamid, text.strip(), ts
                    )
                    if enriched:
                        return latest, False

        # Start a NEW Candidate Session
        new_session = WhatsAppDocumentSession(
            id=uuid.uuid4(),
            organization_id=organization_id,
            phone_number=phone_number,
            session_code="SESS-" + uuid.uuid4().hex[:8].upper(),
            status="OPEN",
            first_message_at=ts,
            last_message_at=ts,
            window_expires_at=ts + timedelta(seconds=60),
            hard_max_at=ts + timedelta(seconds=120),
            ack_sent_at=None,
            ack_wamid=None,
            document_ids=[str(document_id)] if document_id else [],
            message_wamids=[wamid],
            captions=[{"wamid": wamid, "text": text.strip(), "timestamp": ts.isoformat()}] if text and text.strip() else [],
            session_metadata={},
        )
        db.add(new_session)
        await db.flush()

        if document_id:
            await cls._link_document_session(db, document_id, new_session)

        return new_session, True

    @classmethod
    async def _link_document_session(
        cls,
        db: AsyncSession,
        document_id: uuid.UUID,
        session: WhatsAppDocumentSession,
    ) -> None:
        """Add session link and hints into Document source_metadata."""
        doc = await db.scalar(select(Document).where(Document.id == document_id))
        if doc:
            meta = dict(doc.source_metadata or {})
            meta["session_id"] = str(session.id)
            meta["session_code"] = session.session_code
            # If session has captions, store latest caption hints in metadata
            if session.captions:
                all_caption_text = " ".join(c.get("text", "") for c in session.captions if c.get("text"))
                hints = extract_caption_hints(all_caption_text)
                meta["session_caption_hints"] = hints
            doc.source_metadata = meta
            await db.flush()

    @classmethod
    async def _handle_late_message_enrichment(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session: WhatsAppDocumentSession,
        wamid: str,
        text: str,
        timestamp: datetime,
    ) -> bool:
        """Safely enrich an already-finalized session with a late message (Section 22).

        If documents are not yet approved/posted:
        allow session enrichment / re-analysis.
        If already approved/posted:
        preserve original accounting state and route late information for review/audit.
        """
        # Inspect documents in session
        docs = (await db.scalars(
            select(Document).where(
                Document.organization_id == organization_id,
                Document.id.in_([uuid.UUID(did) for did in session.document_ids if did])
            )
        )).all() if session.document_ids else []

        any_posted = any(d.processing_status in {DocumentProcessingStatus.POSTED, DocumentProcessingStatus.PROCESSED} for d in docs)

        session.captions = list(session.captions) + [{
            "wamid": wamid,
            "text": text,
            "timestamp": timestamp.isoformat(),
            "late_enrichment": True,
            "posted_accounting_preserved": any_posted,
        }]

        if any_posted:
            # Audit only: do NOT silently mutate posted accounting!
            meta = dict(session.session_metadata or {})
            meta.setdefault("late_audit_notes", []).append({
                "wamid": wamid,
                "text": text,
                "timestamp": timestamp.isoformat(),
                "action": "PRESERVED_ACCOUNTING_AUDIT_LOGGED",
            })
            session.session_metadata = meta

            for d in docs:
                d_meta = dict(d.source_metadata or {})
                d_meta.setdefault("late_message_audit", []).append({
                    "wamid": wamid,
                    "text": text,
                    "timestamp": timestamp.isoformat(),
                    "note": "Late message received after posting. Accounting preserved.",
                })
                d.source_metadata = d_meta

            await db.flush()
            return True

        # Not yet posted: enrich document metadata with new caption hints
        all_caption_text = " ".join(c.get("text", "") for c in session.captions if c.get("text"))
        hints = extract_caption_hints(all_caption_text)

        for doc in docs:
            meta = dict(doc.source_metadata or {})
            meta["session_caption_hints"] = hints
            meta.setdefault("late_captions", []).append(text)
            doc.source_metadata = meta

        await db.flush()
        return True

    _active_batch_senders: Set[Tuple[uuid.UUID, str]] = set()

    @classmethod
    def is_sender_batch_locked(cls, organization_id: uuid.UUID, phone_number: str) -> bool:
        """Check if sender has an active backlog batch in flight."""
        return (organization_id, phone_number) in cls._active_batch_senders

    @classmethod
    def begin_batch(cls, organization_id: uuid.UUID, senders: List[str]) -> None:
        """Register active batch scope for senders."""
        for s in senders:
            cls._active_batch_senders.add((organization_id, s))

    @classmethod
    def end_batch(cls, organization_id: uuid.UUID, senders: List[str]) -> None:
        """Release active batch scope for senders."""
        for s in senders:
            cls._active_batch_senders.discard((organization_id, s))

    @classmethod
    @asynccontextmanager
    async def batch_scope(
        cls,
        organization_id: uuid.UUID,
        senders: List[str],
    ):
        """Scope an active backlog batch for specific senders.

        Prevents independent overdue-session finalizers from closing historical
        sessions midway through the same active batch.
        """
        cls.begin_batch(organization_id, senders)
        try:
            yield
        finally:
            cls.end_batch(organization_id, senders)

    @classmethod
    async def finalize_expired_sessions(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        as_of: Optional[datetime] = None,
    ) -> List[WhatsAppDocumentSession]:
        """Finalize all OPEN sessions where quiet window or hard max has expired.

        Quiet window: 60s sliding window.
        Hard max: 120s from first message.

        Skips senders currently protected by an active backlog batch.
        """
        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        expired = (await db.scalars(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.organization_id == organization_id,
                WhatsAppDocumentSession.status == "OPEN",
                or_(
                    WhatsAppDocumentSession.window_expires_at <= now,
                    WhatsAppDocumentSession.hard_max_at <= now,
                ),
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )).all()

        finalized_list: List[WhatsAppDocumentSession] = []
        for s in expired:
            if cls.is_sender_batch_locked(organization_id, s.phone_number):
                continue
            s.status = "FINALIZED"
            meta = dict(s.session_metadata or {})
            if meta.get("ack_status") not in {"SENDING", "SENT_CONFIRMED"}:
                meta["ack_status"] = "NOT_SENT"
                s.session_metadata = meta
            finalized_list.append(s)

        if finalized_list:
            await db.flush()

        return finalized_list

    @classmethod
    async def get_sessions_needing_ack(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        stale_claim_seconds: float = 30.0,
    ) -> List[WhatsAppDocumentSession]:
        """Fetch FINALIZED sessions that have not yet sent an ACK.

        Invariants:
        - If ack_sent_at is NOT None -> already confirmed, skip!
        - If active claim is in-flight (< stale_claim_seconds) -> skip!
        - If claim is stale (> stale_claim_seconds) or failed -> eligible for retry!
        """
        sessions = (await db.scalars(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.organization_id == organization_id,
                WhatsAppDocumentSession.status == "FINALIZED",
                WhatsAppDocumentSession.ack_sent_at.is_(None),
            ).order_by(WhatsAppDocumentSession.created_at.asc())
        )).all()

        eligible: List[WhatsAppDocumentSession] = []
        now = datetime.now(timezone.utc)
        for s in sessions:
            meta = s.session_metadata or {}
            ack_status = meta.get("ack_status", "NOT_SENT")
            if ack_status == "SENT_CONFIRMED":
                continue
            if ack_status == "SENDING":
                claimed_at_str = meta.get("ack_claimed_at")
                if claimed_at_str:
                    try:
                        claimed_at = datetime.fromisoformat(claimed_at_str)
                        if claimed_at.tzinfo is None:
                            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
                        if (now - claimed_at).total_seconds() < stale_claim_seconds:
                            # In-flight send by another worker
                            continue
                    except Exception:
                        pass
            eligible.append(s)

        return eligible

    @classmethod
    async def mark_session_ack_claimed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session_id: uuid.UUID,
        wamid: str,
        claimed_at: Optional[datetime] = None,
    ) -> bool:
        """Mark session ACK as CLAIMED / SENDING.
        DOES NOT set ack_sent_at (preserves retryability on pre-send crash).
        """
        ts = claimed_at or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        sess = await db.scalar(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.id == session_id,
                WhatsAppDocumentSession.organization_id == organization_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if not sess:
            return False
        if sess.ack_sent_at is not None:
            return False

        meta = dict(sess.session_metadata or {})
        ack_status = meta.get("ack_status")
        if ack_status == "SENT_CONFIRMED":
            return False
        if ack_status == "SENDING":
            claimed_at_str = meta.get("ack_claimed_at")
            if claimed_at_str:
                try:
                    claimed_at_dt = datetime.fromisoformat(claimed_at_str)
                    if claimed_at_dt.tzinfo is None:
                        claimed_at_dt = claimed_at_dt.replace(tzinfo=timezone.utc)
                    if (ts - claimed_at_dt).total_seconds() < 30.0:
                        return False
                except Exception:
                    pass

        meta["ack_status"] = "SENDING"
        meta["ack_claimed_at"] = ts.isoformat()
        meta["ack_claim_wamid"] = wamid
        sess.session_metadata = meta
        await db.flush()
        return True

    @classmethod
    async def mark_session_ack_confirmed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session_id: uuid.UUID,
        wamid: str,
        sent_at: Optional[datetime] = None,
    ) -> bool:
        """Tenant-scoped, durable, idempotent ACK confirmation.
        Called ONLY after provider send succeeds!
        """
        ts = sent_at or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        sess = await db.scalar(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.id == session_id,
                WhatsAppDocumentSession.organization_id == organization_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if not sess:
            return False
        if sess.ack_sent_at is not None:
            return True  # Already acknowledged!

        sess.ack_sent_at = ts
        sess.ack_wamid = wamid
        meta = dict(sess.session_metadata or {})
        meta["ack_status"] = "SENT_CONFIRMED"
        meta["ack_delivered_at"] = ts.isoformat()
        sess.session_metadata = meta
        await db.flush()
        return True

    @classmethod
    async def mark_session_ack_failed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session_id: uuid.UUID,
        error_message: Optional[str] = None,
    ) -> bool:
        """Mark session ACK as FAILED so it reconciles to retryable.
        Leaves ack_sent_at as None.
        """
        sess = await db.scalar(
            select(WhatsAppDocumentSession).where(
                WhatsAppDocumentSession.id == session_id,
                WhatsAppDocumentSession.organization_id == organization_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if not sess:
            return False
        if sess.ack_sent_at is not None:
            return False

        meta = dict(sess.session_metadata or {})
        meta["ack_status"] = "FAILED"
        meta["ack_failure_reason"] = error_message or "PROVIDER_SEND_FAILED"
        meta["ack_failed_at"] = datetime.now(timezone.utc).isoformat()
        sess.session_metadata = meta
        await db.flush()
        return True

    @classmethod
    async def mark_session_ack_sent(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session_id: uuid.UUID,
        wamid: str,
        sent_at: Optional[datetime] = None,
    ) -> bool:
        """Tenant-scoped, durable, idempotent ACK recording (delegates to confirmed)."""
        return await cls.mark_session_ack_confirmed(db, organization_id, session_id, wamid, sent_at)

    @classmethod
    async def reconstruct_backlog(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        messages: List[Dict[str, Any]],
        as_of: Optional[datetime] = None,
    ) -> List[WhatsAppDocumentSession]:
        """Reconstruct candidate sessions for an offline backlog.

        CRITICAL (Section 5 & 27):
        DO NOT group based on local received_at!
        Sort by ORIGINAL WhatsApp provider timestamp per sender.
        Build candidate sessions using original chronology.
        Initial temporal heuristic: same sender AND gap between relevant messages <= 120s.
        """
        if not messages:
            return []

        # Sort all backlog messages by original provider timestamp
        def parse_ts(m: Dict[str, Any]) -> datetime:
            t = m.get("timestamp") or m.get("provider_timestamp")
            if isinstance(t, datetime):
                return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t
            if isinstance(t, (int, float)):
                return datetime.fromtimestamp(t, timezone.utc)
            if isinstance(t, str):
                try:
                    dt = datetime.fromisoformat(t)
                    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
                except Exception:
                    pass
            return datetime.now(timezone.utc)

        sorted_msgs = sorted(messages, key=lambda m: (str(m.get("sender_phone") or m.get("phone_number")), parse_ts(m)))
        senders = list({str(m.get("sender_phone") or m.get("phone_number")) for m in sorted_msgs})

        created_or_updated: List[WhatsAppDocumentSession] = []
        async with cls.batch_scope(organization_id, senders):
            for m in sorted_msgs:
                phone = str(m.get("sender_phone") or m.get("phone_number"))
                wamid = str(m.get("wamid") or m.get("id"))
                mtype = str(m.get("message_type") or m.get("type", "DOCUMENT"))
                text = m.get("text") or m.get("caption")
                ts = parse_ts(m)
                doc_id = m.get("document_id")
                if doc_id and isinstance(doc_id, str):
                    doc_id = uuid.UUID(doc_id)

                sess, is_new = await cls.record_inbound_message(
                    db=db,
                    organization_id=organization_id,
                    phone_number=phone,
                    wamid=wamid,
                    message_type=mtype,
                    text=text,
                    provider_timestamp=ts,
                    document_id=doc_id,
                    as_of=as_of,
                )
                if sess and sess not in created_or_updated:
                    created_or_updated.append(sess)

            # After processing all backlog messages, finalize all reconstructed sessions
            for s in created_or_updated:
                s.status = "FINALIZED"
                _normalize_session_tz(s)
                meta = dict(s.session_metadata or {})
                if meta.get("ack_status") not in {"SENDING", "SENT_CONFIRMED"}:
                    meta["ack_status"] = "NOT_SENT"
                    s.session_metadata = meta
            await db.flush()

        return [_normalize_session_tz(s) for s in created_or_updated]
