import io
import uuid

import pytest
from sqlalchemy import select

from src.models.document import DocumentCorrection
from src.models.enums import DocumentProcessingStatus, DocumentType, UserRole
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.transaction import Transaction
from src.models.user import User
from src.services.document_service import DocumentService


@pytest.fixture
async def transfer_review(db_session):
    org = Organization(slug=f"transfer-{uuid.uuid4().hex[:8]}", legal_name="Transfer review")
    db_session.add(org)
    await db_session.flush()
    user = User(organization_id=org.id, email="review@transfer.test", full_name="Reviewer",
                password_hash="unused", role=UserRole.MANAGER)
    db_session.add(user)
    await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\ntransfer-contract"), "transfer.pdf", "application/pdf",
        DocumentType.TRANSFER_PROOF, created_by=user.id,
    )
    doc.extracted_data = {"total_amount": "1000", "currency_code": "IDR", "transfer_reference": "REF-OLD"}
    doc.candidate_transaction = {"id": str(doc.id), "amount": "1000", "currency_code": "IDR",
                                 "transaction_date": "2026-09-10", "status": "REVIEW_REQUIRED",
                                 "proposed_transaction_type": "VENDOR_ADVANCE"}
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.review_flags = []
    await db_session.commit()
    return doc, {"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)}


@pytest.mark.asyncio
async def test_transfer_approval_rechecks_execution_even_without_flags(client, db_session, transfer_review):
    doc, headers = transfer_review
    response = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert response.status_code == 409
    assert "TRANSFER_EXECUTION_UNCONFIRMED" in response.text
    assert not (await db_session.scalars(select(Transaction))).all()
    assert not (await db_session.scalars(select(JournalEntry))).all()


@pytest.mark.asyncio
async def test_transfer_reference_correction_is_persisted_and_audited(client, db_session, transfer_review):
    doc, headers = transfer_review
    response = await client.post(f"/api/v1/documents/{doc.id}/corrections", headers=headers,
                                json={"changes": {"transfer_reference": "REF-NEW"}, "reason": "Read source reference"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["extracted_data"]["transfer_reference"] == "REF-NEW"
    assert result["candidate_transaction"]["external_reference"] == "REF-NEW"
    assert result["processing_status"] == "REVIEW_REQUIRED"
    correction = await db_session.scalar(select(DocumentCorrection).where(DocumentCorrection.document_id == doc.id))
    assert correction.old_value == "REF-OLD" and correction.new_value == "REF-NEW"


@pytest.mark.asyncio
async def test_stale_approved_transfer_cannot_post_without_execution(db_session, transfer_review):
    from src.core.exceptions import InvariantViolationException
    from src.services.document_posting_service import DocumentPostingService
    doc, _ = transfer_review
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.flush()
    with pytest.raises(InvariantViolationException) as error:
        await DocumentPostingService(db_session).post_document(doc.organization_id, doc.id,
                                                               actor_role=UserRole.MANAGER)
    assert error.value.details["failure_reason"] == "UNRESOLVED_REVIEW"
    assert not (await db_session.scalars(select(Transaction))).all()


@pytest.mark.asyncio
async def test_execution_confirmation_keeps_approval_distinct_from_posting(client, db_session, transfer_review):
    doc, headers = transfer_review
    response = await client.post(f"/api/v1/documents/{doc.id}/corrections", headers=headers, json={
        "changes": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil, REF-OLD"},
        "reason": "Verifikasi bukti pelaksanaan",
    })
    assert response.status_code == 200, response.text
    assert response.json()["processing_status"] == "READY_FOR_APPROVAL"
    approved = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["processing_status"] == "READY_TO_POST"
    assert not (await db_session.scalars(select(Transaction))).all()
    assert not (await db_session.scalars(select(JournalEntry))).all()


@pytest.mark.asyncio
async def test_confirming_execution_cannot_hide_foreign_currency_or_fees(client, db_session, transfer_review):
    doc, headers = transfer_review
    doc.extracted_data = {**doc.extracted_data, "admin_fee": "25"}
    await db_session.commit()
    response = await client.post(f"/api/v1/documents/{doc.id}/corrections", headers=headers, json={
        "changes": {"execution_status": "EXECUTED", "execution_evidence": "Transfer berhasil"},
        "reason": "Verifikasi bukti pelaksanaan",
    })
    assert response.status_code == 200, response.text
    assert "TRANSFER_AMOUNT_REVIEW" in response.json()["review_flags"]
    assert response.json()["processing_status"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_transfer_amount_correction_is_persisted_and_authoritative(client, db_session, transfer_review):
    doc, headers = transfer_review
    response = await client.post(f"/api/v1/documents/{doc.id}/corrections", headers=headers, json={
        "changes": {
            "amount": "48110249.26",
            "transfer_reference": "REF-CORRECTED",
            "execution_status": "EXECUTED",
            "execution_evidence": "Transfer berhasil terkonfirmasi",
        },
        "reason": "Koreksi nominal dan referensi oleh peninjau",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["extracted_data"]["total_amount"] == "48110249.26"
    assert body["candidate_transaction"]["amount"] == "48110249.26"
    assert body["candidate_transaction"]["external_reference"] == "REF-CORRECTED"
    assert body["processing_status"] == "READY_FOR_APPROVAL"
