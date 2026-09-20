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


TRIBEX_CLUSTERED = """PT TRIBEX TIGA BERJAYA EKSPRES
INVOICE #SI.2026.09.00022T   26-00012
Bill To :   Invoice Date   14 Sep2026
CV. CAKRAWALA BUANA LESTARI   Delivery Date   11 Sep2026
JL PAPANGGO II C, 27, PAPANGGO,   BL /AWB   6557228344
TANJUNG PRIOK
ETD   02 Sep2026
KOTA ADM.JAKARTA UTARA DKI JAKARTA
1434U   ETA   11 Sep 2026
No.   Description   Amount (IDR)
1   JASA ANGKUT GERMAN TO JAKARTA   19.927.250
2   STAMP   10.000
Total (IDR)   19.937.250
702.083.8889
Bank Account
BCA Duta Gardenia Branch
Account Name   PT Tribex Tiga Berjaya Ekspres
Notes   PT Tribex Tiga Berjaya Ekspres
CONDUCTIX-12005216
METERAI
TEMPEL
A0AOX125190238
TRIBEY
Halaman 1 dari1"""


def test_clustered_horizontal_table_extracts_only_real_items():
    items = extract_line_items_from_text(raw_text=TRIBEX_CLUSTERED)
    assert len(items) == 2, [f"{i.description} ({i.amount})" for i in items]
    assert items[0].description == "JASA ANGKUT GERMAN TO JAKARTA"
    assert items[0].amount == Decimal("19927250")
    assert items[1].description == "STAMP"
    assert items[1].amount == Decimal("10000")
    assert sum(it.amount for it in items) == Decimal("19937250")
    joined = " ".join((it.description or "").upper() for it in items)
    for noise in ("PAPANGGO", "BL /AWB", "TANJUNG PRIOK", "METERAI", "HALAMAN", "BANK ACCOUNT", "ETD", "ETA"):
        assert noise not in joined


def test_single_amount_line_item_without_explicit_quantity():
    raw = (
        "FAKTUR PENJUALAN\n"
        "Vendor: PT Nusa Engineering\n"
        "Invoice No: INV-2026-E2E-1139\n"
        "Tanggal: 20-Sep-2026\n"
        "Jatuh Tempo: 30-Sep-2026\n"
        "Proyek: PRJ-2026-001\n"
        "Deskripsi Barang / Jasa:\n"
        " 1. Pengadaan Material Panel Listrik - Rp 5.000.000\n"
        "Subtotal: Rp 5.000.000\n"
        "PPN 11%: Rp 550.000\n"
        "Grand Total: Rp 5.550.000\n"
    )
    items = extract_line_items_from_text(raw_text=raw)
    assert len(items) == 1, [f"{i.description} ({i.amount})" for i in items]
    assert items[0].description == "Pengadaan Material Panel Listrik"
    assert items[0].amount == Decimal("5000000")


def test_receipt_line_item_with_multiline_and_total():
    raw = (
        "KWITANSI PEMBELIAN MATERIAL (SINTETIS)\n"
        "No: KW-WA-20260920-002\n"
        "Toko Bangunan Sumber Rejeki\n"
        "Tanggal: 2026-09-20\n"
        "Cat Tembok Propan 25kg (E2E-TEST-20260920-1505)\n"
        "Rp 1.250.000\n"
        "Total Bayar:\n"
        "Rp 1.250.000\n"
    )
    items = extract_line_items_from_text(raw_text=raw)
    assert len(items) == 1, [f"{i.description} ({i.amount})" for i in items]
    assert "Cat Tembok Propan 25kg" in items[0].description
    assert items[0].amount == Decimal("1250000")


CBC_CLUSTERED = """PT CBC Indonesia
CBC   BEARINGS-POWERTRANSMISSION   NPWP:   SECURE BUILDING BLOK C   21.100.587.9-004.000   MiMOTION
ENGINEERED SOLUTIONS   INDONESIA   JAKARTA TIMUR   JL RAYA PROTOKOL HALIM PERDANAKUSUMA   13610
Ph: 62 21 2922 1400
Fax: 62 21 2922 1499   TAX INVOICE 357550
Date: 20 FEB 2026
Bill To:   CV CAKRAWALA BUANA LESTARI   Deliver To:   CV CAKRAWALA BUANA
JL PAPANGGO II C, 27.   PAPANGGO TANJUNG PRIOK   JL PAPANGGO IIC NO 27 RT 008 RW 003   PAPANGGO TANJUNG PRIOK
KOTA ADM JAKARTA UTARA   DKI JAKARTA   14340   KOTA ADM JAKARTA UTARA   DKI JAKARTA
Ph: +62 21 26063396   Fax: +62   Ph: 21 26063396   Fax:
Account   Customer Order Ref.   Warehouse   Rep   Delivery Order No.   Credit Terms
C00773   018/CBL-PO/XII/2025   CSUB   729   1169169   30 Days
Item Code   Item Description   Ordered   Shipped   Ln#   PO   UOM   Unit Price   Line Total
WHX126TP   WELDEDSTEEL CRANKED LINK   CHAIN   360   360   0   EACH   1,300,000.00   468,000,000.00
WHX126TP - 103.630MM PITCH
payable to PT CBC Indonesia Live.   Cheques should be crossed and made   PAYMENT TO BE MADE TO:   Ex Tax   IDR   468,000,000.00
to General Conditions of Sale. a copy of   oo e ae s ses e seet   BANK ANZ INDONESIA - ANZ TOWER   PT CBC INDONESIA   VAT   IDR   51,480,000.00
wide on o e n on   JAKARTA - SWFT # ANZBIDJX   (IDR) ACC# 427021-01-00001   TOTAL   IDR   519,480,000.00
For PT CBC Indonesia   Due Date: 22 MAR 2026
BEARINGS CONTACT INFORMATION:   RECEIVED IN GOOD ORDER AND CONDITION
POWER TRANSMISSION   Aecount Receivable Team
Emait: arfinance@motionasiapac.com
AUTHORISED SIGNATURE   SIGNATURE & COMPANY CHOP
Page 1 of 1
Faktur Pajak
Nama: CBC INDONESIA   Alamat: GEDUNG SECURE BUILDING JL
PROTOKOL HALIM PERDANAKUSUMA C . KOTA   ADM. JAKARTA TIMUR #0211006879004000000000
Kode dan Nomor Seri Faktur Pajak: 04002600060399891
Pengusaha Kena Pajak:
Nama : CBC INDONESIA   Alamat : GEDUNG SECURE BUILDING JL PROTOKOL HALIM PERDANAKUSUMA C, RT O00, RW 000, HALIM
PERDANA KUSUMA, MAKASAR, KOTA ADM. JAKARTA TIMUR, DKI JAKARTA 13610   NPWP : 0211006879004000
Pembeli Barang Kena Pajak/Penerima Jasa Kena Pajak:
Nama : CAKRAWALA BUANA LESTARI   Alamat : JL PAPANGGO II C NO.27, RT 008, RW 003, PAPANGGO, TANJUNG PRIOK, KOTA ADM. JAKARTA
NPWP: 0630234862042000   UTARA, DKI JAKARTA 14340 #0630234862042000000000
Nomor Paspor : -   NIK: -
Email: cvcakrawala.market@gmail.com   Identitas Lain : -
No.   Barang/   Kode   Nama Barang Kena Pajak / Jasa Kena Pajak   Harga Jual / Penggantian /   Uang Muka / Termin
Jasa   (Rp)
WHX126TP - 103.630MM PITCH   WHX126TP - WELDEDSTEEL CRANKED LINK CHAIN
000000   Rp 1.300.000,00 × 360,00 Piece   Potongan Harga = Ro 0.00   468.000.000,00
"""


def test_cbc_indonesia_clustered_tax_invoice_extracts_clean_item():
    items = extract_line_items_from_text(raw_text=CBC_CLUSTERED)
    assert len(items) == 1, [f"{i.description} ({i.amount})" for i in items]
    assert "WHX126TP" in items[0].description
    assert "WELDEDSTEEL CRANKED LINK CHAIN" in items[0].description
    assert items[0].quantity == Decimal("360")
    assert items[0].unit.lower() == "each"
    assert items[0].unit_price == Decimal("1300000.00")
    assert items[0].amount == Decimal("468000000.00")


def test_cbc_indonesia_totals_and_vat_extraction():
    from src.services.documents.normalization import extract_document_monetary_totals

    totals = extract_document_monetary_totals(CBC_CLUSTERED)
    assert totals["total_amount"] == Decimal("519480000.00")
    assert totals["subtotal"] == Decimal("468000000.00")
    assert totals["vat_amount"] == Decimal("51480000.00")


def test_faktur_pajak_serial_is_not_parsed_as_vat_amount():
    from src.services.documents.normalization import extract_document_monetary_totals

    text = "Kode dan Nomor Seri Faktur Pajak: 04002600060399891\nTotal Rp 100.000"
    totals = extract_document_monetary_totals(text)
    assert totals["vat_amount"] != Decimal("04002600060399891")
    assert totals["vat_amount"] is None



