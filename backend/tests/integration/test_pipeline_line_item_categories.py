"""Regression: the pipeline must PERSIST per-line category suggestions.

`build_candidate` fills a suggested category on each in-memory `LineItem`, but
`pipeline.py` serialises `extracted_data` BEFORE calling it, so without an
explicit re-serialisation the suggestions never reach the persisted JSON that
the corrections endpoint (Task 6) and the posting path (Task 7) read.
"""
import io
from datetime import date
from decimal import Decimal

import pytest

from src.models.organization import Organization
from src.models.enums import DocumentType, DocumentProcessingStatus
from src.schemas.document import ConfidenceScores, LineItem, StructuredExtraction
from src.services.document_service import DocumentService
from src.services.documents.extraction import ExtractionResult, ScriptedExtractionProvider
from src.services.documents.pipeline import DocumentPipeline


@pytest.fixture
async def pipeline_org(db_session):
    org = Organization(id=None, legal_name="PT Pipeline Category Test", slug="pt-pipeline-cat-test")
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_pipeline_persists_per_line_category_suggestions(db_session, pipeline_org, tmp_path):
    org_id = pipeline_org.id
    doc_service = DocumentService(db_session)
    doc_service.storage.base_dir = tmp_path

    doc = await doc_service.ingest_document(
        org_id, io.BytesIO(b"%PDF-1.4\nVendor invoice"), "vendor_invoice.pdf",
        "application/pdf", DocumentType.VENDOR_INVOICE,
    )

    extraction = StructuredExtraction(
        transaction_date=date(2026, 9, 14),
        total_amount=Decimal("19937250"),
        line_items=[
            LineItem(description="JASA ANGKUT GERMAN TO JAKARTA", amount=Decimal("19927250")),
            LineItem(description="STAMP", amount=Decimal("10000")),
        ],
    )
    scores = ConfidenceScores(
        ocr_confidence=Decimal("0.95"), document_type_confidence=Decimal("0.95"),
        entity_confidence=Decimal("0.90"), project_confidence=Decimal("0.00"),
        amount_confidence=Decimal("0.95"),
    )
    provider = ScriptedExtractionProvider(ExtractionResult(
        DocumentType.VENDOR_INVOICE, extraction, scores, "scripted", "1.0.0"
    ))

    await DocumentPipeline(db_session, provider).process(
        doc, doc_service.storage.get_file_path(doc.storage_path)
    )
    await db_session.flush()

    assert doc.processing_status != DocumentProcessingStatus.FAILED

    persisted = doc.extracted_data
    line_items = persisted["line_items"]
    assert line_items[0]["cost_category"] == "LOG"
    assert line_items[1]["expense_category"] == "OTHER_OPERATIONAL"
