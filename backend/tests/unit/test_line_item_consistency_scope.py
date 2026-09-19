from decimal import Decimal

from src.models.enums import DocumentType, ReviewFlag
from src.schemas.document import LineItem, StructuredExtraction
from src.services.documents.candidate import derive_flags

ITEMS = [
    LineItem(description="a", quantity="1", unit_price="750.00", amount="750.00", line_total="750.00"),
    LineItem(description="b", quantity="1", unit_price="250.00", amount="250.00", line_total="250.00"),
]


def _extraction(total: str) -> StructuredExtraction:
    return StructuredExtraction(
        transaction_date="2026-09-16",
        total_amount=Decimal(total),
        currency_code="IDR",
        line_items=ITEMS,
    )


def test_line_item_mismatch_ignored_for_evidence_documents():
    flags = derive_flags(DocumentType.BANK_STATEMENT, _extraction("19939750.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value not in flags


def test_line_item_mismatch_still_flagged_for_receipt():
    flags = derive_flags(DocumentType.RECEIPT, _extraction("19939750.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value in flags


def test_line_item_match_never_flags_for_invoice():
    flags = derive_flags(DocumentType.VENDOR_INVOICE, _extraction("1000.00"), {}, False)
    assert ReviewFlag.AMOUNT_MISMATCH.value not in flags
