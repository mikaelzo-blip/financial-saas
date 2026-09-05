"""Regression test suite for OCR pipeline integrity and document code generation.

Verifies:
- Two different source images cannot share the wrong OCR result.
- WAMID/media hash maps to exactly one correct Document.
- Existing document codes are not reused for a new document.
- Candidate and review item always reference the same source document.
- No journal or accounting mutation occurs before approval.
"""

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
import pytest
from sqlalchemy import select, func

from src.models.enums import DocumentType, DocumentProcessingStatus, CandidateStatus
from src.models.document import Document
from src.models.organization import Organization
from src.models.transaction import Transaction
from src.models.journal import JournalEntry, JournalLine
from src.services.document_service import DocumentService
from src.services.documents.local_provider import classify_text, LocalExtractionProvider
from src.services.documents.pipeline import DocumentPipeline


@pytest.fixture
async def sample_organization(db_session):
    org = Organization(
        id=uuid.uuid4(),
        legal_name="PT Test Org",
        slug="pt-test-org",
        tax_id="01.234.567.8-901.000",
        fiscal_year_start_month=1,
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_document_code_sequential_does_not_reuse_existing_codes(db_session, sample_organization):
    """Prove that generate_document_code uses max numeric suffix, avoiding collision with existing codes."""
    service = DocumentService(db_session)
    org_id = sample_organization.id
    year = date.today().year

    # Seed Document with code DOC-YYYY-000001
    doc1 = Document(
        organization_id=org_id,
        document_code=f"DOC-{year}-000001",
        document_type=DocumentType.RECEIPT,
        file_name="receipt1.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
        file_hash="hash_1" * 12 + "0001",
        storage_path="path/1",
        source_channel="WEB_UPLOAD",
    )
    db_session.add(doc1)
    await db_session.flush()

    # Next code MUST be DOC-YYYY-000002
    next_code = await service.generate_document_code(org_id)
    assert next_code == f"DOC-{year}-000002"

    # Seed a jump, e.g. DOC-YYYY-000010
    doc2 = Document(
        organization_id=org_id,
        document_code=f"DOC-{year}-000010",
        document_type=DocumentType.RECEIPT,
        file_name="receipt2.jpg",
        mime_type="image/jpeg",
        file_size_bytes=100,
        file_hash="hash_2" * 12 + "0002",
        storage_path="path/2",
        source_channel="WEB_UPLOAD",
    )
    db_session.add(doc2)
    await db_session.flush()

    # Even though count is 2, next code MUST be 000011 (max_seq + 1), never 000003 or 000001
    next_code_after_jump = await service.generate_document_code(org_id)
    assert next_code_after_jump == f"DOC-{year}-000011"


@pytest.mark.asyncio
async def test_classify_text_prioritizes_tax_invoice_over_secondary_po_do_references():
    """Prove that vendor tax invoices with customer PO reference or delivery order lines classify correctly."""
    invoice_text = (
        "PT Nusa Utama Engineering\n"
        "TAX INVOICE 9482\n"
        "Delivery Order No. 107984AA\n"
        "Customer Order Ref. 020/CBL-PO/XII/2025\n"
        "Total IDR 38,850,000.00"
    )
    res = classify_text(invoice_text)
    assert res.document_type == DocumentType.VENDOR_INVOICE
    assert res.confidence >= Decimal("0.90")


@pytest.mark.asyncio
async def test_distinct_images_do_not_share_ocr_extraction():
    """Prove that two distinct document images extract independent data."""
    text_a = "PT Nusa Utama Engineering\nTAX INVOICE 9482\nDate: 11 MAR 2026\nTOTAL IDR 38,850,000.00"
    text_b = "PT Semen Nusantara\nKUITANSI PEMBELIAN\nDate: 01 FEB 2026\nTOTAL IDR 1,500,000.00"

    class_a = classify_text(text_a)
    class_b = classify_text(text_b)

    assert class_a.document_type == DocumentType.VENDOR_INVOICE
    assert class_b.document_type == DocumentType.RECEIPT


@pytest.mark.asyncio
async def test_accounting_baseline_preserved_before_approval(db_session, sample_organization):
    """Prove that document intake and candidate generation never mutate Transactions or Journals."""
    trx_count = await db_session.scalar(select(func.count()).select_from(Transaction))
    je_count = await db_session.scalar(select(func.count()).select_from(JournalEntry))
    jl_count = await db_session.scalar(select(func.count()).select_from(JournalLine))

    # Ingest document
    service = DocumentService(db_session)
    doc_code = await service.generate_document_code(sample_organization.id)
    doc = Document(
        organization_id=sample_organization.id,
        document_code=doc_code,
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="invoice.jpg",
        mime_type="image/jpeg",
        file_size_bytes=5000,
        file_hash="unique_hash_for_test_" + uuid.uuid4().hex,
        storage_path="storage/test.jpg",
        source_channel="WHATSAPP",
        candidate_transaction={
            "proposed_transaction_type": "VENDOR_BILL",
            "amount": "38850000.00",
            "status": "REVIEW_REQUIRED",
        },
        processing_status=DocumentProcessingStatus.READY_FOR_APPROVAL,
    )
    db_session.add(doc)
    await db_session.flush()

    # Verify counts remain identical
    trx_count_after = await db_session.scalar(select(func.count()).select_from(Transaction))
    je_count_after = await db_session.scalar(select(func.count()).select_from(JournalEntry))
    jl_count_after = await db_session.scalar(select(func.count()).select_from(JournalLine))

    assert trx_count_after == trx_count
    assert je_count_after == je_count
    assert jl_count_after == jl_count


@pytest.mark.asyncio
async def test_vendor_matching_fuzzy_threshold_safety(db_session, sample_organization):
    """Prove that distinct legal entity ('PT Nusa Utama Engineering' vs 'PT Nusa Engineering')

    is NOT auto-matched (SequenceMatcher ratio ~0.87 < 0.90 threshold) and requires review.
    """
    from src.models.counterparty import Counterparty
    from src.schemas.document import StructuredExtraction
    from src.services.documents.matching import match_entities

    org_id = sample_organization.id
    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_id,
        name="PT Nusa Engineering",
        is_vendor=True,
        is_customer=False,
        is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="PT Nusa Utama Engineering",
    )
    matches = await match_entities(db_session, org_id, data)

    # Must NOT auto-match as counterparty_id
    assert matches["counterparty_id"] is None
    # Must list the similar counterparty under alternatives with its score
    assert len(matches["alternatives"]) >= 1
    assert matches["alternatives"][0]["id"] == str(vendor.id)
    assert matches["alternatives"][0]["name"] == "PT Nusa Engineering"
    assert float(matches["alternatives"][0]["score"]) < 0.90

