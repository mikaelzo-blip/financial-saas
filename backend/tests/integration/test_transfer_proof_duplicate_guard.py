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
    assert resp.status_code in (200, 201), resp.text
    assert "DUPLICATE_SUSPECTED" in resp.json()["review_flags"]


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
