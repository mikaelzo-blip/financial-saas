"""Regression tests for scanned invoices whose OCR text is laid out one field per line.

Real case: DOC-2026-000016 (PT TRIBEX, jasa angkut) - a scanned PDF where RapidOCR
reads each table cell on its own line:

    No.
    Description
    Amount (IDR)
    1
    JASA ANGKUT GERMAN TO JAKARTA
    19.927.250
    2
    STAMP
    10.000
    Total (IDR)
    19.937.250

The legacy line parser treated every "text + number" pair as an item and emitted 7
garbage rows (address fragments, dates, BL/AWB, footer text). The document's real
content is exactly 2 items.
"""
from decimal import Decimal

from src.services.documents.table_extractor import extract_line_items_from_text

TRIBEX_RAW = """PT TRIBEX TIGA BERJAYA EKSPRES
INVOICE #SI.2026.09.00022T
26-00012
Bill To :
Invoice Date
14 Sep2026
CV. CAKRAWALA BUANA LESTARI
Delivery Date
11 Sep2026
JL PAPANGGO II C, 27, PAPANGGO,
BL /AWB
6557228344
TANJUNG PRIOK
ETD
02 Sep2026
KOTA ADM.JAKARTA UTARA DKI JAKARTA
1434U
ETA
11 Sep 2026
No.
Description
Amount (IDR)
1
JASA ANGKUT GERMAN TO JAKARTA
19.927.250
2
STAMP
10.000
Total (IDR)
19.937.250
702.083.8889
Bank Account
BCA Duta Gardenia Branch
Account Name
PT Tribex Tiga Berjaya Ekspres
Notes
PT Tribex Tiga Berjaya Ekspres
CONDUCTIX-12005216
METERAI
TEMPEL
A0AOX125190238
TRIBEY
Halaman 1 dari1"""


def test_scanned_vertical_table_yields_only_real_items():
    items = extract_line_items_from_text(raw_text=TRIBEX_RAW)

    assert len(items) == 2, [i.description for i in items]
    assert items[0].description == "JASA ANGKUT GERMAN TO JAKARTA"
    assert items[0].amount == Decimal("19927250")
    assert items[1].description == "STAMP"
    assert items[1].amount == Decimal("10000")


def test_scanned_vertical_table_sum_matches_document_total():
    items = extract_line_items_from_text(raw_text=TRIBEX_RAW)
    assert sum(it.amount for it in items) == Decimal("19937250")


def test_scanned_vertical_table_ignores_address_and_footer_noise():
    items = extract_line_items_from_text(raw_text=TRIBEX_RAW)
    joined = " ".join((it.description or "").upper() for it in items)
    for noise in ("PAPANGGO", "BL /AWB", "TANJUNG PRIOK", "METERAI", "HALAMAN", "BANK ACCOUNT", "ETD"):
        assert noise not in joined, f"noise {noise!r} leaked into line items: {joined}"


def test_scanned_vertical_table_with_ocr_boxes_also_yields_two_items():
    # Same field-per-line content, but supplied as 1-D OCR geometry (each field its own box).
    txts = [ln for ln in TRIBEX_RAW.splitlines() if ln.strip()]
    boxes = [[[10, 10 + i * 14], [300, 10 + i * 14], [300, 24 + i * 14], [10, 24 + i * 14]] for i in range(len(txts))]

    items = extract_line_items_from_text(raw_text=TRIBEX_RAW, ocr_boxes=boxes, ocr_txts=txts)

    assert len(items) == 2, [i.description for i in items]
    assert items[0].description == "JASA ANGKUT GERMAN TO JAKARTA"
    assert items[0].amount == Decimal("19927250")
    assert items[1].description == "STAMP"
    assert items[1].amount == Decimal("10000")


def test_vertical_table_with_multi_line_description():
    raw = """PT CONTOH JAYA
No.
Description
Amount (IDR)
1
JASA ANGKUT GERMAN TO JAKARTA
VIA SURABAYA
19.927.250
2
STAMP
10.000
Total (IDR)
19.937.250"""
    items = extract_line_items_from_text(raw_text=raw)
    assert len(items) == 2
    assert items[0].description == "JASA ANGKUT GERMAN TO JAKARTA\nVIA SURABAYA"
    assert items[0].amount == Decimal("19927250")
    assert items[1].amount == Decimal("10000")


def test_horizontal_invoice_is_not_hijacked_by_vertical_parser():
    # No standalone "Description" header line -> legacy parser must stay in charge.
    raw = (
        "FAKTUR PENJUALAN\n"
        "Semen Gresik 50kg   20   sak   Rp 70.000   Rp 1.400.000\n"
        "Besi Beton 12mm   100   btg   Rp 95.000   Rp 9.500.000\n"
        "Total Rp 10.900.000\n"
    )
    items = extract_line_items_from_text(raw_text=raw)
    assert len(items) == 2
    assert items[0].description == "Semen Gresik 50kg"
    assert items[0].amount == Decimal("1400000")
    assert items[1].amount == Decimal("9500000")
