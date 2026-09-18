import pytest
from decimal import Decimal

from src.services.documents.table_extractor import extract_line_items_from_text
from src.services.documents.normalization import extract_document_monetary_totals


def test_three_item_multiline_invoice_extraction():
    """Requirement D: Real invoice sample with multiline item descriptions.

    Expected canonical items:
    Item 1:
      Description: "COVER / REPAIR STRIP\\nSIZE : 100 MM X 10.000 MM"
      Qty: 1, Unit: ROLL, Price: 3.100.000, Amount: 3.100.000
    Item 2:
      Description: "COVER / REPAIR STRIP\\nSIZE : 220 MM X 10.000 MM"
      Qty: 1, Unit: ROLL, Price: 6.300.000, Amount: 6.300.000
    Item 3:
      Description: "LEM SC 2000 + HARDENER UTR"
      Qty: 10, Unit: SET, Price: 620.000, Amount: 6.200.000
    Total: 15.600.000
    """
    invoice_text = """
    FAKTUR PENJUALAN
    PT BERKAT ANUGERAH TEKNIK
    No: INV/2026/09/0045
    Tanggal: 15 September 2026

    1. COVER / REPAIR STRIP
    SIZE : 100 MM X 10.000 MM
    1 ROLL 3.100.000 3.100.000

    2. COVER / REPAIR STRIP
    SIZE : 220 MM X 10.000 MM
    1 ROLL 6.300.000 6.300.000

    3. LEM SC 2000 + HARDENER UTR
    10 SET 620.000 6.200.000

    TOTAL: 15.600.000
    """

    items = extract_line_items_from_text(invoice_text)
    assert len(items) == 3, f"Expected 3 items, got {len(items)}"

    # Item 1 assertions
    item1 = items[0]
    assert item1.description == "COVER / REPAIR STRIP\nSIZE : 100 MM X 10.000 MM"
    assert item1.quantity == Decimal("1")
    assert (item1.unit or "").upper() == "ROLL"
    assert item1.unit_price == Decimal("3100000")
    assert item1.amount == Decimal("3100000")

    # Item 2 assertions (not merged with Item 1)
    item2 = items[1]
    assert item2.description == "COVER / REPAIR STRIP\nSIZE : 220 MM X 10.000 MM"
    assert item2.quantity == Decimal("1")
    assert (item2.unit or "").upper() == "ROLL"
    assert item2.unit_price == Decimal("6300000")
    assert item2.amount == Decimal("6300000")

    # Item 3 assertions (not lost)
    item3 = items[2]
    assert item3.description == "LEM SC 2000 + HARDENER UTR"
    assert item3.quantity == Decimal("10")
    assert (item3.unit or "").upper() == "SET"
    assert item3.unit_price == Decimal("620000")
    assert item3.amount == Decimal("6200000")

    # Total and sum invariants
    line_total_sum = sum(it.amount for it in items)
    assert line_total_sum == Decimal("15600000")

    totals = extract_document_monetary_totals(invoice_text)
    assert totals["total_amount"] == Decimal("15600000")
    assert line_total_sum == totals["total_amount"]


def test_three_item_invoice_horizontal_layout_variation():
    """Variant where description header and size numbers are grouped per row."""
    invoice_text = """
    COVER / REPAIR STRIP
    SIZE : 100 MM X 10.000 MM 1 ROLL 3.100.000 3.100.000
    COVER / REPAIR STRIP
    SIZE : 220 MM X 10.000 MM 1 ROLL 6.300.000 6.300.000
    LEM SC 2000 + HARDENER UTR 10 SET 620.000 6.200.000
    TOTAL 15.600.000
    """
    items = extract_line_items_from_text(invoice_text)
    assert len(items) == 3
    assert items[0].amount == Decimal("3100000")
    assert items[1].amount == Decimal("6300000")
    assert items[2].amount == Decimal("6200000")
    assert sum(it.amount for it in items) == Decimal("15600000")


def test_three_item_invoice_with_currency_and_dash_notation():
    """Variant with Rp prefix and trailing ,- notation on amounts."""
    invoice_text = """
    1. COVER / REPAIR STRIP
    SIZE : 100 MM X 10.000 MM
    1 ROLL Rp 3.100.000,- Rp 3.100.000,-

    2. COVER / REPAIR STRIP
    SIZE : 220 MM X 10.000 MM
    1 ROLL Rp 6.300.000,- Rp 6.300.000,-

    3. LEM SC 2000 + HARDENER UTR
    10 SET Rp 620.000,- Rp 6.200.000,-

    TOTAL: Rp 15.600.000,-
    """
    items = extract_line_items_from_text(invoice_text)
    assert len(items) == 3
    assert items[0].description == "COVER / REPAIR STRIP\nSIZE : 100 MM X 10.000 MM"
    assert items[0].quantity == Decimal("1")
    assert items[0].unit == "roll"
    assert items[0].unit_price == Decimal("3100000")
    assert items[0].amount == Decimal("3100000")

    assert items[1].description == "COVER / REPAIR STRIP\nSIZE : 220 MM X 10.000 MM"
    assert items[1].quantity == Decimal("1")
    assert items[1].unit == "roll"
    assert items[1].unit_price == Decimal("6300000")
    assert items[1].amount == Decimal("6300000")

    assert items[2].description == "LEM SC 2000 + HARDENER UTR"
    assert items[2].quantity == Decimal("10")
    assert items[2].unit == "set"
    assert items[2].unit_price == Decimal("620000")
    assert items[2].amount == Decimal("6200000")

    assert sum(it.amount for it in items) == Decimal("15600000")
    totals = extract_document_monetary_totals(invoice_text)
    assert totals["total_amount"] == Decimal("15600000")


def test_three_item_invoice_with_ocr_boxes():
    """Verify that 2D OCR geometry row clustering preserves all 3 items and SIZE specifications."""
    txts = [
        "1. COVER / REPAIR STRIP",
        "SIZE : 100 MM X 10.000 MM",
        "1 ROLL 3.100.000 3.100.000",
        "2. COVER / REPAIR STRIP",
        "SIZE : 220 MM X 10.000 MM",
        "1 ROLL 6.300.000 6.300.000",
        "3. LEM SC 2000 + HARDENER UTR",
        "10 SET 620.000 6.200.000",
        "TOTAL: 15.600.000",
    ]
    # Boxes simulated at reasonable y positions
    boxes = [
        [[20, 20], [200, 20], [200, 40], [20, 40]],
        [[20, 50], [250, 50], [250, 70], [20, 70]],
        [[20, 80], [300, 80], [300, 100], [20, 100]],
        [[20, 120], [200, 120], [200, 140], [20, 140]],
        [[20, 150], [250, 150], [250, 170], [20, 170]],
        [[20, 180], [300, 180], [300, 200], [20, 200]],
        [[20, 220], [350, 220], [350, 240], [20, 240]],
        [[20, 250], [300, 250], [300, 270], [20, 270]],
        [[20, 300], [200, 300], [200, 320], [20, 320]],
    ]
    raw_text = "\n".join(txts)
    items = extract_line_items_from_text(raw_text, ocr_boxes=boxes, ocr_txts=txts)
    assert len(items) == 3
    assert "SIZE : 100 MM X 10.000 MM" in items[0].description
    assert "SIZE : 220 MM X 10.000 MM" in items[1].description
    assert items[2].description == "LEM SC 2000 + HARDENER UTR"
    assert sum(it.amount for it in items) == Decimal("15600000")


def test_line_item_total_mismatch_routes_to_review():
    """Requirement 14: If line-item sum differs materially from extracted total,

    consistency validation must add AMOUNT_MISMATCH flag and route candidate to REVIEW_REQUIRED.
    """
    from src.models.enums import DocumentType, CandidateStatus, ReviewFlag
    from src.schemas.document import StructuredExtraction, LineItem
    from src.services.documents.candidate import derive_flags, build_candidate
    import uuid

    # 1. Matching total: sum(3.1m + 6.3m + 6.2m) == 15.6m -> No AMOUNT_MISMATCH flag
    clean_extraction = StructuredExtraction(
        total_amount=Decimal("15600000"),
        line_items=[
            LineItem(description="Item 1", amount=Decimal("3100000")),
            LineItem(description="Item 2", amount=Decimal("6300000")),
            LineItem(description="Item 3", amount=Decimal("6200000")),
        ],
        field_evidence={},
    )
    clean_flags = derive_flags(
        DocumentType.VENDOR_INVOICE,
        clean_extraction,
        {"counterparty_id": "c1", "project_id": "p1"},
        low_confidence=False,
    )
    assert ReviewFlag.AMOUNT_MISMATCH.value not in clean_flags

    # 2. Mismatching total: sum(15.6m) != total_amount(18.0m) -> AMOUNT_MISMATCH flag added
    mismatched_extraction = StructuredExtraction(
        total_amount=Decimal("18000000"),
        line_items=[
            LineItem(description="Item 1", amount=Decimal("3100000")),
            LineItem(description="Item 2", amount=Decimal("6300000")),
            LineItem(description="Item 3", amount=Decimal("6200000")),
        ],
        field_evidence={},
    )
    mismatch_flags = derive_flags(
        DocumentType.VENDOR_INVOICE,
        mismatched_extraction,
        {"counterparty_id": "c1", "project_id": "p1"},
        low_confidence=False,
    )
    assert ReviewFlag.AMOUNT_MISMATCH.value in mismatch_flags

    # Candidate status must become REVIEW_REQUIRED
    candidate = build_candidate(
        document_id=uuid.uuid4(),
        document_type=DocumentType.VENDOR_INVOICE,
        data=mismatched_extraction,
        matches={"counterparty_id": uuid.uuid4(), "project_id": uuid.uuid4()},
        flags=mismatch_flags,
    )
    assert candidate.status == CandidateStatus.REVIEW_REQUIRED
