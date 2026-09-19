import io
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import DocumentProcessingStatus, DocumentType
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService

pytestmark = pytest.mark.asyncio


async def _setup(db_session, bill_code="BILL-DUP-001", bill_amount="48930988.86"):
    org = Organization(slug="tp-dup", legal_name="TP Dup Org")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    manager = User(
        organization_id=org.id, email="dup@test.local", full_name="Dup",
        password_hash="x", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    coa = await db_session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101",
        )
    )
    account = PaymentAccount(
        organization_id=org.id, coa_account_id=coa.id, name="Mandiri", is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    vendor = Counterparty(organization_id=org.id, name="PT Vendor Dup", is_vendor=True)
    db_session.add(vendor)
    await db_session.flush()
    bill = VendorBill(
        organization_id=org.id,
        bill_code=bill_code,
        vendor_id=vendor.id,
        bill_date=date(2026, 8, 1),
        due_date=date(2026, 9, 1),
        total_amount=Decimal(bill_amount),
    )
    db_session.add(bill)
    await db_session.commit()
    return org, manager, account


async def _doc(db_session, org, manager, account, ref, amount="48930988.86"):
    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\ndup"), "dup.pdf", "application/pdf",
        DocumentType.TRANSFER_PROOF, created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "expense_category": "OTHER_OPERATIONAL",
        "payment_account_id": str(account.id),
        "amount": amount,
        "transaction_date": "2026-08-13",
        "status": "READY_FOR_APPROVAL",
        "external_reference": ref,
    }
    doc.extracted_data = {"transfer_reference": ref, "invoice_number": ref}
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    return doc


async def test_matching_reference_and_similar_amount_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session, bill_code="20708003319")
    doc = await _doc(db_session, org, manager, account, "20708003319")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "duplicate" in resp.json()["detail"].lower()


async def test_matching_reference_but_far_amount_is_flagged_not_rejected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session, bill_code="20708003319")
    doc = await _doc(db_session, org, manager, account, "20708003319", amount="1000000.00")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    # Not rejected (no 422), but NOT auto-approved: it must stay reviewable so the
    # flag can be resolved. Landing in READY_TO_POST would dead-end (auto-post and
    # manual post both refuse while a review flag is present).
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert "DUPLICATE_SUSPECTED" in body["review_flags"]
    assert body["processing_status"] == "REVIEW_REQUIRED"


async def test_flagged_duplicate_can_be_resolved_then_approved(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session, bill_code="20708003319")
    doc = await _doc(db_session, org, manager, account, "20708003319", amount="1000000.00")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    flagged = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert flagged.status_code in (200, 201), flagged.text
    assert "DUPLICATE_SUSPECTED" in flagged.json()["review_flags"]

    # Reviewer resolves the suspected duplicate by correcting the (mis-read)
    # reference. The document carried the same value in transfer_reference and
    # invoice_number (mirroring real OCR), so both are corrected here.
    corrected = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {"transfer_reference": "88877766655", "invoice_number": "88877766655"},
            "reason": "Nomor referensi dikoreksi (bukan duplikat)",
        },
    )
    assert corrected.status_code in (200, 201), corrected.text
    assert "DUPLICATE_SUSPECTED" not in corrected.json()["review_flags"]

    # Now approval can succeed and the document reaches READY_TO_POST.
    approved = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert approved.status_code in (200, 201), approved.text
    assert approved.json()["candidate_transaction"]["status"] == "READY_TO_POST"


async def test_different_reference_with_similar_amount_is_allowed(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session)
    doc = await _doc(db_session, org, manager, account, "99900011122")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201), resp.text


async def test_normalized_reference_variants_are_detected(client: AsyncClient, db_session):
    org, manager, account = await _setup(db_session, bill_code="20708003319")
    doc = await _doc(db_session, org, manager, account, "2070-8003-319")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422


async def test_duplicate_found_beyond_scan_batch_boundary(client: AsyncClient, db_session):
    # I2: the scan reads in bounded batches; a duplicate sitting past the first
    # batch must still be found (proves keyset pagination crosses the boundary).
    org, manager, account = await _setup(db_session, bill_code="FILLER-000")
    vendor = (await db_session.scalars(
        select(VendorBill).where(VendorBill.organization_id == org.id)
    )).first().vendor_id
    for i in range(600):
        db_session.add(VendorBill(
            organization_id=org.id,
            bill_code=f"FILLER-{i:04d}",
            vendor_id=vendor,
            bill_date=date(2026, 8, 1),
            due_date=date(2026, 9, 1),
            total_amount=Decimal("1.00"),
        ))
    await db_session.flush()
    # The real duplicate lands after the batch boundary.
    db_session.add(VendorBill(
        organization_id=org.id, bill_code="20708003319", vendor_id=vendor,
        bill_date=date(2026, 8, 1), due_date=date(2026, 9, 1),
        total_amount=Decimal("48930988.86"),
    ))
    await db_session.commit()

    doc = await _doc(db_session, org, manager, account, "20708003319")
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422, resp.text
    assert "duplicate" in resp.json()["detail"].lower()
