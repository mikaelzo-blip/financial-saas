import pytest
from decimal import Decimal
from pathlib import Path
from reportlab.pdfgen import canvas

from src.models.enums import DocumentType
from src.services.documents.local_provider import LocalExtractionProvider
from src.services.documents.normalization import (
    extract_document_monetary_totals,
    parse_candidate_money,
)
def format_idr(val: Decimal) -> str:
    return f"Rp {int(val):,}".replace(",", ".")


def test_representative_extracted_text_grand_total():
    """UAT Defect 1 Regression:
    Ex Tax IDR 183,733,600.00
    VAT IDR 20,210,696.00
    TOTAL IDR 203,944,296.00

    Must distinguish:
    subtotal == 183733600
    vat_amount == 20210696
    total_amount == 203944296
    """
    text = """
    QUOTATION / PROFORMA INVOICE
    PT SUPPLIER MATERIAL INDONESIA
    No: QUO/2026/09/0014
    Date: 12 September 2026

    Deskripsi: Pengadaan Baja Ringan & Hollow
    Ex Tax IDR 183,733,600.00
    VAT IDR 20,210,696.00
    TOTAL IDR 203,944,296.00
    """
    totals = extract_document_monetary_totals(text)
    assert totals["subtotal"] == Decimal("183733600")
    assert totals["vat_amount"] == Decimal("20210696")
    assert totals["total_amount"] == Decimal("203944296")


def test_priority_order_grand_total_over_subtotal():
    """Semantic priority:
    1. GRAND TOTAL
    2. TOTAL AMOUNT / TOTAL
    3. AMOUNT DUE / TOTAL DUE
    4. NET PAYABLE
    5. subtotal only as fallback when no final total exists

    Do NOT choose Ex Tax / Subtotal / DPP when a final TOTAL is present.
    """
    # Case with DPP, PPN, and Grand Total
    text = """
    FAKTUR PENJUALAN
    Subtotal: Rp 183.733.600
    DPP: Rp 183.733.600
    PPN 11%: Rp 20.210.696
    Grand Total: Rp 203.944.296
    """
    totals = extract_document_monetary_totals(text)
    assert totals["subtotal"] == Decimal("183733600")
    assert totals["vat_amount"] == Decimal("20210696")
    assert totals["total_amount"] == Decimal("203944296")


def test_fallback_to_subtotal_only_when_no_final_total():
    text = """
    PENAWARAN HARGA
    Subtotal: Rp 50.000.000
    """
    totals = extract_document_monetary_totals(text)
    assert totals["subtotal"] == Decimal("50000000")
    assert totals["total_amount"] == Decimal("50000000")


@pytest.mark.asyncio
async def test_local_provider_uat_quotation_pdf(tmp_path):
    """Verify LocalExtractionProvider processes representative PDF with Ex Tax, VAT, TOTAL."""
    pdf_path = tmp_path / "quotation_uat.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(50, 200, "QUOTATION / PROFORMA INVOICE")
    c.drawString(50, 180, "No: QUO/2026/09/0014")
    c.drawString(50, 160, "Date: 12-Sep-2026")
    c.drawString(50, 140, "Ex Tax IDR 183,733,600.00")
    c.drawString(50, 120, "VAT IDR 20,210,696.00")
    c.drawString(50, 100, "TOTAL IDR 203,944,296.00")
    c.save()

    provider = LocalExtractionProvider()
    result = await provider.extract(pdf_path, "application/pdf")

    assert result.data.subtotal == Decimal("183733600")
    assert result.data.vat_amount == Decimal("20210696")
    assert result.data.total_amount == Decimal("203944296")
    assert result.data.total_amount == 203944296
    assert result.data.subtotal == 183733600
    assert result.document_type in (DocumentType.QUOTATION, DocumentType.VENDOR_INVOICE)


@pytest.mark.parametrize(
    "label",
    [
        "Sub Total",
        "Sub-Total",
        "Subtotal",
        "Ex Tax",
        "Ex-Tax",
        "ExTax",
        "Total Ex Tax",
        "Total Ex-Tax",
    ],
)
def test_edge_case_1_subtotal_and_ex_tax_variations(label: str):
    """Edge Case 1: Sub-Total, Ex-Tax, Total Ex-Tax and variations.

    Invariant: subtotal / ex-tax must NEVER outrank a final payable TOTAL / GRAND TOTAL.
    """
    # 1. With final TOTAL line: subtotal must not outrank final total
    doc_with_total = f"""
    FAKTUR PEMBELIAN
    {label}: Rp 183.733.600
    PPN 11%: Rp 20.210.696
    TOTAL: Rp 203.944.296
    """
    res1 = extract_document_monetary_totals(doc_with_total)
    assert res1["subtotal"] == Decimal("183733600"), f"Failed to extract subtotal for label '{label}'"
    assert res1["vat_amount"] == Decimal("20210696")
    assert res1["total_amount"] == Decimal("203944296"), f"Subtotal outranked final TOTAL for label '{label}'"

    # 2. With GRAND TOTAL line
    doc_with_grand_total = f"""
    FAKTUR PEMBELIAN
    {label}: Rp 183.733.600
    PPN 11%: Rp 20.210.696
    GRAND TOTAL: Rp 203.944.296
    """
    res2 = extract_document_monetary_totals(doc_with_grand_total)
    assert res2["subtotal"] == Decimal("183733600")
    assert res2["total_amount"] == Decimal("203944296")

    # 3. Fallback when no final total exists
    doc_fallback = f"""
    PENAWARAN
    {label}: Rp 50.000.000
    """
    res3 = extract_document_monetary_totals(doc_fallback)
    assert res3["subtotal"] == Decimal("50000000")
    assert res3["total_amount"] == Decimal("50000000")


@pytest.mark.parametrize(
    "vat_label,expected_vat",
    [
        ("PPN 11%", Decimal("20210696")),
        ("PPN (11%)", Decimal("20210696")),
        ("PPN 12%", Decimal("22048032")),
        ("PPN (12%)", Decimal("22048032")),
        ("VAT 11%", Decimal("20210696")),
        ("VAT (11%)", Decimal("20210696")),
        ("VAT 12%", Decimal("22048032")),
        ("VAT (12%)", Decimal("22048032")),
    ],
)
def test_edge_case_2_vat_and_ppn_rate_variations(vat_label: str, expected_vat: Decimal):
    """Edge Case 2: Parenthesized VAT / PPN rates.

    Support:
    PPN 11%, PPN (11%), PPN 12%, PPN (12%)
    VAT 11%, VAT (11%), VAT 12%, VAT (12%)
    """
    # Test with currency prefix
    doc_with_curr = f"""
    INVOICE
    Subtotal: Rp 183.733.600
    {vat_label}: Rp {expected_vat:,}
    TOTAL: Rp 203.944.296
    """.replace(",", ".")
    res_curr = extract_document_monetary_totals(doc_with_curr)
    assert res_curr["vat_amount"] == expected_vat, f"Failed with currency for '{vat_label}'"
    assert res_curr["subtotal"] == Decimal("183733600")
    assert res_curr["total_amount"] == Decimal("203944296")

    # Test without currency prefix (raw number)
    doc_raw = f"""
    INVOICE
    Subtotal: 183.733.600
    {vat_label}: {expected_vat:,}
    TOTAL: 203.944.296
    """.replace(",", ".")
    res_raw = extract_document_monetary_totals(doc_raw)
    assert res_raw["vat_amount"] == expected_vat, f"Failed without currency for '{vat_label}'"


def test_combined_edge_cases_subtotal_and_parenthesized_vat():
    """Verify combination of hyphenated subtotal / ex-tax and parenthesized VAT.

    Preserves UAT invariants:
    subtotal = 183733600
    vat_amount = 20210696
    total_amount = 203944296
    """
    doc1 = """
    PT BANGUNAN NUSANTARA
    FAKTUR PENJUALAN
    Sub-Total: Rp 183.733.600
    PPN (11%): Rp 20.210.696
    TOTAL: Rp 203.944.296
    """
    res1 = extract_document_monetary_totals(doc1)
    assert res1["subtotal"] == Decimal("183733600")
    assert res1["vat_amount"] == Decimal("20210696")
    assert res1["total_amount"] == Decimal("203944296")

    doc2 = """
    PT BANGUNAN NUSANTARA
    QUOTATION / PROFORMA INVOICE
    Total Ex-Tax IDR 183,733,600.00
    VAT (11%) IDR 20,210,696.00
    GRAND TOTAL IDR 203,944,296.00
    """
    res2 = extract_document_monetary_totals(doc2)
    assert res2["subtotal"] == Decimal("183733600")
    assert res2["vat_amount"] == Decimal("20210696.00")
    assert res2["total_amount"] == Decimal("203944296.00")
