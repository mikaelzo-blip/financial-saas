import uuid
from datetime import date
from decimal import Decimal

from src.models.enums import DocumentProcessingStatus, DocumentType
from src.schemas.document import ConfidenceScores, TransactionCandidate
from src.services.documents.status import (
    EVIDENCE_DOCUMENT_TYPES,
    document_type_is_confident,
    is_evidence_document,
    is_supporting_document,
    resolve_document_status,
)

CONFIDENT = {"document_type_confidence": "0.95"}
BORDERLINE = {"document_type_confidence": "0.85"}
UNCERTAIN = {"document_type_confidence": "0.75"}
WEAK = {"document_type_confidence": "0.30"}
MISSING = {}


def _candidate(document_type=DocumentType.TRANSFER_PROOF, proposed=None):
    return TransactionCandidate(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "t"),
        proposed_transaction_type=proposed,
        transaction_date=date(2026, 9, 2),
        amount=Decimal("1000000.00"),
        currency_code="IDR",
        description="x",
    )


def test_evidence_document_types_cover_supporting_plus_orphans():
    for t in (
        DocumentType.SPK, DocumentType.BAST, DocumentType.TAX_INVOICE,
        DocumentType.BANK_STATEMENT, DocumentType.QUOTATION,
        DocumentType.VARIATION_ORDER, DocumentType.SUBCONTRACT_AGREEMENT,
        DocumentType.PETTY_CASH_PROOF, DocumentType.CUSTOMER_RECEIPT,
    ):
        assert is_evidence_document(t) is True, t
    for t in (DocumentType.TRANSFER_PROOF, DocumentType.RECEIPT,
              DocumentType.VENDOR_INVOICE, DocumentType.CUSTOMER_INVOICE,
              DocumentType.UNKNOWN):
        assert is_evidence_document(t) is False, t


def test_evidence_document_types_accepts_strings():
    assert is_evidence_document("BANK_STATEMENT") is True
    assert is_evidence_document("VENDOR_INVOICE") is False
    assert is_evidence_document(None) is False


def test_supporting_document_is_subset_of_evidence():
    assert is_supporting_document(DocumentType.SPK) is True
    assert is_supporting_document(DocumentType.BANK_STATEMENT) is False
    assert len(EVIDENCE_DOCUMENT_TYPES) == 17


def test_document_type_is_confident_uses_inclusive_threshold():
    assert document_type_is_confident(CONFIDENT) is True
    assert document_type_is_confident(BORDERLINE) is True
    assert document_type_is_confident(WEAK) is False
    assert document_type_is_confident(MISSING) is False
    assert document_type_is_confident(None) is False


def test_document_type_is_confident_accepts_confidence_scores_object():
    scores = ConfidenceScores(
        ocr_confidence=".9", document_type_confidence=".9",
        entity_confidence=".9", project_confidence=".9", amount_confidence=".9",
    )
    assert document_type_is_confident(scores) is True


def test_financial_document_keeps_legacy_behavior():
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, _candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), [], CONFIDENT
    ) == DocumentProcessingStatus.READY_FOR_APPROVAL
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, _candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), ["VENDOR_UNKNOWN"], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_confident_without_flags_is_archived():
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], CONFIDENT
    ) == DocumentProcessingStatus.PROCESSED
    assert resolve_document_status(
        DocumentType.SPK, None, [], BORDERLINE
    ) == DocumentProcessingStatus.PROCESSED


def test_evidence_with_flag_stays_in_review():
    assert resolve_document_status(
        DocumentType.SPK, None, ["OCR_LOW_CONFIDENCE"], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_with_weak_or_missing_confidence_stays_in_review():
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], WEAK
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], MISSING
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], None
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_unknown_type_always_review_required():
    assert resolve_document_status(
        DocumentType.UNKNOWN, None, [], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_evidence_type_renamed_to_financial_returns_review():
    assert resolve_document_status(
        DocumentType.VENDOR_INVOICE, None, [], CONFIDENT
    ) == DocumentProcessingStatus.REVIEW_REQUIRED


def test_pipeline_reexports_document_status_for():
    from src.services.documents.pipeline import document_status_for as pipeline_status_for
    assert pipeline_status_for(_candidate(DocumentType.VENDOR_INVOICE, "VENDOR_BILL"), []) == \
        DocumentProcessingStatus.READY_FOR_APPROVAL


def test_human_type_confirmation_archives_uncertain_evidence():
    # OCR type confidence is below threshold, but a reviewer confirmed the type.
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, [], UNCERTAIN, type_confirmed=True
    ) == DocumentProcessingStatus.PROCESSED


def test_human_type_confirmation_still_blocked_by_remaining_flag():
    assert resolve_document_status(
        DocumentType.BANK_STATEMENT, None, ["AMOUNT_MISMATCH"], UNCERTAIN, type_confirmed=True
    ) == DocumentProcessingStatus.REVIEW_REQUIRED
