import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.audit import AuditLog
from src.models.counterparty import Counterparty
from src.models.document import DocumentCorrection
from src.models.enums import (CandidateStatus, CostCategory, DocumentProcessingStatus,
                              DocumentType, ProjectStatus, TransactionType, UserRole)
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.project import Project
from src.models.receivable import CustomerInvoice
from src.models.user import User
from src.schemas.document import TransactionCandidate
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_review_correction_audits_and_converts_without_posting(client: AsyncClient, db_session):
    org = Organization(slug="doc-review", legal_name="Document Review Org")
    db_session.add(org); await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    manager = User(organization_id=org.id, email="manager@review.test", full_name="Manager",
                   password_hash="not-used", role=UserRole.MANAGER)
    customer = Counterparty(organization_id=org.id, name="Customer", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name="Vendor", is_vendor=True)
    db_session.add_all([manager, customer, vendor]); await db_session.flush()
    project = Project(organization_id=org.id, project_code="PRJ-2026-900", project_name="Review Project",
                      customer_id=customer.id, start_date=date(2026, 1, 1), project_status=ProjectStatus.ACTIVE,
                      original_contract_value=Decimal("0"), revised_contract_value=Decimal("0"))
    db_session.add(project); await db_session.flush()
    document = await DocumentService(db_session).ingest_document(org.id, io.BytesIO(b"%PDF-1.4\ninvoice"),
        "invoice.pdf", "application/pdf", DocumentType.VENDOR_INVOICE)
    candidate = TransactionCandidate(id=document.id, proposed_transaction_type=TransactionType.VENDOR_BILL,
        transaction_date=date(2026, 8, 30), amount=Decimal("1000.00"), currency_code="IDR",
        description="Vendor invoice", cost_category=CostCategory.MAT, status=CandidateStatus.REVIEW_REQUIRED)
    document.candidate_transaction = candidate.model_dump(mode="json")
    document.review_flags = ["PROJECT_UNKNOWN", "VENDOR_UNKNOWN"]
    document.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    corrected = await client.post(f"/api/v1/documents/{document.id}/corrections", headers=headers,
        json={"changes": {"project_id": str(project.id), "counterparty_id": str(vendor.id)}, "reason": "Verified source"})
    assert corrected.status_code == 200
    assert corrected.json()["processing_status"] == "READY_FOR_APPROVAL"
    assert corrected.json()["review_flags"] == []
    approved = await client.post(f"/api/v1/documents/{document.id}/approve", headers=headers)
    assert approved.status_code == 201
    assert approved.json()["workflow_status"] == "POSTED"
    assert await db_session.scalar(select(DocumentCorrection).where(DocumentCorrection.document_id == document.id))
    journal = await db_session.scalar(select(JournalEntry).where(JournalEntry.transaction_id == uuid.UUID(approved.json()["id"])))
    assert journal and journal.total_debit == journal.total_credit == Decimal("1000.00")
    approval_event = await db_session.scalar(select(AuditLog).where(
        AuditLog.entity_id == document.id, AuditLog.action == "APPROVE_CANDIDATE"
    ))
    assert approval_event and approval_event.new_values == {
        "transaction_id": approved.json()["id"], "journal_id": str(journal.id)
    }
    second = await client.post(f"/api/v1/documents/{document.id}/approve", headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_review_rejects_cross_tenant_master_ids(client: AsyncClient, db_session):
    org1 = Organization(slug="review-one", legal_name="One"); org2 = Organization(slug="review-two", legal_name="Two")
    db_session.add_all([org1, org2]); await db_session.flush()
    manager = User(organization_id=org1.id, email="manager@one.test", full_name="Manager", password_hash="x", role=UserRole.MANAGER)
    outsider = Counterparty(organization_id=org2.id, name="Outsider", is_vendor=True)
    db_session.add_all([manager, outsider]); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(org1.id, io.BytesIO(b"%PDF-1.4\ncross"),
        "cross.pdf", "application/pdf", DocumentType.VENDOR_INVOICE)
    doc.candidate_transaction = TransactionCandidate(id=doc.id, status=CandidateStatus.REVIEW_REQUIRED).model_dump(mode="json")
    doc.review_flags = ["VENDOR_UNKNOWN"]; doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    response = await client.post(f"/api/v1/documents/{doc.id}/corrections",
        headers={"X-Organization-ID": str(org1.id), "X-User-ID": str(manager.id)},
        json={"changes": {"counterparty_id": str(outsider.id)}, "reason": "invalid tenant"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_review_rejects_cross_tenant_allocation_target(client: AsyncClient, db_session):
    org1 = Organization(slug="allocation-one", legal_name="Allocation One")
    org2 = Organization(slug="allocation-two", legal_name="Allocation Two")
    db_session.add_all([org1, org2]); await db_session.flush()
    manager = User(organization_id=org1.id, email="manager@allocation.test", full_name="Manager",
                   password_hash="x", role=UserRole.MANAGER)
    customer = Counterparty(organization_id=org2.id, name="Other Customer", is_customer=True)
    db_session.add_all([manager, customer]); await db_session.flush()
    project = Project(organization_id=org2.id, project_code="PRJ-OTHER", project_name="Other Project",
                      customer_id=customer.id, start_date=date(2026, 1, 1), project_status=ProjectStatus.ACTIVE,
                      original_contract_value=Decimal("0"), revised_contract_value=Decimal("0"))
    db_session.add(project); await db_session.flush()
    invoice = CustomerInvoice(organization_id=org2.id, invoice_code="INV-OTHER", customer_id=customer.id,
                              project_id=project.id, invoice_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
                              total_amount=Decimal("1000"))
    db_session.add(invoice); await db_session.flush()
    doc = await DocumentService(db_session).ingest_document(
        org1.id, io.BytesIO(b"%PDF-1.4\nallocation"), "allocation.pdf", "application/pdf",
        DocumentType.TRANSFER_PROOF,
    )
    doc.candidate_transaction = TransactionCandidate(id=doc.id, status=CandidateStatus.REVIEW_REQUIRED).model_dump(mode="json")
    doc.review_flags = ["ACCOUNT_REVIEW"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    response = await client.post(f"/api/v1/documents/{doc.id}/corrections",
        headers={"X-Organization-ID": str(org1.id), "X-User-ID": str(manager.id)},
        json={"changes": {"allocation_target_id": str(invoice.id)}, "reason": "invalid tenant allocation"})

    assert response.status_code == 422
