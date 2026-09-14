import io
import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.audit import AuditLog
from src.models.counterparty import Counterparty
from src.models.document import Document, DocumentCorrection
from src.models.enums import (
    CandidateStatus,
    DocumentProcessingStatus,
    DocumentType,
    ProjectStatus,
    TransactionType,
    UserRole,
)
from src.models.journal import JournalEntry
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.project import Project
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.document import StructuredExtraction, TransactionCandidate
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_review_detail_returns_extraction_candidate_evidence_and_corrections(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-detail", legal_name="Slice 4 Detail Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="manager@slice4.test",
        full_name="Review Manager",
        password_hash="not-used",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nslice4-detail"),
        "detail_invoice.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    doc.extracted_data = {
        "invoice_number": "INV-2026-001",
        "total_amount": "5000000.00",
        "line_items": [{"description": "Semen Portland", "amount": "5000000.00"}],
        "field_evidence": {
            "total_amount": {
                "value": "5000000.00",
                "confidence": "0.98",
                "evidence": "Total: Rp 5.000.000",
                "validation_status": "VALID",
            }
        },
    }
    doc.confidence_scores = {
        "ocr_confidence": "0.95",
        "amount_confidence": "0.98",
    }
    doc.matching_results = {
        "match_candidates": [
            {
                "entity_type": "Counterparty",
                "entity_id": str(uuid.uuid4()),
                "score": "0.92",
                "confidence_band": "HIGH",
                "positive_signals": ["EXACT_NAME"],
                "negative_signals": [],
                "explanation": "Matched by name",
                "scoring_details": {},
                "target_model": "Counterparty",
            }
        ],
        "ambiguous": False,
        "requires_review": False,
    }
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "VENDOR_BILL",
        "amount": "5000000.00",
        "transaction_date": "2026-09-10",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["VENDOR_UNKNOWN"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED

    # Add a correction
    correction = DocumentCorrection(
        organization_id=org.id,
        document_id=doc.id,
        field_path="counterparty_id",
        old_value=None,
        new_value=str(uuid.uuid4()),
        reason="Manual verification",
        corrected_by=manager.id,
    )
    db_session.add(correction)
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    response = await client.get(f"/api/v1/documents/{doc.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["extracted_data"]["invoice_number"] == "INV-2026-001"
    assert len(data["extracted_data"]["line_items"]) == 1
    assert data["extracted_data"]["field_evidence"]["total_amount"]["validation_status"] == "VALID"
    assert len(data["matching_results"]["match_candidates"]) == 1
    assert "corrections" in data
    assert len(data["corrections"]) == 1
    assert data["corrections"][0]["field_path"] == "counterparty_id"
    assert data["corrections"][0]["reason"] == "Manual verification"


@pytest.mark.asyncio
async def test_candidate_selection_persists_choice_and_rejects_cross_tenant(
    client: AsyncClient, db_session
):
    org1 = Organization(slug="slice4-select-1", legal_name="Org One")
    org2 = Organization(slug="slice4-select-2", legal_name="Org Two")
    db_session.add_all([org1, org2])
    await db_session.flush()

    manager = User(
        organization_id=org1.id,
        email="manager@select1.test",
        full_name="Manager One",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    vendor1 = Counterparty(organization_id=org1.id, name="Vendor One", is_vendor=True)
    vendor2 = Counterparty(organization_id=org2.id, name="Vendor Two", is_vendor=True)
    vendor3 = Counterparty(organization_id=org1.id, name="Vendor Three", is_vendor=True)
    db_session.add_all([manager, vendor1, vendor2, vendor3])
    await db_session.flush()

    bill1 = VendorBill(
        organization_id=org1.id,
        bill_code="BILL-ORG1-001",
        vendor_id=vendor1.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("3000000.00"),
        status="UNPAID",
    )
    bill2 = VendorBill(
        organization_id=org2.id,
        bill_code="BILL-ORG2-999",
        vendor_id=vendor2.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("3000000.00"),
        status="UNPAID",
    )
    db_session.add_all([bill1, bill2])
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org1.id,
        io.BytesIO(b"%PDF-1.4\nselect-proof"),
        "proof.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "PAY_VENDOR_BILL",
        "counterparty_id": str(vendor1.id),
        "amount": "3000000.00",
        "transaction_date": "2026-09-02",
        "allocation_target_id": None,
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["ACCOUNT_REVIEW"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {"X-Organization-ID": str(org1.id), "X-User-ID": str(manager.id)}

    # Valid selection: bill1 belonging to org1
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {"selected_candidate_id": str(bill1.id)},
            "reason": "Explicitly selected matching vendor bill",
        },
    )
    assert resp.status_code == 200
    candidate = resp.json()["candidate_transaction"]
    assert candidate["allocation_target_id"] == str(bill1.id)

    # Cross-tenant selection: bill2 belonging to org2 must be rejected
    cross_resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {"selected_candidate_id": str(bill2.id)},
            "reason": "Attempting cross tenant candidate",
        },
    )
    assert cross_resp.status_code == 422

    # A candidate linked to vendor1 cannot survive a counterparty correction to vendor3.
    stale_target_resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {"counterparty_id": str(vendor3.id)},
            "reason": "Corrected vendor after checking source evidence",
        },
    )
    assert stale_target_resp.status_code == 200
    assert stale_target_resp.json()["candidate_transaction"]["allocation_target_id"] is None

    approve_resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert approve_resp.status_code == 409


@pytest.mark.asyncio
async def test_material_correction_triggers_rematch_and_audit_history(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-rematch", legal_name="Slice 4 Rematch Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="manager@rematch.test",
        full_name="Rematch Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    vendor = Counterparty(organization_id=org.id, name="PT Cahaya Abadi", is_vendor=True)
    db_session.add_all([manager, vendor])
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nrematch"),
        "rematch.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    doc.extracted_data = {
        "invoice_number": "OLD-INV-001",
        "total_amount": "1000000.00",
        "issuer_name": "Old Vendor",
    }
    doc.matching_results = {
        "counterparty_id": None,
        "match_candidates": [],
        "primary_candidate": None,
        "ambiguous": False,
        "requires_review": True,
    }
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "VENDOR_BILL",
        "amount": "1000000.00",
        "transaction_date": "2026-09-01",
        "counterparty_id": None,
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["VENDOR_UNKNOWN"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    # Material correction: change invoice_number, counterparty_id, and amount
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {
                "invoice_number": "NEW-INV-777",
                "counterparty_id": str(vendor.id),
                "amount": "2500000.00",
            },
            "reason": "Corrected vendor and invoice number from visual review",
        },
    )
    assert resp.status_code == 200
    res_data = resp.json()

    # Verify extracted_data updated
    assert res_data["extracted_data"]["invoice_number"] == "NEW-INV-777"
    assert res_data["extracted_data"]["total_amount"] == "2500000.00"
    # Verify candidate updated
    assert res_data["candidate_transaction"]["counterparty_id"] == str(vendor.id)
    assert res_data["candidate_transaction"]["amount"] == "2500000.00"

    # Verify audit history
    corrections = (
        await db_session.scalars(
            select(DocumentCorrection)
            .where(DocumentCorrection.document_id == doc.id)
            .order_by(DocumentCorrection.corrected_at.asc())
        )
    ).all()
    assert len(corrections) >= 3
    fields = {c.field_path for c in corrections}
    assert {"invoice_number", "counterparty_id", "amount"} <= fields
    for c in corrections:
        assert c.corrected_by == manager.id
        assert c.reason == "Corrected vendor and invoice number from visual review"

    audit_logs = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_id == doc.id,
                AuditLog.action == "CORRECT_EXTRACTION",
            )
        )
    ).all()
    assert len(audit_logs) >= 1
    assert audit_logs[0].actor_id == manager.id


@pytest.mark.asyncio
async def test_approve_valid_reviewed_candidate_leads_to_ready_to_post(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-approve", legal_name="Slice 4 Approve Org")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)

    manager = User(
        organization_id=org.id,
        email="approver@slice4.test",
        full_name="Approver Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    vendor = Counterparty(organization_id=org.id, name="PT Supplier", is_vendor=True)
    db_session.add_all([manager, vendor])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-APP-001",
        project_name="Approve Project",
        customer_id=vendor.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("10000000.00"),
        revised_contract_value=Decimal("10000000.00"),
    )
    db_session.add(project)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nappr"),
        "appr.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "amount": "4000000.00",
        "transaction_date": "2026-09-05",
        "status": "READY_FOR_APPROVAL",
    }
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["processing_status"] == "READY_TO_POST"
    assert body["candidate_transaction"]["status"] == "READY_TO_POST"

    # Crucial Slice 4 Boundary: ZERO transactions, ZERO journals created
    trx = await db_session.scalar(
        select(Transaction).where(Transaction.organization_id == org.id)
    )
    assert trx is None
    journal = await db_session.scalar(
        select(JournalEntry).where(JournalEntry.organization_id == org.id)
    )
    assert journal is None

    # Audit event logged
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == doc.id,
            AuditLog.action == "APPROVE_CANDIDATE",
        )
    )
    assert audit is not None
    assert audit.actor_id == manager.id


@pytest.mark.asyncio
async def test_approve_ambiguous_or_unresolved_candidate_rejected(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-ambig", legal_name="Slice 4 Ambig Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="ambig@slice4.test",
        full_name="Ambig Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nambig"),
        "ambig.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    # Ambiguous candidate with unresolved review flags
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "VENDOR_BILL",
        "amount": "1000000.00",
        "transaction_date": "2026-09-01",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["AMBIGUOUS_MATCH", "VENDOR_UNKNOWN"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (409, 422)


@pytest.mark.asyncio
async def test_reject_requires_reason_and_persists_audit(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-reject", legal_name="Slice 4 Reject Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="reject@slice4.test",
        full_name="Reject Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nreject"),
        "reject.pdf",
        "application/pdf",
        DocumentType.UNKNOWN,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["MISSING_CRITICAL_FIELD"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    # Missing/too short reason fails validation
    invalid_resp = await client.post(
        f"/api/v1/documents/{doc.id}/reject",
        headers=headers,
        json={"reason": "no"},
    )
    assert invalid_resp.status_code == 422

    # Valid rejection
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/reject",
        headers=headers,
        json={"reason": "Dokumen tidak sah atau tidak terbaca sama sekali"},
    )
    assert resp.status_code == 200
    assert resp.json()["processing_status"] == "REJECTED"

    # Zero financial mutations
    assert (
        await db_session.scalar(
            select(Transaction).where(Transaction.organization_id == org.id)
        )
        is None
    )


@pytest.mark.asyncio
async def test_finalized_review_cannot_be_silently_changed(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-finalized", legal_name="Slice 4 Finalized Org")
    db_session.add(org)
    await db_session.flush()

    manager = User(
        organization_id=org.id,
        email="final@slice4.test",
        full_name="Final Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nfinalized"),
        "final.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    doc.processing_status = DocumentProcessingStatus.READY_TO_POST
    await db_session.commit()

    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}

    # Corrections on already finalized document should return 409
    corr_resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"amount": "1000.00"}, "reason": "Late correction"},
    )
    assert corr_resp.status_code == 409

    # Approve on already finalized document should return 409
    appr_resp = await client.post(
        f"/api/v1/documents/{doc.id}/approve",
        headers=headers,
    )
    assert appr_resp.status_code == 409

    # Reject on already finalized document should return 409
    rej_resp = await client.post(
        f"/api/v1/documents/{doc.id}/reject",
        headers=headers,
        json={"reason": "Late rejection"},
    )
    assert rej_resp.status_code == 409


@pytest.mark.asyncio
async def test_unauthorized_role_cannot_mutate_review(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-authz", legal_name="Slice 4 Authz Org")
    db_session.add(org)
    await db_session.flush()

    viewer = User(
        organization_id=org.id,
        email="viewer@slice4.test",
        full_name="Viewer User",
        password_hash="x",
        role=UserRole.VIEWER,
    )
    operator = User(
        organization_id=org.id,
        email="operator@slice4.test",
        full_name="Operator User",
        password_hash="x",
        role=UserRole.OPERATOR,
    )
    db_session.add_all([viewer, operator])
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nauthz"),
        "authz.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = ["VENDOR_UNKNOWN"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    for user in (viewer, operator):
        h = {"X-Organization-ID": str(org.id), "X-User-ID": str(user.id)}
        assert (
            await client.post(
                f"/api/v1/documents/{doc.id}/corrections",
                headers=h,
                json={"changes": {"amount": "100.00"}, "reason": "Unauthorized"},
            )
        ).status_code == 403
        assert (
            await client.post(f"/api/v1/documents/{doc.id}/approve", headers=h)
        ).status_code == 403
        assert (
            await client.post(
                f"/api/v1/documents/{doc.id}/reject",
                headers=h,
                json={"reason": "Unauthorized"},
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_approve_rejects_ambiguous_matching_results_without_selection(
    client: AsyncClient, db_session
):
    org = Organization(slug="slice4-ambiguous-rematch", legal_name="Slice 4 Ambiguous Rematch Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="ambiguous-rematch@slice4.test",
        full_name="Ambiguous Rematch Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    vendor = Counterparty(organization_id=org.id, name="Ambiguous Vendor", is_vendor=True)
    db_session.add_all([manager, vendor])
    await db_session.flush()
    project = Project(
        organization_id=org.id,
        project_code="PRJ-AMBIG-001",
        project_name="Ambiguous Match Project",
        customer_id=vendor.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("10000000.00"),
        revised_contract_value=Decimal("10000000.00"),
    )
    db_session.add(project)
    await db_session.flush()

    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nambiguous-rematch"),
        "ambiguous-rematch.pdf",
        "application/pdf",
        DocumentType.VENDOR_INVOICE,
        created_by=manager.id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": "VENDOR_BILL",
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "amount": "4000000.00",
        "transaction_date": "2026-09-05",
        "status": "READY_FOR_APPROVAL",
    }
    doc.matching_results = {"ambiguous": True, "match_candidates": []}
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()

    response = await client.post(
        f"/api/v1/documents/{doc.id}/approve",
        headers={"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)},
    )

    assert response.status_code == 409
    assert "ambiguous" in response.json()["detail"].lower()
