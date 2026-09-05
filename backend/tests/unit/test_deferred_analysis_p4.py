import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.inbox import InboxMessage, DocumentSession, MatchEvidence
from src.models.document import Document
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import (
    InboxMessageStatus,
    SessionMatchStatus,
    ProcessingPolicyDecision,
    DocumentProcessingStatus,
    DocumentType,
)
from src.services.deferred_analysis_service import DeferredAnalysisService


@pytest.mark.asyncio
async def test_deferred_analysis_evidence_and_policy_gates(db_session: AsyncSession):
    analysis_service = DeferredAnalysisService(db_session)

    org = Organization(slug=f"p4-org-{uuid.uuid4().hex[:6]}", legal_name="P4 Review Test PT")
    db_session.add(org)
    await db_session.flush()

    # Create known counterparty and project
    vendor = Counterparty(organization_id=org.id, name="PT Semen Nusantara", is_vendor=True)
    customer = Counterparty(organization_id=org.id, name="Owner Gedung", is_customer=True)
    db_session.add_all([vendor, customer])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        customer_id=customer.id,
        project_name="Gedung Olahraga",
        project_code="PRJ-GOR-01",
        start_date=datetime.now().date()
    )

    db_session.add(project)
    await db_session.flush()

    # Case 1: 99% AI confidence but UNKNOWN vendor -> MUST NOT AUTO-POST (Must be REVIEW_REQUIRED)
    doc_unverified = Document(
        organization_id=org.id,
        document_code="DOC-FAKE-99",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="invoice_99.pdf",
        storage_path="storage/fake.pdf",
        file_hash="hash99percentconfidence",
        file_size_bytes=1024,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.EXTRACTED,
        extracted_data={

            "confidence": "0.9900",  # > 95% AI confidence!
            "vendor_name": "Unknown Vendor X",
            "project_code": "PRJ-GOR-01"
        }
    )
    db_session.add(doc_unverified)
    await db_session.flush()

    sess_1 = DocumentSession(
        organization_id=org.id,
        session_code="SESS-P4-001",
        status=SessionMatchStatus.PENDING,
        document_id=doc_unverified.id
    )
    db_session.add(sess_1)
    await db_session.flush()

    analyzed_sess, decision = await analysis_service.analyze_session(org.id, sess_1.id)
    assert decision == ProcessingPolicyDecision.REVIEW_REQUIRED
    assert analyzed_sess.status == SessionMatchStatus.REVIEW_REQUIRED

    # Check match evidences recorded
    evidences = (await db_session.scalars(
        select(MatchEvidence).where(MatchEvidence.document_session_id == sess_1.id)
    )).all()
    assert len(evidences) >= 3
    rule_names = [e.rule_name for e in evidences]
    assert "COUNTERPARTY_UNKNOWN" in rule_names
    assert "PROJECT_IDENTIFIED" in rule_names

    # Case 2: Fully verified (Vendor identified, Project identified, Document Hash present) -> AUTO_SAFE
    doc_verified = Document(
        organization_id=org.id,
        document_code="DOC-VERIFIED-01",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="invoice_semen.pdf",
        storage_path="storage/semen.pdf",
        file_hash="hashverified123",
        file_size_bytes=2048,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.EXTRACTED,
        extracted_data={

            "confidence": "0.9500",
            "vendor_name": "PT Semen Nusantara",
            "project_code": "PRJ-GOR-01"
        }
    )
    db_session.add(doc_verified)
    await db_session.flush()

    sess_2 = DocumentSession(
        organization_id=org.id,
        session_code="SESS-P4-002",
        status=SessionMatchStatus.PENDING,
        document_id=doc_verified.id
    )
    db_session.add(sess_2)
    await db_session.flush()

    analyzed_sess_2, decision_2 = await analysis_service.analyze_session(org.id, sess_2.id)
    assert decision_2 == ProcessingPolicyDecision.AUTO_SAFE
    assert analyzed_sess_2.status == SessionMatchStatus.MATCHED

    # Case 3: Missing document attachment -> BLOCKED
    sess_3 = DocumentSession(
        organization_id=org.id,
        session_code="SESS-P4-003",
        status=SessionMatchStatus.PENDING,
        document_id=None
    )
    db_session.add(sess_3)
    await db_session.flush()

    analyzed_sess_3, decision_3 = await analysis_service.analyze_session(org.id, sess_3.id)
    assert decision_3 == ProcessingPolicyDecision.BLOCKED
    assert analyzed_sess_3.status == SessionMatchStatus.REVIEW_REQUIRED
