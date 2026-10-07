import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient

from sqlalchemy import select

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import AccountType, DocumentProcessingStatus, DocumentType, NormalBalance, ProjectStatus, UserRole
from src.models.organization import Organization
from src.models.project import Project
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService


@pytest.fixture
async def evidence_env(db_session):
    org = Organization(slug="evidence-org", legal_name="Evidence Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="m@evidence.test",
        full_name="Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.commit()
    return {"org": org, "manager": manager}


@pytest.mark.asyncio
async def test_correcting_evidence_document_does_not_500(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.review_flags = ["OCR_LOW_CONFIDENCE"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"document_type": "BANK_STATEMENT"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    # A flag that the correction does not resolve keeps the document in review.
    assert resp.json()["processing_status"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_confirming_uncertain_evidence_document_archives_it(
    client: AsyncClient, db_session, evidence_env
):
    """A reviewer confirming/correcting the type is an authoritative signal.

    Even when OCR type confidence is below threshold, saving the document must
    archive it (PROCESSED) so it can leave the review queue.
    """
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.review_flags = []
    doc.confidence_scores = {"document_type_confidence": "0.75"}
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"document_type": "BANK_STATEMENT"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert resp.json()["processing_status"] == "PROCESSED"


@pytest.mark.asyncio
async def test_approving_evidence_document_is_rejected_clearly(client: AsyncClient, db_session, evidence_env):
    doc = await DocumentService(db_session).ingest_document(
        evidence_env["org"].id,
        io.BytesIO(b"%PDF-1.4\nmutasi"),
        "mutasi.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=evidence_env["manager"].id,
    )
    doc.candidate_transaction = {}
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(evidence_env["org"].id),
        "X-User-ID": str(evidence_env["manager"].id),
    }
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 409
    assert "Dokumen pendukung" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_correcting_evidence_to_transfer_proof_allows_direct_purchase_approval(
    client: AsyncClient, db_session, evidence_env
):
    org = evidence_env["org"]
    manager = evidence_env["manager"]

    await seed_standard_coa(db_session, org.id)
    cash_acc = await db_session.scalar(
        select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org.id,
            ChartOfAccount.account_code == "1101",
        )
    )
    payment_account = PaymentAccount(
        id=uuid.uuid4(),
        organization_id=org.id,
        coa_account_id=cash_acc.id,
        name="Bank Mandiri",
        bank_name="Mandiri",
        account_number="1200012500877",
        is_active=True,
    )
    customer = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Klien Conveyor",
        is_customer=True,
        is_vendor=False,
        is_active=True,
    )
    project = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-2026-CONVEYOR",
        project_name="Proyek Conveyor 1",
        project_status=ProjectStatus.ACTIVE,
        customer_id=customer.id,
        original_contract_value=Decimal("50000000.00"),
        start_date=date(2026, 1, 1),
    )
    db_session.add_all([payment_account, customer, project])
    await db_session.flush()

    # Ingest document misclassified as BANK_STATEMENT
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nmandiri-receipt"),
        "mandiri-receipt.pdf",
        "application/pdf",
        DocumentType.BANK_STATEMENT,
        created_by=manager.id,
    )
    doc.candidate_transaction = {}
    doc.extracted_data = {
        "total_amount": "1500000.00",
        "transaction_date": "2026-07-03",
        "transfer_reference": "202607031259641732",
    }
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()

    headers = {
        "X-Organization-ID": str(org.id),
        "X-User-ID": str(manager.id),
    }

    # Verify initially cannot be approved
    initial_app = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert initial_app.status_code == 409

    # Correct document type to TRANSFER_PROOF, specify direct expense for worker fee (LAB)
    corr_resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={
            "changes": {
                "document_type": "TRANSFER_PROOF",
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "cost_category": "LAB",
                "project_id": str(project.id),
                "payment_account_id": str(payment_account.id),
            },
            "reason": "Koreksi ke bukti transfer upah tenaga kerja proyek",
        },
    )
    assert corr_resp.status_code == 200
    corr_data = corr_resp.json()
    assert corr_data["document_type"] == "TRANSFER_PROOF"
    assert corr_data["candidate_transaction"]["proposed_transaction_type"] == "DIRECT_PURCHASE"
    assert corr_data["candidate_transaction"]["cost_category"] == "LAB"

    # Now approval succeeds
    app_resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["candidate_transaction"]["status"] in ("READY_TO_POST", "CONVERTED")

