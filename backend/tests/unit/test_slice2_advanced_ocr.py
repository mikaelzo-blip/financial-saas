"""Product Slice 2 — Advanced OCR Pipeline Test Suite.

Comprehensive synthetic verification covering:
1. Digital PDF invoice (native fast path, text quality pass)
2. Scanned PDF invoice (rasterization + RapidOCR fallback)
3. Mixed PDF (page-by-page fallback: native on page 1, OCR on page 2)
4. Rotated image (orientation handling: 90/180/270 degrees)
5. Transfer screenshot (mobile/banking receipt, counterparty & reference extraction)
6. Multipage PDF (deterministic ordering and page provenance)
7. Basic line-item table (construction units, quantity, unit price, tax, line total)
8. Low quality / blank document (does not fabricate confident values)
9. Performance timing (native digital path remains sub-second fast)
10. DOCUMENT_PROCESS worker queue integration (durable state machine verification)
"""
import io
import time
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from PIL import Image, ImageDraw
import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.enums import DocumentProcessingStatus, DocumentType, ReviewFlag
from src.models.organization import Organization
from src.models.background_job import BackgroundJob
from src.services.document_service import DocumentService
from src.services.documents.classification import classify_text
from src.services.documents.exceptions import InvalidFileError
from src.services.documents.local_provider import LocalExtractionProvider
from src.services.documents.normalization import parse_candidate_date, parse_candidate_money
from src.services.documents.quality_gate import evaluate_page_text_quality
from src.services.documents.table_extractor import extract_line_items_from_text, parse_line_item_text
from src.services.job_queue_service import JobQueueService
from src.worker import handle_document_process


# ---------------------------------------------------------------------------
# Synthetic Fixture Generators (No sensitive business documents)
# ---------------------------------------------------------------------------

def create_synthetic_digital_pdf(file_path: Path) -> Path:
    """Creates a clean digital PDF with embedded text streams."""
    c = canvas.Canvas(str(file_path))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 780, "PT MITRA BANGUN PERSADA")
    c.setFont("Helvetica", 10)
    c.drawString(50, 760, "TAX INVOICE INV-2026-8891")
    c.drawString(50, 745, "Tanggal: 13 September 2026")
    c.drawString(50, 730, "Jatuh Tempo: 30 September 2026")
    c.drawString(50, 715, "Kepada: PT NUSANTARA KONSTRUKSI")
    c.drawString(50, 680, "Semen Padang 50kg   20   sak   Rp 65.000   Rp 1.300.000")
    c.drawString(50, 660, "Besi Beton D10   50   btg   Rp 80.000   Rp 4.000.000")
    c.drawString(50, 620, "Subtotal: Rp 5.300.000")
    c.drawString(50, 600, "PPN 11%: Rp 583.000")
    c.drawString(50, 580, "Total Bayar: Rp 5.883.000")
    c.save()
    return file_path


def create_synthetic_scanned_pdf(file_path: Path) -> Path:
    """Creates a scanned PDF consisting purely of a raster image with NO text stream."""
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "FAKTUR PEMBELIAN PT JAYA ABADI", fill=(0, 0, 0))
    draw.text((40, 70), "No: INV-2026-099", fill=(0, 0, 0))
    draw.text((40, 100), "Tanggal: 15/09/2026", fill=(0, 0, 0))
    draw.text((40, 130), "Pasir Cor   10   m3   Rp 350.000   Rp 3.500.000", fill=(0, 0, 0))
    draw.text((40, 160), "Subtotal: Rp 3.500.000", fill=(0, 0, 0))
    draw.text((40, 190), "PPN: Rp 350.000", fill=(0, 0, 0))
    draw.text((40, 220), "Total: Rp 3.850.000", fill=(0, 0, 0))
    img.save(str(file_path), "PDF")
    return file_path


def create_synthetic_rotated_image(file_path: Path, angle: int = 90) -> Path:
    """Creates an image with text rotated 90, 180, or 270 degrees."""
    img = Image.new("RGB", (600, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 40), "STRUK PEMBELIAN TOKO CAT MAJU", fill=(0, 0, 0))
    draw.text((30, 80), "Tanggal: 25/08/2026", fill=(0, 0, 0))
    draw.text((30, 120), "Total: Rp 450.000", fill=(0, 0, 0))
    rotated = img.rotate(angle, expand=True)
    rotated.save(str(file_path), "PNG")
    return file_path


def create_synthetic_transfer_screenshot(file_path: Path) -> Path:
    """Creates a synthetic mobile banking transfer proof image."""
    img = Image.new("RGB", (600, 400), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.text((40, 30), "BUKTI TRANSFER BANK BCA", fill=(0, 50, 150))
    draw.text((40, 70), "Status: Transaksi Berhasil", fill=(0, 150, 0))
    draw.text((40, 110), "Tanggal: 13-09-2026", fill=(0, 0, 0))
    draw.text((40, 140), "No Referensi: 2026091399881", fill=(0, 0, 0))
    draw.text((40, 170), "Rekening Tujuan: 8820192831", fill=(0, 0, 0))
    draw.text((40, 200), "Nama Penerima: PT ADHI JAYA", fill=(0, 0, 0))
    draw.text((40, 240), "Jumlah Transfer: Rp 25.000.000", fill=(0, 0, 0))
    img.save(str(file_path), "PNG")
    return file_path


def create_synthetic_multipage_pdf(file_path: Path) -> Path:
    """Creates a 2-page digital PDF to test deterministic page ordering and provenance."""
    c = canvas.Canvas(str(file_path))
    # Page 1
    c.drawString(50, 750, "PT MULTIPAGE JAYA")
    c.drawString(50, 720, "INVOICE INV-MP-001 PAGE 1")
    c.drawString(50, 690, "Tanggal: 13 September 2026")
    c.drawString(50, 660, "Semen 10 sak Rp 60.000 Rp 600.000")
    c.showPage()
    # Page 2
    c.drawString(50, 750, "CATATAN PEMBAYARAN PAGE 2")
    c.drawString(50, 720, "Jatuh Tempo: 28 September 2026")
    c.drawString(50, 690, "Total: Rp 600.000")
    c.save()
    return file_path


def create_synthetic_mixed_pdf(file_path: Path) -> Path:
    """Creates a 2-page PDF: Page 1 has native text, Page 2 is a scanned image page."""
    c = canvas.Canvas(str(file_path))
    # Page 1: native text
    c.drawString(50, 750, "PT HYBRID NATIVE PAGE 1")
    c.drawString(50, 720, "INVOICE INV-HYBRID-002")
    c.drawString(50, 690, "Tanggal: 13 September 2026")
    c.showPage()

    # Page 2: rasterized image page drawn into canvas
    img = Image.new("RGB", (500, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 40), "SCANNED ATTACHMENT PAGE 2", fill=(0, 0, 0))
    draw.text((30, 80), "Total Bayar: Rp 1.500.000", fill=(0, 0, 0))
    
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)
    
    # Save temporary image for reportlab drawImage
    temp_img_path = file_path.parent / "temp_hybrid_p2.png"
    img.save(str(temp_img_path), "PNG")
    c.drawImage(str(temp_img_path), 50, 400, width=400, height=240)
    c.save()
    if temp_img_path.exists():
        temp_img_path.unlink()
    return file_path


# ---------------------------------------------------------------------------
# Unit & Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_quality_gate_distinguishes_native_and_poor_text():
    """Verify text quality gate checks character count, tokens, and control characters."""
    # Sufficient digital page
    rich_text = "PT MITRA BANGUN PERSADA\nTAX INVOICE INV-2026-8891\nTotal Rp 5.883.000"
    q_rich = evaluate_page_text_quality(rich_text)
    assert q_rich.is_sufficient is True
    assert q_rich.char_count > 35
    assert q_rich.meaningful_token_count >= 5

    # Poor / Scanned page extracting 0 or minimal text
    q_empty = evaluate_page_text_quality("")
    assert q_empty.is_sufficient is False

    q_minimal = evaluate_page_text_quality("Page 1")
    assert q_minimal.is_sufficient is False
    assert "Character count too low" in q_minimal.reason

    # Corrupt / abnormal control characters
    corrupt_text = "PT TEST \x00\x01\x02\x03\x04\x05\x06\x07 GARBAGE FONT"
    q_corrupt = evaluate_page_text_quality(corrupt_text)
    assert q_corrupt.is_sufficient is False


@pytest.mark.asyncio
async def test_digital_pdf_uses_fast_native_path(tmp_path):
    """Verify that digital PDFs pass text quality gate and use fast native extraction."""
    pdf_path = create_synthetic_digital_pdf(tmp_path / "digital_invoice.pdf")

    provider = LocalExtractionProvider()
    start_t = time.monotonic()
    result = await provider.extract(pdf_path, "application/pdf")
    latency = time.monotonic() - start_t

    # Native path should be fast (well under 1 second)
    assert latency < 1.0, f"Digital PDF native path took too long: {latency:.2f}s"

    assert result.document_type == DocumentType.VENDOR_INVOICE
    assert result.data.invoice_number == "INV-2026-8891"
    assert result.data.total_amount == Decimal("5883000")
    assert result.data.subtotal == Decimal("5300000")
    assert result.data.vat_amount == Decimal("583000")
    assert result.data.transaction_date == date(2026, 9, 13)
    assert result.data.due_date == date(2026, 9, 30)
    assert result.confidence.ocr_confidence >= Decimal("0.90")

    # Verify provenance
    assert result.raw_payload["extraction_mode"] == "native"
    assert result.raw_payload["page_count"] == 1
    assert result.raw_payload["pages"][0]["source"] == "native"

    # Verify line items extracted
    assert len(result.data.line_items) == 2
    assert result.data.line_items[0].quantity == Decimal("20")
    assert result.data.line_items[0].unit == "sak"
    assert result.data.line_items[0].line_total == Decimal("1300000")
    assert result.data.line_items[1].quantity == Decimal("50")
    assert result.data.line_items[1].unit == "btg"
    assert result.data.line_items[1].line_total == Decimal("4000000")


@pytest.mark.asyncio
async def test_scanned_pdf_uses_rasterization_ocr_fallback(tmp_path):
    """Verify that scanned PDFs with no native text fall back to rasterization + RapidOCR."""
    pdf_path = create_synthetic_scanned_pdf(tmp_path / "scanned_invoice.pdf")

    provider = LocalExtractionProvider()
    result = await provider.extract(pdf_path, "application/pdf")

    # Provenance proves OCR was used on rasterized page
    assert result.raw_payload["extraction_mode"] == "ocr"
    assert result.raw_payload["pages"][0]["source"] == "ocr"

    assert result.document_type in (DocumentType.VENDOR_INVOICE, DocumentType.PURCHASE_ORDER)
    assert result.data.total_amount == Decimal("3850000")
    assert result.data.subtotal == Decimal("3500000")
    assert result.data.vat_amount == Decimal("350000")
    assert result.data.transaction_date == date(2026, 9, 15)

    # Line item from OCR
    assert len(result.data.line_items) >= 1
    assert result.data.line_items[0].line_total == Decimal("3500000")


@pytest.mark.asyncio
async def test_mixed_pdf_page_by_page_fallback(tmp_path):
    """Verify hybrid extraction on mixed PDF (native on page 1, OCR on page 2)."""
    pdf_path = create_synthetic_mixed_pdf(tmp_path / "mixed_doc.pdf")

    provider = LocalExtractionProvider()
    result = await provider.extract(pdf_path, "application/pdf")

    assert result.raw_payload["page_count"] == 2
    assert result.raw_payload["pages"][0]["page_number"] == 1
    assert result.raw_payload["pages"][0]["source"] == "native"
    assert result.raw_payload["pages"][1]["page_number"] == 2
    assert result.raw_payload["pages"][1]["source"] == "ocr"
    assert result.raw_payload["extraction_mode"] == "hybrid"

    # Provenance and combined raw text preserves order
    assert "PAGE 1" in result.raw_payload["pages"][0]["raw_text"]
    assert "PAGE 2" in result.raw_payload["pages"][1]["raw_text"]
    assert result.data.total_amount == Decimal("1500000")


@pytest.mark.asyncio
async def test_rotated_image_orientation_recovery(tmp_path):
    """Verify that images rotated 90 degrees recover readable text and amount."""
    img_path = create_synthetic_rotated_image(tmp_path / "rotated_90.png", angle=90)

    provider = LocalExtractionProvider()
    result = await provider.extract(img_path, "image/png")

    assert result.document_type == DocumentType.RECEIPT
    assert result.data.total_amount == Decimal("450000")
    assert result.data.transaction_date == date(2026, 8, 25)
    assert result.confidence.ocr_confidence > Decimal("0.50")


@pytest.mark.asyncio
async def test_transfer_screenshot_structured_extraction(tmp_path):
    """Verify mobile banking transfer screenshot extraction."""
    img_path = create_synthetic_transfer_screenshot(tmp_path / "bca_transfer.png")

    provider = LocalExtractionProvider()
    result = await provider.extract(img_path, "image/png")

    assert result.document_type == DocumentType.TRANSFER_PROOF
    assert result.data.total_amount == Decimal("25000000")
    assert result.data.transaction_date == date(2026, 9, 13)
    assert result.data.transfer_reference == "2026091399881"
    assert result.data.destination_account_number == "8820192831"
    assert result.data.origin_bank == "BCA"
    assert result.data.destination_bank == "BCA"


@pytest.mark.asyncio
async def test_multipage_pdf_deterministic_ordering_and_provenance(tmp_path):
    """Verify multipage PDF deterministic ordering (page 1 precedes page 2)."""
    pdf_path = create_synthetic_multipage_pdf(tmp_path / "multipage_ordered.pdf")

    provider = LocalExtractionProvider()
    result = await provider.extract(pdf_path, "application/pdf")

    assert result.raw_payload["page_count"] == 2
    assert result.raw_payload["pages"][0]["page_number"] == 1
    assert result.raw_payload["pages"][1]["page_number"] == 2

    raw_text = result.data.raw_text or ""
    pos_p1 = raw_text.find("PAGE 1")
    pos_p2 = raw_text.find("PAGE 2")
    assert pos_p1 != -1 and pos_p2 != -1
    assert pos_p1 < pos_p2, "Page ordering must be deterministic and sequential"


@pytest.mark.asyncio
async def test_low_quality_blank_document_does_not_fabricate(tmp_path):
    """Verify that blank or corrupt documents do not invent confident values."""
    blank_pdf = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(blank_pdf))
    c.showPage()
    c.save()

    provider = LocalExtractionProvider()
    result = await provider.extract(blank_pdf, "application/pdf")

    assert result.document_type == DocumentType.UNKNOWN
    assert result.confidence.document_type_confidence <= Decimal("0.35")
    assert result.data.total_amount is None
    assert result.data.invoice_number is None
    assert result.confidence.amount_confidence == Decimal("0.00")


@pytest.mark.asyncio
async def test_indonesian_date_normalization_variations():
    """Verify common Indonesian date formats."""
    # 13/09/2026
    c1 = parse_candidate_date("13/09/2026")
    assert c1.value == date(2026, 9, 13)
    assert c1.validation_status == "VALID"

    # 13-09-2026
    c2 = parse_candidate_date("13-09-2026")
    assert c2.value == date(2026, 9, 13)
    assert c2.validation_status == "VALID"

    # 13 September 2026
    c3 = parse_candidate_date("13 September 2026")
    assert c3.value == date(2026, 9, 13)
    assert c3.validation_status == "VALID"

    # 13 Sep 2026
    c4 = parse_candidate_date("13 Sep 2026")
    assert c4.value == date(2026, 9, 13)
    assert c4.validation_status == "VALID"

    # Ambiguous date with both day <= 12 and month <= 12 without day context
    c5 = parse_candidate_date("04/05/2026")
    assert c5.value is None
    assert c5.validation_status == "AMBIGUOUS"


@pytest.mark.asyncio
async def test_indonesian_money_normalization_variations():
    """Verify Indonesian currency variations without binary float rounding."""
    m1 = parse_candidate_money("Rp 1.250.000")
    assert m1.value == Decimal("1250000")

    m2 = parse_candidate_money("1.250.000,00")
    assert m2.value == Decimal("1250000.00")

    m3 = parse_candidate_money("1,250,000.00")
    assert m3.value == Decimal("1250000.00")

    m4 = parse_candidate_money("1250000")
    assert m4.value == Decimal("1250000")

    m5 = parse_candidate_money("Rp 1.250.000,-")
    assert m5.value == Decimal("1250000")


@pytest.mark.asyncio
async def test_table_extractor_construction_units_and_math():
    """Verify structured line-item extraction with construction units and calculations."""
    raw_lines = (
        "Semen Gresik 50kg   20   sak   Rp 70.000   Rp 1.400.000\n"
        "Besi Beton 12mm   100   btg   Rp 95.000   Rp 9.500.000\n"
        "Pasir Pasang   4   m3   Rp 300.000   Rp 1.200.000\n"
        "Pekerjaan Cat Dinding   1   ls   Rp 2.500.000   Rp 2.500.000\n"
    )
    items = extract_line_items_from_text(raw_lines)
    assert len(items) == 4
    assert items[0].description == "Semen Gresik 50kg"
    assert items[0].quantity == Decimal("20")
    assert items[0].unit == "sak"
    assert items[0].unit_price == Decimal("70000")
    assert items[0].line_total == Decimal("1400000")

    assert items[1].unit == "btg"
    assert items[2].unit == "m3"
    assert items[3].unit == "ls"


@pytest.mark.asyncio
async def test_document_process_worker_queue_integration(db_session: AsyncSession, tmp_path):
    """Verify DOCUMENT_PROCESS worker job claims queued work, processes OCR, and sets status."""
    from src.worker import build_worker
    from src.services.documents.inbound_adapter import InboundDocumentAdapter, InboundDocumentInput

    org = Organization(slug="org-slice2-test", legal_name="Org Slice 2 Test")
    db_session.add(org)
    await db_session.flush()

    pdf_path = create_synthetic_digital_pdf(tmp_path / "queue_test_invoice.pdf")
    pdf_bytes = pdf_path.read_bytes()

    # Ingest document and enqueue durable job via InboundDocumentAdapter
    adapter = InboundDocumentAdapter(db_session)
    payload = InboundDocumentInput(
        organization_id=org.id,
        file_obj=io.BytesIO(pdf_bytes),
        file_name="invoice_queue.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.UNKNOWN,
        source_channel="WEB",
    )
    doc = await adapter.ingest_and_enqueue(payload)
    await db_session.commit()
    doc_id = doc.id

    assert doc.processing_status == DocumentProcessingStatus.QUEUED

    # Worker executes the queued job
    class TestSessionFactory:
        def __init__(self, s):
            self.s = s
        async def __aenter__(self):
            return self.s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    worker = build_worker()
    worker.session_factory = lambda: TestSessionFactory(db_session)

    processed = await worker.execute_one_job()
    assert processed is True

    await db_session.refresh(doc)
    assert doc.processing_status in (
        DocumentProcessingStatus.READY_FOR_APPROVAL,
        DocumentProcessingStatus.REVIEW_REQUIRED,
    )
    assert doc.extracted_data.get("invoice_number") == "INV-2026-8891"
    assert doc.extracted_data.get("total_amount") == "5883000"
    assert doc.extracted_data.get("currency_code") == "IDR"
    assert doc.raw_extraction.get("extraction_mode") == "native"


@pytest.mark.asyncio
async def test_local_provider_handles_empty_or_whitespace_counterparty_matches(tmp_path: Path):
    """Ensure LocalExtractionProvider does not raise IndexError when counterparty regex matches only whitespace."""
    img_path = tmp_path / "whitespace_counterparty.png"
    img = Image.new("RGB", (300, 100), color="white")
    draw = ImageDraw.Draw(img)
    # Text with keywords but followed only by spaces/newlines
    draw.text((10, 10), "Transfer Berhasil\nPenerima   \nRp 50.000", fill="black")
    img.save(img_path)

    provider = LocalExtractionProvider()
    result = await provider.extract(img_path, "image/png")
    assert result is not None
    assert result.document_type is not None


@pytest.mark.asyncio
async def test_bank_transfer_slip_date_and_amount_disclaimer_resilience(tmp_path: Path):
    """Verify bank transfer and foreign exchange slips extract correct dates and ignore disclaimers."""
    from datetime import date
    from src.services.documents.normalization import parse_candidate_date, parse_candidate_money
    from src.services.documents.table_extractor import extract_line_items_from_text

    # 1. Normalization tests for Indonesian bank slip date variations & typos
    d1 = parse_candidate_date("Tanggal 13 Austus 2026")
    assert d1.validation_status == "VALID"
    assert d1.value == date(2026, 8, 13)

    d2 = parse_candidate_date("TGL:27 AUG 2026")
    assert d2.validation_status == "VALID"
    assert d2.value == date(2026, 8, 27)

    d3 = parse_candidate_date("Trade Date: 13-Aug-26")
    assert d3.validation_status == "VALID"
    assert d3.value == date(2026, 8, 13)

    # 2. Regulatory boilerplate rejection in parse_candidate_money
    m_disclaimer = parse_candidate_money("diatas Rp. 100 juta")
    assert m_disclaimer.validation_status == "INVALID"
    assert m_disclaimer.value is None

    # 3. Table extractor ignores date line items
    raw_text = "Tanggal 13 Austus 2026\nSemen Gresik 20 sak Rp 70.000 Rp 1.400.000"
    items = extract_line_items_from_text(raw_text)
    assert len(items) == 1
    assert items[0].description == "Semen Gresik"

    # 4. Local provider extraction ignores boilerplate and extracts real transaction data
    slip_path = tmp_path / "bank_dki_slip.png"
    img = Image.new("RGB", (700, 400), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Aplikasi Kiriman Uang dan Pemindahbukuan Valas", fill="black")
    draw.text((10, 30), "PT BANK DKI", fill="black")
    draw.text((10, 50), "Ref. Number: 20708003319", fill="black")
    draw.text((10, 70), "Tanggal 13 Austus 2026", fill="black")
    draw.text((10, 90), "Untuk transaksi tunai diatas Rp.100 juta ekuivalen", fill="black")
    draw.text((10, 110), "Jumlah Rupiah / Amount in IDR", fill="black")
    draw.text((10, 130), "48.110.249,26", fill="black")
    img.save(slip_path)

    provider = LocalExtractionProvider()
    result = await provider.extract(slip_path, "image/png")
    assert result.document_type == DocumentType.TRANSFER_PROOF
    assert result.data.document_number == "20708003319"
    assert result.data.transaction_date == date(2026, 8, 13)
    assert result.data.total_amount == Decimal("48110249.26")


