"""Generate safe, representative synthetic benchmark documents for OCR evaluation.
Covers 12 documents spanning all financial contractor document types.
"""
from pathlib import Path
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

DOCS_DIR = Path(__file__).parent / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def generate_case_a():
    """CASE A — 3-line invoice with multiline size continuation."""
    img = Image.new("RGB", (1000, 750), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Draw header
    draw.text((50, 40), "FAKTUR PENJUALAN", fill=(0, 0, 0))
    draw.text((50, 70), "PT BERKAT ANUGERAH TEKNIK", fill=(0, 0, 0))
    draw.text((50, 100), "No: INV/2026/09/0045", fill=(0, 0, 0))
    draw.text((50, 130), "Tanggal: 15 September 2026", fill=(0, 0, 0))
    draw.text((50, 160), "Kepada: PT KARYA UTAMA", fill=(0, 0, 0))

    # Draw table items
    draw.text((50, 210), "1. COVER / REPAIR STRIP", fill=(0, 0, 0))
    draw.text((50, 240), "SIZE : 100 MM X 10.000 MM", fill=(0, 0, 0))
    draw.text((50, 270), "1 ROLL 3.100.000 3.100.000", fill=(0, 0, 0))

    draw.text((50, 320), "2. COVER / REPAIR STRIP", fill=(0, 0, 0))
    draw.text((50, 350), "SIZE : 220 MM X 10.000 MM", fill=(0, 0, 0))
    draw.text((50, 380), "1 ROLL 6.300.000 6.300.000", fill=(0, 0, 0))

    draw.text((50, 430), "3. LEM SC 2000 + HARDENER UTR", fill=(0, 0, 0))
    draw.text((50, 460), "10 SET 620.000 6.200.000", fill=(0, 0, 0))

    # Totals
    draw.text((50, 520), "TOTAL: 15.600.000", fill=(0, 0, 0))

    out_png = DOCS_DIR / "01_case_a_3line_invoice.png"
    img.save(str(out_png), "PNG")

    # Also save as PDF
    out_pdf = DOCS_DIR / "01_case_a_3line_invoice.pdf"
    img.save(str(out_pdf), "PDF")
    print(f"Generated Case A: {out_png}")


def generate_case_b():
    """CASE B — Quotation/proforma with Ex Tax, VAT, and Total."""
    pdf_path = DOCS_DIR / "02_case_b_quotation_proforma.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 720, "QUOTATION / PROFORMA INVOICE")
    c.setFont("Helvetica", 11)
    c.drawString(50, 690, "PT SUPPLIER MATERIAL INDONESIA")
    c.drawString(50, 670, "No: QUO/2026/09/0014")
    c.drawString(50, 650, "Date: 12 September 2026")
    c.drawString(50, 630, "Kepada: PT MEKAR ABADI KONSTRUKSI")
    c.drawString(50, 590, "Deskripsi: Pengadaan Baja Ringan & Hollow Proyek Sentul")
    c.drawString(50, 540, "Ex Tax IDR 183,733,600.00")
    c.drawString(50, 510, "VAT IDR 20,210,696.00")
    c.drawString(50, 480, "TOTAL IDR 203,944,296.00")
    c.save()

    # Also generate a raster PNG version
    img = Image.new("RGB", (900, 650), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 40), "QUOTATION / PROFORMA INVOICE", fill=(0, 0, 0))
    draw.text((50, 70), "PT SUPPLIER MATERIAL INDONESIA", fill=(0, 0, 0))
    draw.text((50, 100), "No: QUO/2026/09/0014", fill=(0, 0, 0))
    draw.text((50, 130), "Date: 12 September 2026", fill=(0, 0, 0))
    draw.text((50, 160), "Kepada: PT MEKAR ABADI KONSTRUKSI", fill=(0, 0, 0))
    draw.text((50, 200), "Deskripsi: Pengadaan Baja Ringan & Hollow Proyek Sentul", fill=(0, 0, 0))
    draw.text((50, 260), "Ex Tax IDR 183,733,600.00", fill=(0, 0, 0))
    draw.text((50, 290), "VAT IDR 20,210,696.00", fill=(0, 0, 0))
    draw.text((50, 320), "TOTAL IDR 203,944,296.00", fill=(0, 0, 0))
    out_png = DOCS_DIR / "02_case_b_quotation_proforma.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Case B: {pdf_path} and {out_png}")


def generate_doc_03():
    """Doc 03: Digital PDF Tax Invoice with 2 construction items."""
    pdf_path = DOCS_DIR / "03_digital_tax_invoice.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 730, "PT MITRA BANGUN PERSADA")
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "TAX INVOICE INV-2026-8891")
    c.drawString(50, 690, "Tanggal: 13 September 2026")
    c.drawString(50, 670, "Jatuh Tempo: 30 September 2026")
    c.drawString(50, 650, "Kepada: PT NUSANTARA KONSTRUKSI")
    c.drawString(50, 610, "Semen Padang 50kg   20   sak   Rp 65.000   Rp 1.300.000")
    c.drawString(50, 580, "Besi Beton D10   50   btg   Rp 80.000   Rp 4.000.000")
    c.drawString(50, 530, "Subtotal: Rp 5.300.000")
    c.drawString(50, 500, "PPN 11%: Rp 583.000")
    c.drawString(50, 470, "Total Bayar: Rp 5.883.000")
    c.save()
    print(f"Generated Doc 03: {pdf_path}")


def generate_doc_04():
    """Doc 04: Scanned purchase invoice image (no digital text stream)."""
    img = Image.new("RGB", (900, 650), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "FAKTUR PEMBELIAN PT JAYA ABADI", fill=(20, 20, 20))
    draw.text((40, 70), "No: INV-2026-099", fill=(20, 20, 20))
    draw.text((40, 100), "Tanggal: 15/09/2026", fill=(20, 20, 20))
    draw.text((40, 130), "Kepada: PT ADHI JAYA", fill=(20, 20, 20))
    draw.text((40, 180), "Pasir Cor   10   m3   Rp 350.000   Rp 3.500.000", fill=(20, 20, 20))
    draw.text((40, 240), "Subtotal: Rp 3.500.000", fill=(20, 20, 20))
    draw.text((40, 270), "PPN: Rp 350.000", fill=(20, 20, 20))
    draw.text((40, 300), "Total: Rp 3.850.000", fill=(20, 20, 20))
    out_png = DOCS_DIR / "04_scanned_purchase_invoice.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Doc 04: {out_png}")


def generate_doc_05():
    """Doc 05: Mobile banking transfer proof (Bank BCA)."""
    img = Image.new("RGB", (650, 450), color=(245, 248, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 30), "BUKTI TRANSFER BANK BCA", fill=(0, 50, 150))
    draw.text((40, 70), "Status: Transaksi Berhasil", fill=(0, 150, 0))
    draw.text((40, 110), "Tanggal: 13-09-2026", fill=(0, 0, 0))
    draw.text((40, 140), "No Referensi: 2026091399881", fill=(0, 0, 0))
    draw.text((40, 170), "Rekening Tujuan: 8820192831", fill=(0, 0, 0))
    draw.text((40, 200), "Nama Penerima: PT ADHI JAYA", fill=(0, 0, 0))
    draw.text((40, 240), "Jumlah Transfer: Rp 25.000.000", fill=(0, 0, 0))
    draw.text((40, 270), "Berita: Pembayaran DP Baja Ringan", fill=(0, 0, 0))
    out_png = DOCS_DIR / "05_bca_transfer_screenshot.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Doc 05: {out_png}")


def generate_doc_06():
    """Doc 06: Receipt / Nota rotated 90 degrees."""
    img = Image.new("RGB", (700, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "STRUK PEMBELIAN TOKO CAT MAJU", fill=(0, 0, 0))
    draw.text((40, 80), "Tanggal: 25/08/2026", fill=(0, 0, 0))
    draw.text((40, 120), "Cat Tembok 5kg   2   pail   Rp 225.000   Rp 450.000", fill=(0, 0, 0))
    draw.text((40, 170), "Total: Rp 450.000", fill=(0, 0, 0))
    rotated = img.rotate(90, expand=True)
    out_png = DOCS_DIR / "06_rotated_receipt_nota.png"
    rotated.save(str(out_png), "PNG")
    print(f"Generated Doc 06: {out_png}")


def generate_doc_07():
    """Doc 07: Multi-page digital PDF invoice (2 pages)."""
    pdf_path = DOCS_DIR / "07_multipage_invoice.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    # Page 1
    c.drawString(50, 730, "PT MULTIPAGE JAYA")
    c.drawString(50, 700, "INVOICE INV-MP-001 PAGE 1")
    c.drawString(50, 670, "Tanggal: 13 September 2026")
    c.drawString(50, 640, "Kepada: PT PRIMA CIPTA")
    c.drawString(50, 600, "Semen 10 sak Rp 60.000 Rp 600.000")
    c.showPage()
    # Page 2
    c.drawString(50, 730, "CATATAN PEMBAYARAN PAGE 2")
    c.drawString(50, 700, "Jatuh Tempo: 28 September 2026")
    c.drawString(50, 670, "Bank Mandiri Rek: 123-00-9876543-1 a.n PT MULTIPAGE JAYA")
    c.drawString(50, 630, "Total: Rp 600.000")
    c.save()
    print(f"Generated Doc 07: {pdf_path}")


def generate_doc_08():
    """Doc 08: Purchase Order (PO)."""
    pdf_path = DOCS_DIR / "08_purchase_order.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 730, "PURCHASE ORDER")
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "PT MEGAH KONSTRUKSI NUSANTARA")
    c.drawString(50, 690, "PO Number: PO-2026-0042")
    c.drawString(50, 670, "Tanggal: 10 September 2026")
    c.drawString(50, 650, "Supplier: CV SEMEN MEGAH")
    c.drawString(50, 610, "1. Semen Holcim 50kg   100   sak   Rp 68.000   Rp 6.800.000")
    c.drawString(50, 580, "2. Split 2/3   15   m3   Rp 280.000   Rp 4.200.000")
    c.drawString(50, 550, "3. Pasir Pasang   8   rit   Rp 1.250.000   Rp 10.000.000")
    c.drawString(50, 500, "Subtotal: Rp 21.000.000")
    c.drawString(50, 470, "PPN 11%: Rp 2.310.000")
    c.drawString(50, 440, "Grand Total: Rp 23.310.000")
    c.save()
    print(f"Generated Doc 08: {pdf_path}")


def generate_doc_09():
    """Doc 09: SPK / Contract-style document."""
    pdf_path = DOCS_DIR / "09_spk_contract.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 730, "SURAT PERINTAH KERJA (SPK)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 710, "Nomor: SPK-2026-018")
    c.drawString(50, 690, "Tanggal: 01 September 2026")
    c.drawString(50, 670, "Project Reference: PRJ-JKT-042")
    c.drawString(50, 650, "Pemberi Tugas: PT BANGUN JAYA PERKASA")
    c.drawString(50, 630, "Pelaksana: CV CIPTA MANDIRI")
    c.drawString(50, 590, "Pekerjaan: Struktur Kolom Lantai 2 Proyek Menara Hijau")
    c.drawString(50, 550, "Nilai Kontrak: Rp 85.000.000")
    c.drawString(50, 520, "Total: Rp 85.000.000")
    c.save()
    print(f"Generated Doc 09: {pdf_path}")


def generate_doc_10():
    """Doc 10: Multi-line table invoice (6 line items)."""
    img = Image.new("RGB", (1050, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "FAKTUR PENJUALAN MATERIAL", fill=(0, 0, 0))
    draw.text((40, 70), "PT SUMBER REJEKI BESI", fill=(0, 0, 0))
    draw.text((40, 100), "No Invoice: INV/SRB/2026/088", fill=(0, 0, 0))
    draw.text((40, 130), "Tanggal: 16 September 2026", fill=(0, 0, 0))
    draw.text((40, 160), "Kepada: PT NUSANTARA BANGUN", fill=(0, 0, 0))

    # 6 lines
    draw.text((40, 210), "1. Besi Ulir D16   40   btg   Rp 145.000   Rp 5.800.000", fill=(0, 0, 0))
    draw.text((40, 250), "2. Wiremesh M8   15   lbr   Rp 420.000   Rp 6.300.000", fill=(0, 0, 0))
    draw.text((40, 290), "3. Semen Tiga Roda   50   sak   Rp 66.000   Rp 3.300.000", fill=(0, 0, 0))
    draw.text((40, 330), "4. Kawat Bendrat   5   roll   Rp 125.000   Rp 625.000", fill=(0, 0, 0))
    draw.text((40, 370), "5. Bata Ringan Hebel   10   m3   Rp 650.000   Rp 6.500.000", fill=(0, 0, 0))
    draw.text((40, 410), "6. Cat Weathercoat   4   pail   Rp 1.850.000   Rp 7.400.000", fill=(0, 0, 0))

    draw.text((40, 480), "Subtotal: Rp 29.925.000", fill=(0, 0, 0))
    draw.text((40, 510), "PPN 11%: Rp 3.291.750", fill=(0, 0, 0))
    draw.text((40, 540), "Total Bayar: Rp 33.216.750", fill=(0, 0, 0))

    out_png = DOCS_DIR / "10_multiline_table_invoice.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Doc 10: {out_png}")


def generate_doc_11():
    """Doc 11: Cash receipt / nota (Toko Bangunan Sahabat)."""
    img = Image.new("RGB", (700, 450), color=(253, 253, 250))
    draw = ImageDraw.Draw(img)
    draw.text((40, 30), "NOTA KONTAN TOKO BANGUNAN SAHABAT", fill=(10, 10, 10))
    draw.text((40, 60), "No: NT-2026-041", fill=(10, 10, 10))
    draw.text((40, 90), "Tanggal: 14 September 2026", fill=(10, 10, 10))
    draw.text((40, 140), "Paku Kayu 5cm & 7cm   5   kg   Rp 22.000   Rp 110.000", fill=(10, 10, 10))
    draw.text((40, 180), "Kuas Cat 3 inch   4   bh   Rp 15.000   Rp 60.000", fill=(10, 10, 10))
    draw.text((40, 220), "Thinner A Special   2   btl   Rp 35.000   Rp 70.000", fill=(10, 10, 10))
    draw.text((40, 280), "Total: Rp 240.000", fill=(10, 10, 10))
    out_png = DOCS_DIR / "11_cash_receipt_nota.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Doc 11: {out_png}")


def generate_doc_12():
    """Doc 12: Scanned deposit / transfer receipt (Bank Mandiri)."""
    img = Image.new("RGB", (700, 450), color=(240, 245, 250))
    draw = ImageDraw.Draw(img)
    draw.text((40, 30), "BUKTI SETORAN TUNAI BANK MANDIRI", fill=(0, 40, 120))
    draw.text((40, 70), "No Transaksi: TRX-MDR-889021", fill=(0, 0, 0))
    draw.text((40, 100), "Tanggal: 15-09-2026", fill=(0, 0, 0))
    draw.text((40, 130), "Rekening Tujuan: 1240008899123", fill=(0, 0, 0))
    draw.text((40, 160), "Nama Penerima: PT GRAHA SARANA", fill=(0, 0, 0))
    draw.text((40, 200), "Jumlah Setoran: Rp 12.500.000", fill=(0, 0, 0))
    draw.text((40, 230), "Total: Rp 12.500.000", fill=(0, 0, 0))
    out_png = DOCS_DIR / "12_scanned_deposit_receipt.png"
    img.save(str(out_png), "PNG")
    print(f"Generated Doc 12: {out_png}")


if __name__ == "__main__":
    generate_case_a()
    generate_case_b()
    generate_doc_03()
    generate_doc_04()
    generate_doc_05()
    generate_doc_06()
    generate_doc_07()
    generate_doc_08()
    generate_doc_09()
    generate_doc_10()
    generate_doc_11()
    generate_doc_12()
    print("All 12 benchmark documents generated successfully.")
