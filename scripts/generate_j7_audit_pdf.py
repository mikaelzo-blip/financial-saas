import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1425')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J7_Reporting_Traceability_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J7_Reporting_Traceability_Audit_Report.pdf')
os.makedirs(os.path.dirname(dogfood_pdf_path), exist_ok=True)

doc = SimpleDocTemplate(
    pdf_path,
    pagesize=letter,
    leftMargin=36,
    rightMargin=36,
    topMargin=36,
    bottomMargin=36
)

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Heading1'],
    fontName='Helvetica-Bold',
    fontSize=15,
    leading=19,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=3
)

subtitle_style = ParagraphStyle(
    'DocSub',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8.5,
    leading=12,
    textColor=colors.HexColor('#475569'),
    spaceAfter=6
)

h1_style = ParagraphStyle(
    'H1',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=11,
    leading=14,
    textColor=colors.HexColor('#1e293b'),
    spaceBefore=8,
    spaceAfter=4
)

body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#334155')
)

table_header_style = ParagraphStyle(
    'TH',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7.5,
    leading=10,
    textColor=colors.HexColor('#ffffff')
)

table_cell_style = ParagraphStyle(
    'TD',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7.5,
    leading=10,
    textColor=colors.HexColor('#1e293b')
)

code_style = ParagraphStyle(
    'CodeStyle',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=7,
    leading=9,
    textColor=colors.HexColor('#0f172a')
)

caption_style = ParagraphStyle(
    'Caption',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=7,
    leading=9,
    textColor=colors.HexColor('#64748b'),
    spaceAfter=6
)

elements = []

# Title & Meta
elements.append(Paragraph("FINANCIAL SAAS — ACTIVE E2E WORKFLOW AUDIT REPORT", title_style))
elements.append(Paragraph("Journey J7: Reporting Traceability (Source ↔ Report ↔ Accounting Engine)", subtitle_style))
elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=8))

meta_data = [
    [Paragraph("<b>Audit Run ID:</b>", table_cell_style), Paragraph("E2E-TEST-20260920-1425", code_style),
     Paragraph("<b>Date / Time:</b>", table_cell_style), Paragraph("2026-09-20 14:25 UTC+7", table_cell_style)],
    [Paragraph("<b>Git Commit SHA:</b>", table_cell_style), Paragraph("26ab5affee580a061d7059ef0ebdb5a5c062e90a", code_style),
     Paragraph("<b>Git Branch:</b>", table_cell_style), Paragraph("hermes/document-review-simplification-v2", code_style)],
    [Paragraph("<b>Tenant / Entitas:</b>", table_cell_style), Paragraph("PT Kontraktor Utama Indonesia", table_cell_style),
     Paragraph("<b>Audit Mode:</b>", table_cell_style), Paragraph("DEDICATED J7 REVALIDATION", table_cell_style)],
    [Paragraph("<b>Claim Scope:</b>", table_cell_style), Paragraph("JOURNEY-SCOPED (Reporting Module)", table_cell_style),
     Paragraph("<b>Final Status:</b>", table_cell_style), Paragraph("<font color='#d97706'><b>PASS_WITH_FRICTION</b></font>", table_cell_style)],
]
meta_table = Table(meta_data, colWidths=[105, 165, 105, 165])
meta_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
elements.append(meta_table)
elements.append(Spacer(1, 8))

# Executive Summary
elements.append(Paragraph("1. Ringkasan Eksekutif", h1_style))
summary_text = (
    "Audit J7 memverifikasi ketertelusuran (traceability) dan integritas angka pada seluruh antarmuka pelaporan keuangan "
    "(General Ledger, Trial Balance, Laba Rugi, Neraca, Profitabilitas Proyek, dan Umur Piutang/Utang) menggunakan data "
    "transaksi sintetis terverifikasi dari J1, J3, J4, J5, dan J6. Hasil verifikasi akuntansi membuktikan bahwa "
    "<b>integritas matematis dan prinsip akuntansi terpenuhi 100%</b>: Total Debet == Total Kredit pada Neraca Saldo (Rp 393.130.988,86), "
    "Total Aset == Total Kewajiban + Ekuitas pada Neraca (Rp 56.819.011,14 dengan selisih Rp 0,00), pembatalan/reversal menghasilkan efek "
    "net-zero tanpa menghapus jejak audit, dan isolasi tenant berjalan ketat tanpa kebocoran data. Namun demikian, "
    "<b>status akhir ditetapkan PASS_WITH_FRICTION</b> akibat ditemukannya friksi navigasi audit signifikan: "
    "<b>WF-003 tetap OPEN</b> (baris jurnal pada Buku Besar tidak dapat diklik untuk menuju detail transaksi), "
    "<b>WF-017 baru diidentifikasi</b> (TransactionDetailPage tidak menampilkan nomor jurnal maupun tautan balik ke dokumen bukti asal), "
    "dan <b>WF-018 baru diidentifikasi</b> (nomor invoice/tagihan pada laporan umur piutang/utang berpenampilan link tetapi tidak interaktif)."
)
elements.append(Paragraph(summary_text, body_style))
elements.append(Spacer(1, 8))

# Report Surfaces Table
elements.append(Paragraph("2. Matriks Permukaan Laporan yang Diaudit (Reporting Surfaces)", h1_style))
surfaces_data = [
    [Paragraph("Laporan", table_header_style), Paragraph("Rute UI", table_header_style), Paragraph("Filter Tersedia", table_header_style), Paragraph("Drilldown", table_header_style), Paragraph("Status Integritas", table_header_style)],
    [Paragraph("Buku Besar (GL)", table_cell_style), Paragraph("/reports/general-ledger", code_style), Paragraph("Akun COA, Tanggal Mulai & Selesai", table_cell_style), Paragraph("TIDAK (WF-003)", table_cell_style), Paragraph("VALID (Mutasi & Saldo Akurat)", table_cell_style)],
    [Paragraph("Neraca Saldo (TB)", table_cell_style), Paragraph("/reports/trial-balance", code_style), Paragraph("Per Tanggal (as_of_date)", table_cell_style), Paragraph("TIDAK (Tabel Statis)", table_cell_style), Paragraph("VALID (Dr=Cr Rp 393,13 jt)", table_cell_style)],
    [Paragraph("Laba Rugi (P&L)", table_cell_style), Paragraph("/reports/profit-loss", code_style), Paragraph("Tanggal Mulai & Selesai", table_cell_style), Paragraph("YA (Klik Akun &rarr; GL)", table_cell_style), Paragraph("VALID (HPP Rp 34,25 jt)", table_cell_style)],
    [Paragraph("Posisi Keuangan (Neraca)", table_cell_style), Paragraph("/reports/balance-sheet", code_style), Paragraph("Per Tanggal (as_of_date)", table_cell_style), Paragraph("TIDAK (Tabel Statis)", table_cell_style), Paragraph("VALID (Aset=Pasiva Rp 56,8 jt)", table_cell_style)],
    [Paragraph("Profitabilitas Proyek", table_cell_style), Paragraph("/reports/project-profitability", code_style), Paragraph("Pemilih Proyek Kontraktor", table_cell_style), Paragraph("TIDAK (Kategori Statis)", table_cell_style), Paragraph("VALID (Biaya Langsung & Kas)", table_cell_style)],
    [Paragraph("Umur Piutang (AR Aging)", table_cell_style), Paragraph("/reports/ar-aging", code_style), Paragraph("Per Tanggal (as_of_date)", table_cell_style), Paragraph("TIDAK (WF-018)", table_cell_style), Paragraph("VALID (Bucket Aging Akurat)", table_cell_style)],
    [Paragraph("Umur Utang (AP Aging)", table_cell_style), Paragraph("/reports/ap-aging", code_style), Paragraph("Per Tanggal (as_of_date)", table_cell_style), Paragraph("TIDAK (WF-018)", table_cell_style), Paragraph("VALID (Bucket Aging Akurat)", table_cell_style)],
]
surfaces_table = Table(surfaces_data, colWidths=[95, 115, 120, 100, 110])
surfaces_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
elements.append(surfaces_table)
elements.append(Spacer(1, 8))

# Accounting Verification Details
elements.append(Paragraph("3. Verifikasi Akuntansi & Invarian Finansial", h1_style))
acct_items = [
    "<b>Keseimbangan Neraca Saldo:</b> Total Debet Rp 393.130.988,86 == Total Kredit Rp 393.130.988,86. Total Saldo Akhir Debet Rp 178.850.000 == Total Saldo Akhir Kredit Rp 178.850.000. Selisih = Rp 0,00.",
    "<b>Persamaan Akuntansi Neraca:</b> Total Aset (Rp 56.819.011,14) == Total Kewajiban (Rp 53.850.000) + Total Ekuitas (Rp 2.969.011,14). Selisih matematis = Rp 0,00 tanpa pos penyeimbang buatan.",
    "<b>Non-Duplikasi Pendapatan/Beban:</b> Pembayaran pelanggan (TRX-4 / JE-4 Rp 25 jt) dan tagihan vendor (TRX-6 / JE-6 Rp 12 jt) hanya menggerakkan kas dan akun neraca piutang/utang tanpa menduplikasi pendapatan atau beban di Laporan Laba Rugi.",
    "<b>Integritas Reversal (Net-Zero):</b> Reversal atas JE-11 (Rp 5.550.000) oleh JE-12 (Rp 5.550.000) menghasilkan mutasi kredit penyeimbang sempurna di Buku Besar akun 5101 dan mutasi debet di akun 2101 sehingga dampak laba rugi dan utang bernilai persis Rp 0,00.",
    "<b>Konsistensi Filter Tanggal & Saldo Awal:</b> Penyempitan filter tanggal ke 14-16 Sep 2026 secara dinamis menghitung Saldo Awal sebesar Rp 119.780.988,86 (persis saldo akhir per 10 Sep) dan hanya memunculkan mutasi JE-8 (Rp 2.250.000) sehingga saldo akhir menjadi Rp 122.030.988,86.",
    "<b>Isolasi Multi-Tenant:</b> Pengujian lintas-organisasi terhadap Tenant B membuktikan tidak ada satu pun baris jurnal atau saldo akun Tenant A yang bocor (Tenant B TB: 0 baris, Rp 0,00)."
]
for item in acct_items:
    elements.append(Paragraph(f"• {item}", body_style))
    elements.append(Spacer(1, 2))

elements.append(Spacer(1, 6))

# Known Findings & Evaluation
elements.append(Paragraph("4. Revalidasi Temuan & Temuan Baru", h1_style))
findings_data = [
    [Paragraph("ID", table_header_style), Paragraph("Tingkat", table_header_style), Paragraph("Status", table_header_style), Paragraph("Judul & Dampak UX", table_header_style)],
    [Paragraph("WF-003", code_style), Paragraph("<font color='#d97706'>MEDIUM</font>", table_cell_style), Paragraph("<b>OPEN</b>", table_cell_style),
     Paragraph("<b>Buku Besar tidak memiliki drilldown ke transaksi asal.</b><br/>Elemen nomor jurnal pada GeneralLedgerPage.tsx:136 dirender sebagai &lt;td&gt; statis. Auditor tidak dapat mengklik untuk melihat detail transaksi maupun bukti fisik.", table_cell_style)],
    [Paragraph("WF-017", code_style), Paragraph("<font color='#d97706'>MEDIUM</font>", table_cell_style), Paragraph("<b>OPEN</b>", table_cell_style),
     Paragraph("<b>Ketiadaan tautan balik ke dokumen bukti & jurnal pada detail transaksi.</b><br/>TransactionDetailPage tidak menampilkan nomor entri jurnal (JE-XXXXXX), baris debet/kredit, maupun tautan balik ke dokumen bukti sumber (DOC-XXXXXX), memutus alur audit balik.", table_cell_style)],
    [Paragraph("WF-018", code_style), Paragraph("<font color='#0284c7'>LOW</font>", table_cell_style), Paragraph("<b>OPEN</b>", table_cell_style),
     Paragraph("<b>Nomor invoice/bill pada Laporan Umur Piutang/Utang berpenampilan link tetapi tidak dapat diklik.</b><br/>Kelas text-indigo-700 font-bold memberikan affordance palsu (seolah hyperlink), namun elemen tidak memiliki handler navigasi ke transaksi.", table_cell_style)],
]
findings_table = Table(findings_data, colWidths=[45, 55, 50, 390])
findings_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
elements.append(findings_table)
elements.append(Spacer(1, 8))

# Visual Evidence Section
elements.append(PageBreak())
elements.append(Paragraph("5. Bukti Tangkapan Layar Interaksi Browser (Visual Evidence)", h1_style))
elements.append(Paragraph("Seluruh tangkapan layar diambil secara langsung pada sesi browser aktif:", body_style))
elements.append(Spacer(1, 4))

screenshots = [
    ("11-general-ledger-5101.png", "Buku Besar Akun 5101 (Harga Pokok Proyek): Menampilkan mutasi JE-8, JE-11, JE-12 (reversal net-zero), dan saldo akhir Rp 122.030.988,86."),
    ("12-trial-balance.png", "Neraca Saldo (Trial Balance): Keseimbangan sempurna total debet == total kredit (Rp 393.130.988,86) dan banner status seimbang."),
    ("13-profit-loss.png", "Laporan Laba Rugi: Pengelompokan pendapatan (Rp 25 jt) dan HPP (Rp 34,25 jt). Baris akun dapat diklik menuju Buku Besar."),
    ("14-balance-sheet.png", "Laporan Posisi Keuangan (Neraca): Validasi integritas Total Aset == Total Pasiva (Rp 56.819.011,14, selisih Rp 0,00)."),
    ("15-pl-to-ledger-drilldown.png", "Hasil Drilldown dari Laporan Laba Rugi ke Buku Besar: Filter akun 5101 dan rentang tanggal otomatis terpasang."),
    ("16-gl-no-drilldown.png", "WF-003 Revalidasi: Baris nomor jurnal pada Buku Besar merupakan teks statis non-interaktif tanpa tautan ke transaksi."),
    ("18-gl-filter-including.png", "Filter Tanggal Buku Besar (14-16 Sep 2026): Saldo awal dihitung dinamis (Rp 119,78 jt) dan mutasi JE-8 (Rp 2,25 jt) terisolasi sempurna."),
    ("20-project-profitability-j4.png", "Profitabilitas Proyek PRJ-2026-005: Isolasi proyek memisahkan pendapatan dan biaya langsung tanpa tercampur proyek lain."),
    ("21-gl-reversal-2101.png", "Buku Besar Akun 2101 (Utang Usaha): Reversal JE-11 dan JE-12 memulihkan saldo utang secara transparan tanpa manipulasi data."),
    ("22-ar-aging-unclickable.png", "WF-018: Nomor invoice pada Laporan Umur Piutang berpenampilan seperti tautan biru namun tidak memiliki interaksi klik.")
]

shot_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1425/screenshots')

for filename, caption in screenshots:
    path = os.path.join(shot_dir, filename)
    if os.path.exists(path):
        img = Image(path, width=495, height=245)
        cap = Paragraph(f"<b>Gambar {filename}:</b> {caption}", caption_style)
        elements.append(KeepTogether([img, Spacer(1, 2), cap, Spacer(1, 6)]))

# Scope Boundary & Signoff
elements.append(Spacer(1, 6))
elements.append(Paragraph("6. Batasan Cakupan & Kesimpulan Akhir", h1_style))
scope_text = (
    "<b>Diverifikasi pada Audit J7 (JOURNEY-SCOPED):</b><br/>"
    "1. Ketertelusuran angka dari dokumen sumber &rarr; transaksi &rarr; jurnal &rarr; buku besar &rarr; neraca saldo &rarr; laba rugi & neraca.<br/>"
    "2. Keseimbangan matematis debet-kredit pada Neraca Saldo dan persamaan Aset = Pasiva pada Neraca.<br/>"
    "3. Transparansi jurnal pembalik (reversal) yang menghasilkan net-zero tanpa merusak jejak audit.<br/>"
    "4. Penegakan isolasi tenant pada seluruh service modul pelaporan (MODULE-SCOPED).<br/><br/>"
    "<b>TIDAK Dibuktikan Secara Menyeluruh (NON-APPLICATION-WIDE):</b><br/>"
    "• Modul di luar pelaporan (misal intake WhatsApp live transport, ekspor custom konsultan pajak eksternal).<br/>"
    "• Ketiadaan bypass akuntansi pada endpoint mutasi manual di luar alur yang diaudit.<br/><br/>"
    "<b>STATUS AKHIR J7: PASS_WITH_FRICTION</b> (Integritas akuntansi sempurna, friksi navigasi audit WF-003, WF-017, WF-018)."
)
elements.append(Paragraph(scope_text, body_style))

doc.build(elements)
print(f"Audit report PDF generated successfully at: {pdf_path}")
shutil.copyfile(pdf_path, dogfood_pdf_path)
print(f"Copied to dogfood output at: {dogfood_pdf_path}")
