"""Unit tests for caption / OCR separation and supporting hints extraction."""
from src.models.enums import DocumentType
from src.services.documents.caption_hints import extract_caption_hints


def test_empty_or_none_caption():
    assert extract_caption_hints(None) == {
        "raw_caption": None,
        "document_type_hint": None,
        "project_hint": None,
        "payment_intent": None,
    }
    assert extract_caption_hints("") == {
        "raw_caption": None,
        "document_type_hint": None,
        "project_hint": None,
        "payment_intent": None,
    }
    assert extract_caption_hints("   ") == {
        "raw_caption": None,
        "document_type_hint": None,
        "project_hint": None,
        "payment_intent": None,
    }


def test_po_with_project_name():
    hints = extract_caption_hints("po roll arjer")
    assert hints["raw_caption"] == "po roll arjer"
    assert hints["document_type_hint"] == "PURCHASE_ORDER"
    assert hints["project_hint"] == "roll arjer"
    assert hints["payment_intent"] is None


def test_invoice_with_project_name():
    hints = extract_caption_hints("Invoice material beton proyek Menara Thamrin")
    assert hints["document_type_hint"] == "VENDOR_INVOICE"
    assert "Menara Thamrin" in hints["project_hint"]


def test_transfer_proof_caption():
    hints = extract_caption_hints("pelunasan proyek roll arjer")
    assert hints["document_type_hint"] == "TRANSFER_PROOF"
    assert hints["project_hint"] == "roll arjer"
    assert hints["payment_intent"] == "SETTLEMENT"


def test_transfer_proof_down_payment_caption():
    hints = extract_caption_hints("bayar dp roll arjer")
    assert hints["document_type_hint"] == "TRANSFER_PROOF"
    assert hints["project_hint"] == "roll arjer"
    assert hints["payment_intent"] == "DOWN_PAYMENT"


def test_spk_caption():
    hints = extract_caption_hints("SPK pekerjaan pondasi gedung olahraga")
    assert hints["document_type_hint"] == "SPK"
    assert "pekerjaan pondasi gedung olahraga" in hints["project_hint"]


def test_receipt_caption():
    hints = extract_caption_hints("Nota pembelian semen toko jaya")
    assert hints["document_type_hint"] == "RECEIPT"
    assert "semen toko jaya" in hints["project_hint"]
