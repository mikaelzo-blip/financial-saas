import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Target output paths
output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1345')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J4_AR_Customer_Receipt_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J4_AR_Customer_Receipt_Audit_Report.pdf')

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
    fontSize=16,
    leading=20,
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

h2_style = ParagraphStyle(
    'H2',
    parent=styles['Heading3'],
    fontName='Helvetica-Bold',
    fontSize=9.5,
    leading=13,
    textColor=colors.HexColor('#334155'),
    spaceBefore=5,
    spaceAfter=3
)

body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#1e293b'),
    spaceAfter=3
)

bullet_style = ParagraphStyle(
    'Bullet',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#334155'),
    leftIndent=12,
    spaceAfter=2
)

table_header_style = ParagraphStyle(
    'TableHeader',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=8,
    leading=10,
    textColor=colors.HexColor('#ffffff')
)

table_cell_style = ParagraphStyle(
    'TableCell',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7.5,
    leading=9.5,
    textColor=colors.HexColor('#1e293b')
)

caption_style = ParagraphStyle(
    'Caption',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=7.5,
    leading=10,
    textColor=colors.HexColor('#64748b'),
    spaceBefore=3,
    spaceAfter=6
)

story = []

# Header
story.append(Paragraph("Financial SaaS &mdash; E2E Workflow Audit Report", title_style))
story.append(Paragraph("<b>Journey J4:</b> Piutang Usaha &amp; Penerimaan Pelanggan (AR / Customer Receipt) | Run ID: <b>E2E-TEST-20260920-1345</b>", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=8))

# Metadata Table
meta_data = [
    [Paragraph("<b>Parameter</b>", table_header_style), Paragraph("<b>Nilai Audit</b>", table_header_style), Paragraph("<b>Parameter</b>", table_header_style), Paragraph("<b>Nilai Audit</b>", table_header_style)],
    [Paragraph("Git Commit SHA", table_cell_style), Paragraph("26ab5affee58 (clean)", table_cell_style), Paragraph("Environment", table_cell_style), Paragraph("Local Development (Docker Postgres)", table_cell_style)],
    [Paragraph("Active Branch", table_cell_style), Paragraph("hermes/document-review-simplification-v2", table_cell_style), Paragraph("Tenant Target", table_cell_style), Paragraph("PT Kontraktor Utama Indonesia", table_cell_style)],
    [Paragraph("Frontend URL", table_cell_style), Paragraph("http://localhost:5173", table_cell_style), Paragraph("Backend Health", table_cell_style), Paragraph("http://127.0.0.1:8000 (healthy)", table_cell_style)],
    [Paragraph("Audit Scope", table_cell_style), Paragraph("JOURNEY-SCOPED (J4 AR)", table_cell_style), Paragraph("Status Akhir", table_cell_style), Paragraph("<b>PASS_WITH_FRICTION</b>", table_cell_style)],
]
meta_table = Table(meta_data, colWidths=[110, 160, 110, 160])
meta_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.HexColor('#ffffff')]),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
]))
story.append(meta_table)
story.append(Spacer(1, 8))

# Executive Summary
story.append(Paragraph("1. Executive Summary &amp; Verification Status", h1_style))
summary_text = (
    "Audit menyeluruh Journey J4 (Piutang Usaha &amp; Penerimaan Pembayaran Pelanggan) telah berhasil "
    "dieksekusi menggunakan browser automation langsung pada frontend React (port 5173), backend FastAPI (port 8000), "
    "dan database PostgreSQL Docker. Alur dimulai dari pendaftaran master data sintetis (Customer &amp; Project), pembuatan tagihan "
    "pelanggan (Customer Invoice) Rp 15.000.000, penerimaan sebagian (Partial Receipt) Rp 5.000.000, penolakan overpayment "
    "Rp 20.000.000, pelunasan sisa tagihan (Full Settlement) Rp 10.000.000, verifikasi pencegahan double-payment pada invoice lunas, "
    "rekonsiliasi mutlak Buku Besar (GL) &amp; Neraca Saldo (TB), hingga pembersihan menyeluruh (Full Reversal Cleanup) "
    "dengan dampak saldo akhir net Rp 0 pada seluruh akun riil. Seluruh posting akuntansi mematuhi prinsip double-entry balanced."
)
story.append(Paragraph(summary_text, body_style))
story.append(Spacer(1, 6))

# Accounting Verification Table
story.append(Paragraph("2. Accounting Invariants &amp; Ledger Verification", h1_style))
acct_data = [
    [Paragraph("<b>Tahap Transaksi</b>", table_header_style), Paragraph("<b>Kode Trx / Jurnal</b>", table_header_style), Paragraph("<b>Debit (Akun / Nominal)</b>", table_header_style), Paragraph("<b>Kredit (Akun / Nominal)</b>", table_header_style), Paragraph("<b>Status Ledger</b>", table_header_style)],
    [Paragraph("1. Tagihan Pelanggan", table_cell_style), Paragraph("TRX-000017<br/>JE-000017", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 15.000.000", table_cell_style), Paragraph("4101 Pendapatan Proyek<br/>Rp 15.000.000", table_cell_style), Paragraph("BALANCED<br/>Pendapatan diakui 1x", table_cell_style)],
    [Paragraph("2. Penerimaan Sebagian", table_cell_style), Paragraph("TRX-000018<br/>JE-000018", table_cell_style), Paragraph("1101 Kas/Bank (Mandiri)<br/>Rp 5.000.000", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 5.000.000", table_cell_style), Paragraph("BALANCED<br/>Sisa AR Rp 10jt", table_cell_style)],
    [Paragraph("3. Pelunasan Sisa", table_cell_style), Paragraph("TRX-000019<br/>JE-000019", table_cell_style), Paragraph("1101 Kas/Bank (BCA)<br/>Rp 10.000.000", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 10.000.000", table_cell_style), Paragraph("BALANCED<br/>Sisa AR Rp 0 (LUNAS)", table_cell_style)],
    [Paragraph("4. Reversal Bayar 2", table_cell_style), Paragraph("TRX-000020<br/>JE-000020", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 10.000.000", table_cell_style), Paragraph("1101 Kas/Bank (BCA)<br/>Rp 10.000.000", table_cell_style), Paragraph("BALANCED<br/>AR pulih ke Rp 10jt", table_cell_style)],
    [Paragraph("5. Reversal Bayar 1", table_cell_style), Paragraph("TRX-000021<br/>JE-000021", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 5.000.000", table_cell_style), Paragraph("1101 Kas/Bank (Mandiri)<br/>Rp 5.000.000", table_cell_style), Paragraph("BALANCED<br/>AR pulih ke Rp 15jt", table_cell_style)],
    [Paragraph("6. Reversal Invoice", table_cell_style), Paragraph("TRX-000022<br/>JE-000022", table_cell_style), Paragraph("4101 Pendapatan Proyek<br/>Rp 15.000.000", table_cell_style), Paragraph("1201 Piutang Usaha<br/>Rp 15.000.000", table_cell_style), Paragraph("BALANCED<br/>Net dampak Rp 0", table_cell_style)],
    [Paragraph("<b>TOTAL NET IMPACT</b>", table_cell_style), Paragraph("<b>6 Jurnal Mutlak</b>", table_cell_style), Paragraph("<b>1101: Net Rp 0<br/>1201: Net Rp 0</b>", table_cell_style), Paragraph("<b>4101: Net Rp 0</b>", table_cell_style), Paragraph("<b>ZERO RESIDUAL EFFECT</b>", table_cell_style)]
]
acct_table = Table(acct_data, colWidths=[95, 80, 130, 135, 100])
acct_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#f8fafc'), colors.HexColor('#ffffff')]),
    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
]))
story.append(acct_table)
story.append(Spacer(1, 8))

# Mandatory Backend Trace
story.append(Paragraph("3. Mandatory Backend Trace (UI &rarr; API &rarr; Engine &rarr; Subledger)", h1_style))
trace_text = (
    "<b>A. Pembuatan Tagihan Pelanggan (Customer Invoice):</b><br/>"
    "<code>TransactionCreatePage.tsx</code> &rarr; <code>transactionsApi.create(CUSTOMER_INVOICE)</code> &rarr; "
    "<code>POST /api/v1/transactions</code> &rarr; <code>TransactionService.create_transaction</code> (Validasi status APPROVED) &rarr; "
    "<code>POST /api/v1/transactions/{id}/post</code> &rarr; <code>AccountingEngine.post_transaction</code> &rarr; "
    "<code>PostingRuleRegistry</code> (Dr 1201 / Cr 4101) &rarr; <code>CustomerARService.issue_customer_invoice</code> (Tabel <code>customer_invoices</code>).<br/><br/>"
    "<b>B. Penerimaan Kas/Bank Pelanggan (Customer Payment):</b><br/>"
    "<code>ReceivablesPage.tsx</code> (Klik 'Terima Bayar') &rarr; <code>CustomerPaymentAllocationModal.tsx</code> &rarr; "
    "<code>receivablesApi.allocatePayment(...)</code> &rarr; <code>POST /api/v1/customer-payments</code> &rarr; "
    "<code>record_customer_payment</code> &rarr; <code>TransactionService.create_transaction(CUSTOMER_PAYMENT)</code> &rarr; "
    "<code>AccountingEngine.post_transaction</code> (Dr 1101 Kas/Bank / Cr 1201 Piutang Usaha) &rarr; "
    "<code>CustomerARService.allocate_customer_payment</code> (Tabel <code>customer_payment_allocations</code>) &rarr; "
    "<code>MoneyMovementService.synchronize_payment_money_movement</code> (Tabel <code>money_movements</code>)."
)
story.append(Paragraph(trace_text, body_style))
story.append(Spacer(1, 8))

# Edge Cases & Idempotency
story.append(Paragraph("4. Scenario Testing &amp; Idempotency Protection", h1_style))
cases = [
    "<b>Scenario A (Full Receipt):</b> Penerimaan sisa nominal Rp 10.000.000 berhasil mencatat transaksi kas masuk dan mengubah status invoice menjadi LUNAS (Sisa Piutang Rp 0).",
    "<b>Scenario B (Partial Receipt):</b> Penerimaan parsial Rp 5.000.000 berhasil mengurangi sisa piutang secara akurat dari Rp 15.000.000 menjadi Rp 10.000.000, status tetap aktif, dan tombol bayar tetap tersedia.",
    "<b>Scenario C (Overpayment Rejected):</b> Input pembayaran Rp 20.000.000 pada sisa piutang Rp 15.000.000 ditolak oleh backend (HTTP 422 INVARIANT_VIOLATION: <i>Customer payment amount exceeds outstanding balance</i>). Tidak ada mutasi finansial.",
    "<b>Scenario D (Settled Invoice Protection):</b> Pada invoice yang telah berstatus LUNAS, tombol di UI berganti menjadi label teks 'Lunas' tanpa aksi klik. Percobaan POST langsung ke API ditolak (HTTP 422: <i>Invoice is already fully paid</i>).",
    "<b>Scenario E (Two-Stage Reversal Cleanup):</b> Reversal dilakukan secara berurutan: Pembayaran 2 &rarr; Pembayaran 1 &rarr; Invoice. Setiap pembatalan memulihkan saldo piutang dan saldo kas/bank ke posisi sebelumnya secara bilateral tanpa menghapus riwayat transaksi."
]
for c in cases:
    story.append(Paragraph(f"&bull; {c}", bullet_style))
story.append(Spacer(1, 8))

# Findings Section
story.append(Paragraph("5. Audit Findings &amp; UX Friction", h1_style))
findings_data = [
    [Paragraph("<b>ID</b>", table_header_style), Paragraph("<b>Severity</b>", table_header_style), Paragraph("<b>Judul &amp; Ringkasan Masalah</b>", table_header_style), Paragraph("<b>Dampak &amp; Rekomendasi</b>", table_header_style)],
    [Paragraph("<b>WF-006</b>", table_cell_style), Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell_style), Paragraph("<b>Gagal Pemetaan Error Backend pada Modal Pembayaran</b><br/><code>CustomerPaymentAllocationModal</code> membaca <code>err.response?.data?.detail</code>, padahal backend mengembalikan <code>error.message</code>. Saat overpayment, user melihat toast generik 'Gagal mencatat pembayaran invoice.'", table_cell_style), Paragraph("User tidak tahu mengapa pembayaran gagal (melebihi limit piutang). Update komponen untuk membaca <code>error.message</code>.", table_cell_style)],
    [Paragraph("<b>WF-007</b>", table_cell_style), Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_cell_style), Paragraph("<b>Field Vendor/Pelanggan &amp; Akun Kas '-' pada Detail Transaksi</b><br/>Halaman detail transaksi <code>CUSTOMER_PAYMENT</code> menampilkan '-' untuk counterparty dan akun kas/bank, meskipun tersimpan valid di DB.", table_cell_style), Paragraph("Staf keuangan tidak dapat memverifikasi pelanggan atau rekening bank dari halaman detail transaksi tanpa membuka jurnal.", table_cell_style)],
    [Paragraph("<b>WF-008</b>", table_cell_style), Paragraph("<font color='#2563eb'><b>LOW</b></font>", table_cell_style), Paragraph("<b>Tidak Ada Tautan ke Invoice pada Transaksi Pembayaran</b><br/>Pada <code>TransactionDetailPage</code> untuk pembayaran pelanggan, tidak tercantum nomor invoice yang dilunasi.", table_cell_style), Paragraph("Traceability terhambat; staf harus cross-check manual ke menu Piutang Usaha.", table_cell_style)],
]
f_table = Table(findings_data, colWidths=[45, 60, 235, 200])
f_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.HexColor('#ffffff')]),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
]))
story.append(f_table)
story.append(Spacer(1, 10))

# Screenshots Section
story.append(PageBreak())
story.append(Paragraph("6. Browser Visual Evidence &amp; Verification Artifacts", h1_style))
story.append(Paragraph("Tangkapan layar otentik dari eksekusi browser headless Chrome selama proses audit aktif.", body_style))
story.append(Spacer(1, 6))

screenshots = [
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/14-invoice-form-filled.png", "Gambar 1: Form Input Tagihan Pelanggan (Customer Invoice) Rp 15.000.000 dengan Customer & Proyek Sintetis"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/17-trx-posted.png", "Gambar 2: Detail Transaksi Tagihan Berstatus 'SUDAH DIPOSTING' (Debit Piutang Usaha / Kredit Pendapatan Proyek)"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/18-receivables-list-with-invoice.png", "Gambar 3: Halaman Piutang Usaha Menampilkan Sisa Tagihan Rp 15.000.000 dengan Aksi 'Terima Bayar'"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/21-overpayment-toast.png", "Gambar 4: Penolakan Overpayment Rp 20.000.000 (Backend Invariant Guard HTTP 422)"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/23-after-partial-payment.png", "Gambar 5: Halaman Piutang setelah Penerimaan Parsial Rp 5.000.000 (Sisa Piutang Berkurang Menjadi Rp 10.000.000)"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/26-after-full-payment.png", "Gambar 6: Halaman Piutang setelah Pelunasan Penuh (Status LUNAS, Sisa Piutang Rp 0, Tombol Berubah Menjadi Teks 'Lunas')"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/29-trial-balance.png", "Gambar 7: Neraca Saldo (Trial Balance) Terverifikasi Seimbang Sempurna Selama Siklus Piutang Aktif"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/33-receivables-after-reversing-payment2.png", "Gambar 8: Reversal Pembayaran 2 Otomatis Memulihkan Saldo Piutang ke Rp 10.000.000 dan Tombol Bayar Kembali Aktif"),
    ("docs/audits/E2E-TEST-20260920-1345/screenshots/38-trial-balance-after-cleanup.png", "Gambar 9: Neraca Saldo setelah Full Reversal Cleanup (Net Dampak Finansial Nol pada Seluruh Akun Riil)")
]

for img_rel_path, caption in screenshots:
    full_path = os.path.abspath(img_rel_path)
    if os.path.exists(full_path):
        img = Image(full_path, width=495, height=245)
        cap = Paragraph(caption, caption_style)
        story.append(KeepTogether([img, cap, Spacer(1, 4)]))

# Build PDF
doc.build(story)
print(f"Primary PDF generated at: {pdf_path}")

# Copy to dogfood-output
os.makedirs(os.path.dirname(dogfood_pdf_path), exist_ok=True)
shutil.copyfile(pdf_path, dogfood_pdf_path)
print(f"Dogfood copy generated at: {dogfood_pdf_path}")
