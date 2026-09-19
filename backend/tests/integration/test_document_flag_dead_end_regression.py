import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import (
    DocumentProcessingStatus,
    DocumentType,
    ReviewFlag,
    TransactionType,
    UserRole,
)
from src.models.organization import Organization
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_amount_mismatch_document_can_be_resolved_and_posted(client: AsyncClient, db_session):
    org = Organization(slug="dead-end-org", legal_name="Dead End Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id, email="m@deadend.test", full_name="M",
        password_hash="x", role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)

    cash = await db_session.scalar(select(PaymentAccount).where(
        PaymentAccount.organization_id == org.id, PaymentAccount.is_active.is_(True)
    ))
    vendor = Counterparty(
        id=uuid.uuid4(), organization_id=org.id, name="PT Uji",
        is_vendor=True, is_customer=False, is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\nnota"), "nota.pdf", "application/pdf",
        DocumentType.RECEIPT, created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": TransactionType.DIRECT_PURCHASE.value,
        "counterparty_id": str(vendor.id),
        "payment_account_id": str(cash.id),
        "cost_category": None,
        "expense_category": "TRAVEL_OFFICE",
        "project_id": None,
        "amount": "1000.00",
        "transaction_date": "2026-09-16",
        "currency_code": "IDR",
        "description": "Nota uji",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = [ReviewFlag.AMOUNT_MISMATCH.value]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.flush()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    # 1. Approve while the flag exists must fail closed.
    blocked = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert blocked.status_code == 409

    # 2. Resolve the flag THROUGH THE API (not by writing to the DB).
    corrected = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"amount": "1000.00"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert corrected.status_code == 200
    assert ReviewFlag.AMOUNT_MISMATCH.value not in corrected.json()["review_flags"]

    # 3. Approve now succeeds.
    approved = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["processing_status"] in {"READY_TO_POST", "POSTED"}
