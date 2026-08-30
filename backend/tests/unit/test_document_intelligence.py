import uuid
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from src.models.enums import DocumentType, ReviewFlag, TransactionType
from src.schemas.document import ConfidenceScores, StructuredExtraction
from src.services.documents.candidate import build_candidate, derive_flags
from src.services.documents.confidence import below_threshold
from src.services.documents.extraction import get_extraction_provider, register_extraction_provider


def test_strict_extraction_rejects_unknown_and_preserves_decimal():
    extraction = StructuredExtraction(total_amount=Decimal("15000000.00"), currency_code="IDR")
    assert extraction.total_amount == Decimal("15000000.00")
    with pytest.raises(ValidationError): StructuredExtraction.model_validate({"fabricated": "value"})


def test_low_critical_confidence_routes_review():
    scores = ConfidenceScores(ocr_confidence=".90", document_type_confidence=".90",
        entity_confidence=".90", project_confidence=".90", amount_confidence=".40")
    assert below_threshold(scores, ("ocr_confidence", "amount_confidence"))


def test_transfer_proof_never_becomes_expense_or_journal_instruction():
    data = StructuredExtraction(transaction_date=date(2026, 8, 30), total_amount=Decimal("8500000"), currency_code="IDR")
    candidate = build_candidate(uuid.uuid4(), DocumentType.TRANSFER_PROOF, data, {}, [ReviewFlag.VENDOR_UNKNOWN.value])
    assert candidate is not None and candidate.proposed_transaction_type is None
    payload = candidate.model_dump(mode="json")
    assert not ({"debit", "credit", "journal"} & set(payload))


def test_vendor_invoice_proposes_authorized_type_but_unknowns_review():
    data = StructuredExtraction(transaction_date=date(2026, 8, 30), total_amount=Decimal("100"), currency_code="IDR")
    flags = derive_flags(DocumentType.VENDOR_INVOICE, data, {}, False)
    assert set(flags) == {ReviewFlag.VENDOR_UNKNOWN.value, ReviewFlag.PROJECT_UNKNOWN.value}
    candidate = build_candidate(uuid.uuid4(), DocumentType.VENDOR_INVOICE, data, {}, flags)
    assert candidate and candidate.proposed_transaction_type == TransactionType.VENDOR_BILL


def test_project_document_does_not_force_financial_candidate():
    assert build_candidate(uuid.uuid4(), DocumentType.BAST, StructuredExtraction(), {}, []) is None


def test_provider_factory_keeps_processing_provider_replaceable():
    class TestProvider:
        async def extract(self, path, mime_type):  # pragma: no cover - factory boundary only
            raise AssertionError("not invoked")

    register_extraction_provider("unit-test-provider", TestProvider)
    assert isinstance(get_extraction_provider("UNIT-TEST-PROVIDER"), TestProvider)
