import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.audit import AuditLog
from src.models.document import Document
from src.models.transaction import Transaction
from src.models.enums import CandidateStatus, DocumentProcessingStatus, DocumentType, UserRole
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.user import User
from src.schemas.document import ConfidenceScores, StructuredExtraction, TransactionCandidate
from src.services.document_service import DocumentService
from src.services.documents.extraction import ExtractionResult, ScriptedExtractionProvider
from src.services.documents.pipeline import DocumentPipeline


@pytest.mark.asyncio
async def test_document_review_queue_and_rejection_create_no_financial_event(client: AsyncClient, db_session):
    org = Organization(slug="uat11-reject", legal_name="UAT 11 Reject")
    db_session.add(org); await db_session.flush()
    manager = User(organization_id=org.id, email="reviewer@uat11.test", full_name="Reviewer", password_hash="x", role=UserRole.MANAGER)
    db_session.add(manager); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(org.id, io.BytesIO(b"%PDF-1.4\nproof"), "proof.pdf", "application/pdf", DocumentType.TRANSFER_PROOF, created_by=manager.id)
    doc.candidate_transaction = TransactionCandidate(id=doc.id, status=CandidateStatus.REVIEW_REQUIRED).model_dump(mode="json")
    doc.review_flags = ["ACCOUNT_REVIEW"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    queue = await client.get("/api/v1/documents/review-queue", headers=headers)
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [str(doc.id)]
    received = await db_session.scalar(select(AuditLog).where(
        AuditLog.entity_id == doc.id, AuditLog.action == "DOCUMENT_RECEIVED"
    ))
    assert received and received.actor_id == manager.id and received.new_values["source_channel"] == "WEB"
    rejected = await client.post(f"/api/v1/documents/{doc.id}/reject", headers=headers, json={"reason": "Evidence does not represent a business event"})
    assert rejected.status_code == 200
    assert rejected.json()["processing_status"] == "REJECTED"
    assert await db_session.scalar(select(JournalEntry)) is None
    event = await db_session.scalar(select(AuditLog).where(
        AuditLog.entity_id == doc.id, AuditLog.action == "REJECT_CANDIDATE"
    ))
    assert event and event.actor_id == manager.id and event.reason == "Evidence does not represent a business event"
    assert (await client.post(f"/api/v1/documents/{doc.id}/reject", headers=headers,
                              json={"reason": "replay"})).status_code == 409
    assert (await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)).status_code == 409


@pytest.mark.asyncio
async def test_pipeline_audits_classification_extraction_and_candidate(db_session, tmp_path):
    org = Organization(slug="uat11-pipeline-audit", legal_name="UAT 11 Pipeline Audit")
    db_session.add(org); await db_session.flush()
    service = DocumentService(db_session); service.storage.base_dir = tmp_path
    doc = await service.ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\ntransfer"), "transfer.pdf", "application/pdf",
        DocumentType.UNKNOWN,
    )
    extraction = StructuredExtraction(transaction_date="2026-09-02", total_amount="25000000",
                                      currency_code="IDR", issuer_name="Unknown Sender")
    scores = ConfidenceScores(ocr_confidence=".99", document_type_confidence=".99",
                              entity_confidence="0", project_confidence="0", amount_confidence=".99")
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.TRANSFER_PROOF, extraction, scores, "scripted", "uat11",
    ))

    await DocumentPipeline(db_session, provider).process(doc, service.storage.get_file_path(doc.storage_path))

    actions = set((await db_session.scalars(select(AuditLog.action).where(AuditLog.entity_id == doc.id))).all())
    assert {"DOCUMENT_RECEIVED", "DOCUMENT_CLASSIFIED", "DOCUMENT_EXTRACTED", "CANDIDATE_PROPOSED"} <= actions


@pytest.mark.asyncio
async def test_payment_approval_without_allocation_fails_before_financial_mutation(client: AsyncClient, db_session):
    org = Organization(slug="uat11-payment-guard", legal_name="UAT 11 Payment Guard")
    db_session.add(org); await db_session.flush()
    manager = User(organization_id=org.id, email="guard@uat11.test", full_name="Guard", password_hash="x", role=UserRole.MANAGER)
    db_session.add(manager); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\npayment"), "payment.pdf", "application/pdf",
        DocumentType.TRANSFER_PROOF, created_by=manager.id,
    )
    doc.candidate_transaction = TransactionCandidate(
        id=doc.id, proposed_transaction_type="CUSTOMER_PAYMENT", transaction_date="2026-09-02",
        amount="25000000", currency_code="IDR", status=CandidateStatus.READY_FOR_APPROVAL,
    ).model_dump(mode="json")
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    response = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)

    assert response.status_code == 409
    assert await db_session.scalar(select(Transaction).where(Transaction.organization_id == org.id)) is None
    assert await db_session.scalar(select(JournalEntry).where(JournalEntry.organization_id == org.id)) is None


@pytest.mark.asyncio
async def test_approval_locks_document_row_before_conversion(client: AsyncClient, db_session, monkeypatch):
    org = Organization(slug="uat11-approval-lock", legal_name="UAT 11 Approval Lock")
    db_session.add(org); await db_session.flush()
    manager = User(organization_id=org.id, email="lock@uat11.test", full_name="Lock", password_hash="x", role=UserRole.MANAGER)
    db_session.add(manager); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\nlock"), "lock.pdf", "application/pdf", DocumentType.VENDOR_INVOICE,
    )
    doc.candidate_transaction = TransactionCandidate(
        id=doc.id, proposed_transaction_type="VENDOR_BILL", transaction_date="2026-09-02",
        amount="1000", currency_code="IDR", status=CandidateStatus.READY_FOR_APPROVAL,
    ).model_dump(mode="json")
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    seen = False
    original_scalar = db_session.scalar

    async def observe_lock(statement, *args, **kwargs):
        nonlocal seen
        if "FOR UPDATE" in str(statement):
            seen = True
        return await original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "scalar", observe_lock)
    response = await client.post(f"/api/v1/documents/{doc.id}/approve",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)})
    assert response.status_code == 422  # Candidate lacks required vendor/project, but lock occurs first.
    assert seen


@pytest.mark.asyncio
async def test_document_ingestion_never_mutates_financial_state(db_session, tmp_path):
    org = Organization(slug="uat11-no-post", legal_name="UAT 11 No Posting")
    db_session.add(org); await db_session.flush()
    service = DocumentService(db_session); service.storage.base_dir = tmp_path
    await service.ingest_document(
        org.id, io.BytesIO(b"%PDF-1.4\nfinancial-evidence-only"), "evidence.pdf",
        "application/pdf", DocumentType.VENDOR_INVOICE,
    )
    assert await db_session.scalar(select(Transaction).where(Transaction.organization_id == org.id)) is None
    assert await db_session.scalar(select(JournalEntry).where(JournalEntry.organization_id == org.id)) is None


@pytest.mark.asyncio
async def test_cross_tenant_cannot_queue_or_reject_document(client: AsyncClient, db_session):
    owner = Organization(slug="uat11-owner", legal_name="Owner"); other = Organization(slug="uat11-other", legal_name="Other")
    db_session.add_all([owner, other]); await db_session.flush()
    reviewer = User(organization_id=other.id, email="other@uat11.test", full_name="Other", password_hash="x", role=UserRole.MANAGER)
    db_session.add(reviewer); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(owner.id, io.BytesIO(b"%PDF-1.4\nprivate"), "private.pdf", "application/pdf", DocumentType.UNKNOWN)
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    headers = {"X-Organization-ID": str(other.id), "X-User-ID": str(reviewer.id)}
    assert (await client.get("/api/v1/documents/review-queue", headers=headers)).json() == []
    assert (await client.post(f"/api/v1/documents/{doc.id}/reject", headers=headers, json={"reason": "not mine"})).status_code == 404
