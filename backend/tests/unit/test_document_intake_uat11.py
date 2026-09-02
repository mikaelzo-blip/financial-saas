from datetime import date
from decimal import Decimal

import pytest

from src.models.enums import DocumentType
from src.services.documents.normalization import parse_candidate_date, parse_candidate_money
from src.schemas.document import ExtractedField, StructuredExtraction
from src.services.documents.local_provider import classify_text


@pytest.mark.parametrize(("raw", "expected"), [
    ("Rp 1.250.000", Decimal("1250000")),
    ("1.250.000,00", Decimal("1250000.00")),
    ("1,250,000.00", Decimal("1250000.00")),
    ("Rp25,000,000", Decimal("25000000")),
])
def test_indonesian_and_international_money_are_decimal(raw, expected):
    candidate = parse_candidate_money(raw)
    assert candidate.value == expected
    assert candidate.validation_status == "VALID"


def test_ambiguous_money_separator_requires_review():
    candidate = parse_candidate_money("1,250")
    assert candidate.value is None
    assert candidate.validation_status == "AMBIGUOUS"


@pytest.mark.parametrize(("raw", "expected"), [
    ("2026-09-02", date(2026, 9, 2)),
    ("31/08/2026", date(2026, 8, 31)),
    ("31-08-2026", date(2026, 8, 31)),
])
def test_unambiguous_dates_are_normalized(raw, expected):
    assert parse_candidate_date(raw).value == expected


def test_ambiguous_date_requires_review():
    candidate = parse_candidate_date("02/09/2026")
    assert candidate.value is None
    assert candidate.validation_status == "AMBIGUOUS"


@pytest.mark.parametrize(("text", "kind"), [
    ("BUKTI TRANSFER BANK", DocumentType.TRANSFER_PROOF),
    ("STRUK PEMBELIAN TOKO", DocumentType.RECEIPT),
    ("VENDOR INVOICE", DocumentType.VENDOR_INVOICE),
    ("CUSTOMER INVOICE", DocumentType.CUSTOMER_INVOICE),
    ("PURCHASE ORDER", DocumentType.PURCHASE_ORDER),
    ("SURAT PERINTAH KERJA", DocumentType.SPK),
    ("BERITA ACARA SERAH TERIMA", DocumentType.BAST),
    ("SURAT JALAN", DocumentType.SURAT_JALAN),
    ("FAKTUR PAJAK", DocumentType.TAX_INVOICE),
    ("lampiran pendukung", DocumentType.UNKNOWN),
])
def test_contractor_document_classification_has_signals(text, kind):
    result = classify_text(text)
    assert result.document_type == kind
    assert result.reasons
    assert result.needs_review is (kind == DocumentType.UNKNOWN)


def test_extracted_fields_require_value_confidence_evidence_and_validation():
    extraction = StructuredExtraction(field_evidence={
        "total_amount": ExtractedField(value="1250000.00", confidence=Decimal("0.98"),
                                       evidence="page 1, bounding box 10,20,100,40",
                                       validation_status="VALID")
    })
    assert extraction.field_evidence["total_amount"].validation_status == "VALID"
    with pytest.raises(ValueError):
        StructuredExtraction(field_evidence={"total_amount": {"value": "1250000.00"}})
