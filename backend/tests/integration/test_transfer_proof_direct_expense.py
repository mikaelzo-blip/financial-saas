import io
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.document import Document, DocumentProcessingStatus, DocumentType
from src.models.enums import CostCategory, UserRole
from src.models.organization import Organization
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa
from src.services.document_service import DocumentService

pytestmark = pytest.mark.asyncio


async def _org_user_account(db_session):
    org = Organization(slug="tp-direct", legal_name="Transfer Proof Direct Org")
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org.id)
    manager = User(
        organization_id=org.id,
        email="tp-approver@test.local",
        full_name="TP Approver",
        password_hash="x",
        role=UserRole.MANAGER,
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
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Mandiri",
        is_active=True,
    )
    db_session.add(account)
    await db_session.flush()
    return org, manager, account


async def _transfer_proof_doc(db_session, org, manager, candidate_extra: dict):
    doc = await DocumentService(db_session).ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\ntransfer-proof"),
        "bukti.pdf",
        "application/pdf",
        DocumentType.TRANSFER_PROOF,
        created_by=manager.id,
    )
    candidate = {
        "id": str(doc.id),
        "amount": "48930988.86",
        "transaction_date": "2026-08-13",
        "status": "READY_FOR_APPROVAL",
        "external_reference": "20708003319",
    }
    candidate.update(candidate_extra)
    doc.candidate_transaction = candidate
    doc.review_flags = []
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    await db_session.commit()
    return doc


async def test_transfer_proof_with_category_and_account_is_approved(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "expense_category": "OFFICE_ADMIN",
            "payment_account_id": str(account.id),
            "project_id": None,
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["candidate_transaction"]["status"] == "READY_TO_POST"


async def test_transfer_proof_direct_purchase_without_category_is_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "DIRECT_PURCHASE",
            "payment_account_id": str(account.id),
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
    assert "recording category" in resp.json()["detail"].lower()


async def test_transfer_proof_as_vendor_bill_still_rejected(client: AsyncClient, db_session):
    org, manager, account = await _org_user_account(db_session)
    doc = await _transfer_proof_doc(
        db_session, org, manager,
        {
            "proposed_transaction_type": "VENDOR_BILL",
            "payment_account_id": str(account.id),
        },
    )
    headers = {"X-Organization-ID": str(org.id), "X-User-ID": str(manager.id)}
    resp = await client.post(f"/api/v1/documents/{doc.id}/approve", headers=headers)
    assert resp.status_code == 422
