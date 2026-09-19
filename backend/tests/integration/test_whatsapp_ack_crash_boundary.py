"""Focused crash-boundary regression tests for WhatsApp session ACK state machine.

Verifies:
CASE 1 - Crash before provider send -> ACK remains retryable, exactly 1 eventual ACK
CASE 2 - Send succeeds, persistence succeeds -> Retry/restart yields 0 additional ACK
CASE 3 - Send raises ProviderError before success -> Reconciles to retryable, eventual 1 ACK
CASE 4 - Ambiguous provider boundary post-send -> Document provider limitation and local suppression
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from tests.integration.test_whatsapp_quiet_ack import wa, send_wa_event
from src.models.whatsapp import WhatsAppDocumentSession, WhatsAppMessageLog
from src.services.documents.whatsapp_session_service import WhatsAppSessionService
from src.services.integrations.whatsapp.provider import ProviderError


@pytest.mark.asyncio
async def test_case_1_crash_before_provider_send_remains_retryable(wa, db_session, monkeypatch):
    """CASE 1: Process claims ACK notice but crashes before provider.send() executes.

    Expected:
    - Session is NOT permanently marked acknowledged prematurely.
    - On retry/recovery, ACK remains eligible.
    - Exactly one logical ACK is eventually delivered.
    """
    wa["provider"].outbound.clear()
    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]
    t0 = datetime.now(timezone.utc) - timedelta(seconds=150)

    # 1. Create a candidate session via real inbound intake event
    wa["provider"].media["img-crash-1"] = ("image/png", b"\x89PNG\r\n\x1a\ncrash-1")
    res = await send_wa_event(wa, wamid="wamid.crash.001", media_id="img-crash-1")
    assert res.status_code == 200

    sess = await WhatsAppSessionService.get_open_session(db_session, org_id, phone)
    assert sess is not None
    await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=datetime.now(timezone.utc) + timedelta(seconds=70))
    await db_session.commit()

    # 2. Simulate crash during send: claim succeeds, but before outbound.text returns, process dies
    original_text = wa["service"].outbound.text

    call_count = 0

    async def crashing_text(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Simulates crash before provider send completes
        raise RuntimeError("Simulated process crash before provider send")

    monkeypatch.setattr(wa["service"].outbound, "text", crashing_text)

    # First attempt: worker attempts delivery and crashes
    try:
        await wa["service"].deliver_pending_notifications()
    except Exception:
        pass

    # CRUCIAL INVARIANT: session must NOT be permanently acknowledged
    await db_session.refresh(sess)
    assert sess.ack_sent_at is None, "Session was prematurely marked ack_sent_at before provider send!"

    # 3. Simulate recovery / restart: restore normal outbound provider
    monkeypatch.setattr(wa["service"].outbound, "text", original_text)

    # Fast forward or reset stale claim timestamp so retry kicks in
    claim_log = await db_session.scalar(
        select(WhatsAppMessageLog).where(
            WhatsAppMessageLog.organization_id == org_id,
            WhatsAppMessageLog.wamid == f"session-ack-{sess.id}",
        )
    )
    if claim_log:
        claim_log.created_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        await db_session.commit()

    # Retry delivery cycle
    await wa["service"].deliver_pending_notifications()

    # Provider should have received exactly ONE successful ACK
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    # Now session is confirmed acknowledged
    await db_session.refresh(sess)
    assert sess.ack_sent_at is not None
    assert sess.session_metadata.get("ack_status") == "SENT_CONFIRMED"


@pytest.mark.asyncio
async def test_case_2_send_succeeds_retry_yields_zero_additional_ack(wa, db_session):
    """CASE 2: Provider send succeeds and persistence succeeds.

    Expected:
    - Subsequent retry/restart/notification poll yields 0 additional ACK.
    """
    wa["provider"].outbound.clear()
    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]

    # 1. Create and finalize session via real event
    wa["provider"].media["img-case2-1"] = ("image/png", b"\x89PNG\r\n\x1a\ncase2-1")
    res = await send_wa_event(wa, wamid="wamid.case2.001", media_id="img-case2-1")
    assert res.status_code == 200

    sess = await WhatsAppSessionService.get_open_session(db_session, org_id, phone)
    assert sess is not None
    await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=datetime.now(timezone.utc) + timedelta(seconds=70))
    await db_session.commit()

    # 2. Normal delivery
    await wa["service"].deliver_pending_notifications()
    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    await db_session.refresh(sess)
    assert sess.ack_sent_at is not None

    # 3. Subsequent poll cycles / restarts
    await wa["service"].deliver_pending_notifications()
    await wa["service"].deliver_pending_notifications()

    # 0 additional ACKs emitted
    assert len(wa["provider"].outbound) == 1


@pytest.mark.asyncio
async def test_case_3_send_raises_before_success_reconciles_to_retryable(wa, db_session, monkeypatch):
    """CASE 3: Provider raises ProviderError on first attempt.

    Expected:
    - Delivery failure is recorded.
    - Session state reconciles to retryable (ack_sent_at is None, ack_status is FAILED).
    - Eventual successful retry delivers exactly one ACK.
    """
    wa["provider"].outbound.clear()
    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]

    # 1. Create and finalize session via real event
    wa["provider"].media["img-case3-1"] = ("image/png", b"\x89PNG\r\n\x1a\ncase3-1")
    res = await send_wa_event(wa, wamid="wamid.case3.001", media_id="img-case3-1")
    assert res.status_code == 200

    sess = await WhatsAppSessionService.get_open_session(db_session, org_id, phone)
    assert sess is not None
    await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=datetime.now(timezone.utc) + timedelta(seconds=70))
    await db_session.commit()

    # 2. Mock provider failure on first attempt
    original_text = wa["service"].outbound.text

    fail_once = True

    async def flaky_text(*args, **kwargs):
        nonlocal fail_once
        if fail_once:
            fail_once = False
            raise ProviderError("DELIVERY_UNCONFIRMED")
        return await original_text(*args, **kwargs)

    monkeypatch.setattr(wa["service"].outbound, "text", flaky_text)

    # First attempt fails
    await wa["service"].deliver_pending_notifications()
    assert len(wa["provider"].outbound) == 0

    await db_session.refresh(sess)
    assert sess.ack_sent_at is None, "Failed send should not record ack_sent_at!"
    assert sess.session_metadata.get("ack_status") == "FAILED"

    # 3. Second attempt succeeds
    await wa["service"].deliver_pending_notifications()

    assert len(wa["provider"].outbound) == 1
    assert wa["provider"].outbound[0].body_text == "Oke, saya catat."

    await db_session.refresh(sess)
    assert sess.ack_sent_at is not None
    assert sess.session_metadata.get("ack_status") == "SENT_CONFIRMED"


@pytest.mark.asyncio
async def test_case_4_post_send_pre_commit_crash_local_suppression(wa, db_session):
    """CASE 4: Post-send / pre-commit boundary documentation and local suppression.

    The underlying providers (Meta Cloud API / Baileys bridge) do NOT support
    caller-supplied idempotency keys on text sends.
    Verify:
    1. Provider idempotency capability is documented as NOT_SUPPORTED.
    2. Local outbound message log suppresses duplicate attempts once DELIVERED is committed.
    """
    from src.services.integrations.whatsapp.meta_provider import MetaCloudWhatsAppProvider
    from src.services.integrations.whatsapp.baileys_provider import BaileysBridgeWhatsAppProvider

    # Document limitation
    assert not hasattr(MetaCloudWhatsAppProvider, "supports_caller_idempotency_key") or not MetaCloudWhatsAppProvider.supports_caller_idempotency_key
    assert not hasattr(BaileysBridgeWhatsAppProvider, "supports_caller_idempotency_key") or not BaileysBridgeWhatsAppProvider.supports_caller_idempotency_key

    org_id = wa["orgs"][0].id
    phone = wa["phones"][0]

    wa["provider"].media["img-case4-1"] = ("image/png", b"\x89PNG\r\n\x1a\ncase4-1")
    res = await send_wa_event(wa, wamid="wamid.case4.001", media_id="img-case4-1")
    assert res.status_code == 200

    sess = await WhatsAppSessionService.get_open_session(db_session, org_id, phone)
    assert sess is not None
    await WhatsAppSessionService.finalize_expired_sessions(db_session, org_id, as_of=datetime.now(timezone.utc) + timedelta(seconds=70))
    await db_session.commit()

    # Deliver once
    await wa["service"].deliver_pending_notifications()
    assert len(wa["provider"].outbound) == 1

    # Attempt manual duplicate claim with same key
    client = wa["service"].tenant_client(str(org_id))
    dup_claim = await client.channel_request("notifications/claim", {
        "phone_number": phone,
        "document_id": sess.document_ids[0],
        "body": "Oke, saya catat.",
        "key": f"session-ack-{sess.id}",
    })
    assert dup_claim["claimed"] is False, "Local suppression should reject duplicate claim for already-delivered session ACK"
