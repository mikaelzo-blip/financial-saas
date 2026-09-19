import io

import pytest
from httpx import AsyncClient

from src.models.enums import (
    DocumentProcessingStatus,
    DocumentType,
    ReviewFlag,
    UserRole,
)
from src.models.organization import Organization
from src.models.user import User
from src.services.document_service import DocumentService


@pytest.fixture
async def correction_env(db_session):
    org = Organization(slug="flag-resolution", legal_name="Flag Resolution Org")
    db_session.add(org)
    await db_session.flush()
    manager = User(
        organization_id=org.id,
        email="manager@flag.test",
        full_name="Manager",
        password_hash="x",
        role=UserRole.MANAGER,
    )
    db_session.add(manager)
    await db_session.commit()
    return {"org": org, "manager": manager}


async def _make_doc(db_session, env, flags, amount="19939750.00", ttype="DIRECT_PURCHASE"):
    doc = await DocumentService(db_session).ingest_document(
        env["org"].id,
        io.BytesIO(b"%PDF-1.4\nx"),
        "x.pdf",
        "application/pdf",
        DocumentType.RECEIPT,
        created_by=env["manager"].id,
    )
    doc.candidate_transaction = {
        "id": str(doc.id),
        "proposed_transaction_type": ttype,
        "amount": amount,
        "transaction_date": "2026-09-16",
        "currency_code": "IDR",
        "description": "x",
        "status": "REVIEW_REQUIRED",
    }
    doc.review_flags = list(flags)
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    return doc


@pytest.mark.asyncio
async def test_amount_correction_clears_amount_mismatch(client: AsyncClient, db_session, correction_env):
    doc = await _make_doc(db_session, correction_env, [ReviewFlag.AMOUNT_MISMATCH.value])
    headers = {
        "X-Organization-ID": str(correction_env["org"].id),
        "X-User-ID": str(correction_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"amount": "19939750.00"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert ReviewFlag.AMOUNT_MISMATCH.value not in resp.json()["review_flags"]


@pytest.mark.asyncio
async def test_date_correction_clears_date_mismatch(client: AsyncClient, db_session, correction_env):
    doc = await _make_doc(db_session, correction_env, [ReviewFlag.DATE_MISMATCH.value])
    headers = {
        "X-Organization-ID": str(correction_env["org"].id),
        "X-User-ID": str(correction_env["manager"].id),
    }
    resp = await client.post(
        f"/api/v1/documents/{doc.id}/corrections",
        headers=headers,
        json={"changes": {"transaction_date": "2026-09-16"}, "reason": "Verifikasi dokumen sumber"},
    )
    assert resp.status_code == 200
    assert ReviewFlag.DATE_MISMATCH.value not in resp.json()["review_flags"]
