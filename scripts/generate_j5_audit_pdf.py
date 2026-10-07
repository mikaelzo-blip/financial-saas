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
output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1350')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J5_Bank_Reconciliation_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J5_Bank_Reconciliation_Audit_Report.pdf')

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
    spaceBefore=6,
    spaceAfter=3
)

body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#1e293b'),
    spaceAfter=4
)

code_style = ParagraphStyle(
    'Code',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=7,
    leading=9,
    textColor=colors.HexColor('#0f172a')
)

table_header_style = ParagraphStyle(
    'TH',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7.5,
    leading=9.5,
    textColor=colors.white
)

table_cell_style = ParagraphStyle(
    'TC',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7.5,
    leading=9.5,
    textColor=colors.HexColor('#1e293b')
)

badge_style_pass = ParagraphStyle(
    'BadgePass',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=8,
    textColor=colors.HexColor('#166534')
)

badge_style_partial = ParagraphStyle(
    'BadgePartial',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=8,
    textColor=colors.HexColor('#854d0e')
)

badge_style_fail = ParagraphStyle(
    'BadgeFail',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=8,
    textColor=colors.HexColor('#991b1b')
)

story = []

# Title & Metadata Banner
story.append(Paragraph("Laporan Audit Alur Kerja E2E: J5 — Rekonsiliasi Bank", title_style))
story.append(Paragraph("Financial SaaS • Framework Audit v3 • Evaluasi Browser Riil, Jejak Backend & Integritas Akuntansi", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=8))

# Meta Table
meta_data = [
    [Paragraph("<b>Run ID:</b>", table_cell_style), Paragraph("E2E-TEST-20260920-1350", table_cell_style),
     Paragraph("<b>Git SHA / Branch:</b>", table_cell_style), Paragraph("26ab5af / hermes/document-review-simplification-v2", table_cell_style)],
    [Paragraph("<b>Entitas Tenant:</b>", table_cell_style), Paragraph("PT Kontraktor Utama Indonesia", table_cell_style),
     Paragraph("<b>Lingkungan:</b>", table_cell_style), Paragraph("Local Development (FastAPI + Vite + Postgres)", table_cell_style)],
    [Paragraph("<b>Rekening Bank:</b>", table_cell_style), Paragraph("Bank Mandiri (1101) - 978c8ceb-...", table_cell_style),
     Paragraph("<b>Status Akhir J5:</b>", table_cell_style), Paragraph("<b>PARTIAL</b> (Backend/Ledger Verified, UI Blocked)", badge_style_partial)],
]
t_meta = Table(meta_data, colWidths=[90, 180, 110, 160])
t_meta.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
]))
story.append(t_meta)
story.append(Spacer(1, 8))

# Executive Summary
story.append(Paragraph("1. Ringkasan Eksekutif", h1_style))
summary_text = (
    "Audit menyeluruh terhadap perjalanan alur kerja <b>J5 — Bank Reconciliation</b> dilakukan secara langsung pada sistem "
    "berjalan menggunakan browser nyata, trace backend interaktif, dan verifikasi basis data PostgreSQL. "
    "Hasil audit menunjukkan bahwa <b>layanan domain backend dan aturan integritas akuntansi bekerja dengan sangat baik</b>: "
    "deteksi duplikasi file (SHA-256), pencegahan double-matching rekonsiliasi, validasi kesesuaian nominal dan arah mutasi (debet vs kredit), "
    "serta isolasi multi-tenant terbukti kuat dan memenuhi batas ketat akuntansi.<br/><br/>"
    "Namun demikian, <b>antarmuka frontend (/bank-reconciliation) mengalami cacat integrasi kritis (WF-009)</b>: "
    "klien API frontend menduplikasi prefix URL <code>/api/v1</code> sehingga permintaan Axios menghasilkan <code>/api/v1/api/v1/...</code> (HTTP 404). "
    "Akibatnya pengguna tidak dapat mengakses fitur unggah rekening koran maupun visualisasi dasbor secara langsung di browser tanpa perbaikan klien. "
    "Selain itu ditemukan bahwa sistem <b>belum memiliki kapabilitas Undo / Unmatch (WF-010)</b> dan halaman UI <b>tidak memiliki tabel rincian baris mutasi bank (WF-011)</b>."
)
story.append(Paragraph(summary_text, body_style))
story.append(Spacer(1, 6))

# Status & Evidence Matrix Table
story.append(Paragraph("2. Matriks Verifikasi Komponen J5", h1_style))
matrix_data = [
    [Paragraph("Komponen / Aspek", table_header_style), Paragraph("Status", table_header_style), Paragraph("Metode Verifikasi", table_header_style), Paragraph("Bukti / Catatan", table_header_style)],
    [Paragraph("Frontend UI Navigation", table_cell_style), Paragraph("FAILED", badge_style_fail), Paragraph("Browser Real (Playwright/CDP)", table_cell_style), Paragraph("Halaman gagal muat akibat URL 404 (WF-009)", table_cell_style)],
    [Paragraph("Statement File Upload", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("API / Service Test", table_cell_style), Paragraph("Berhasil parse CSV, SHA-256 hash tersimpan", table_cell_style)],
    [Paragraph("Duplicate Import Block", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("API Idempotency Check", table_cell_style), Paragraph("Upload file identik ditolak HTTP 409 Conflict", table_cell_style)],
    [Paragraph("Deterministic Auto-Match", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("Service & DB Verification", table_cell_style), Paragraph("Cocok otomatis via aturan EXACT_DATE_AND_AMOUNT", table_cell_style)],
    [Paragraph("Duplicate Match Guard", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("API & DB Constraint", table_cell_style), Paragraph("Ditolak HTTP 409, constraint uq_statement_line aktif", table_cell_style)],
    [Paragraph("Nominal Mismatch Guard", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("API Invariant Test", table_cell_style), Paragraph("Ditolak HTTP 422 INVARIANT_VIOLATION", table_cell_style)],
    [Paragraph("Wrong Bank Account Guard", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("API Invariant Test", table_cell_style), Paragraph("Ditolak HTTP 422 (payment account mismatch)", table_cell_style)],
    [Paragraph("Journal Integrity (Dr==Cr)", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("PostgreSQL DB Query", table_cell_style), Paragraph("Total Debit = Total Kredit = Rp 2.500.000 (ck_je_balanced)", table_cell_style)],
    [Paragraph("No Duplicate Journal", table_cell_style), Paragraph("PASS", badge_style_pass), Paragraph("PostgreSQL DB Query", table_cell_style), Paragraph("Rekonsiliasi tidak menduplikasi jurnal beban/kas", table_cell_style)],
    [Paragraph("Undo / Unmatch Feature", table_cell_style), Paragraph("UNSUPPORTED", badge_style_fail), Paragraph("Code & API Inspection", table_cell_style), Paragraph("Tidak ada endpoint / tombol pembatalan rekonsiliasi (WF-010)", table_cell_style)],
    [Paragraph("Reversal Traceability", table_cell_style), Paragraph("PASS_WITH_FRICTION", badge_style_partial), Paragraph("API & DB Verification", table_cell_style), Paragraph("Reversal berhasil (Net Rp 0), namun link rekonsiliasi tidak ter-update (WF-012)", table_cell_style)],
]
t_matrix = Table(matrix_data, colWidths=[130, 75, 115, 220])
t_matrix.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
]))
story.append(t_matrix)
story.append(Spacer(1, 8))

# Accounting Trace & Integrity
story.append(Paragraph("3. Jejak Akuntansi & Integritas Data", h1_style))
acct_text = (
    "<b>A. Transaksi Sumber & Jurnal Terkait:</b><br/>"
    "• Transaksi: <code>TRX-2026-000023</code> (DIRECT_PURCHASE, Rp 2.500.000,00, Bank Mandiri)<br/>"
    "• Jurnal: <code>JE-2026-000023</code> — Dr 6199 Beban Operasional Lainnya Rp 2.500.000 / Cr 1101 Kas & Bank Rp 2.500.000.<br/>"
    "• Baris Kas/Bank: ID <code>31c0d9ef-de23-44cb-b857-8a6cfe517cbf</code> (Credit Rp 2.500.000, payment_account_id Mandiri).<br/><br/>"
    "<b>B. Rekening Koran & Hasil Rekonsiliasi:</b><br/>"
    "• File Rekening Koran: <code>mandiri_statement_20260920.csv</code> (Import ID: <code>96984b90-...</code>, Hash: <code>50b29128...</code>)<br/>"
    "• Baris 1: Debit Rp 2.500.000,00 -> Status: <b>MATCHED</b> (Reconciliation ID: <code>bc9f6f92-...</code>, Aturan: EXACT_DATE_AND_AMOUNT)<br/>"
    "• Baris 2: Debit Rp 25.000,00 -> Status: <b>UNMATCHED_BANK</b> (Tetap terbuka di antrean mutasi belum cocok)<br/><br/>"
    "<b>C. Integritas Buku Besar Pasca Rekonsiliasi:</b><br/>"
    "Total jurnal sebelum rekonsiliasi = 23, sesudah rekonsiliasi = 23. Terbukti proses rekonsiliasi hanya menghubungkan mutasi "
    "ke jurnal pembukuan dan <b>sama sekali tidak menduplikasi pencatatan beban maupun saldo kas</b>."
)
story.append(Paragraph(acct_text, body_style))
story.append(Spacer(1, 8))

# Findings Detail
story.append(Paragraph("4. Temuan Audit (Findings & Defect Registry)", h1_style))

findings = [
    ("WF-009", "HIGH", "Duplikasi Prefix '/api/v1' pada frontend/src/api/bankReconciliation.ts Memblokir UI",
     "<b>Lokasi:</b> frontend/src/api/bankReconciliation.ts:32, 45, 52, 61<br/>"
     "<b>Dampak Lapangan:</b> Saat pengguna membuka menu Kas & Bank -> Rekonsiliasi Bank, browser meminta URL <code>/api/v1/api/v1/bank-reconciliation/dashboard</code> "
     "yang menghasilkan HTTP 404 Not Found. Layar menampilkan alert error 'Data rekonsiliasi belum berhasil dimuat' dan tombol Coba Lagi secara permanen, "
     "sehingga modul rekonsiliasi bank tidak dapat diakses sama sekali melalui UI.<br/>"
     "<b>Rekomendasi:</b> Hapus prefix <code>/api/v1</code> pada seluruh fungsi di <code>bankReconciliationApi</code> agar konsisten dengan baseURL Axios."),

    ("WF-010", "MEDIUM", "Ketiadaan Fitur Undo / Unmatch Rekonsiliasi Bank di Seluruh Sistem",
     "<b>Lokasi:</b> backend/src/api/v1/bank_reconciliation.py & frontend/src/pages/reconciliation/BankReconciliationPage.tsx<br/>"
     "<b>Dampak Lapangan:</b> Sekali mutasi bank ter-rekonsiliasi (baik otomatis maupun manual), status terkunci secara permanen. "
     "Tidak ada endpoint API maupun tombol di antarmuka web untuk membatalkan (unmatch) pencocokan yang salah. "
     "Pengguna keuangan tidak memiliki mekanisme koreksi operasional mandiri.<br/>"
     "<b>Rekomendasi:</b> Sediakan endpoint <code>POST /api/v1/bank-reconciliation/matches/{id}/unmatch</code> yang mengembalikan status statement line ke UNMATCHED_BANK."),

    ("WF-011", "HIGH", "Ketiadaan Tabel Rincian Baris Mutasi Rekening Koran & Pemilih Kandidat di UI",
     "<b>Lokasi:</b> frontend/src/pages/reconciliation/BankReconciliationPage.tsx<br/>"
     "<b>Dampak Lapangan:</b> Antarmuka halaman rekonsiliasi hanya menyajikan 4 kartu metrik ringkasan (Total Masuk, Total Keluar, Ter-Rekonsiliasi, Kas Belum Teralokasi). "
     "Tidak tersedia tabel daftar mutasi rekening koran, status per baris, ataupun daftar transaksi kandidat untuk dipasangkan secara manual oleh staf keuangan.<br/>"
     "<b>Rekomendasi:</b> Implementasikan tabel dua kolom (Mutasi Bank vs Pembukuan Kas) dengan aksi pencocokan interaktif."),

    ("WF-012", "MEDIUM", "Reversal Transaksi Tidak Memeriksa Status Rekonsiliasi Bank",
     "<b>Lokasi:</b> backend/src/services/reversal_service.py<br/>"
     "<b>Dampak Lapangan:</b> Saat transaksi <code>TRX-2026-000023</code> dibatalkan melalui fitur Reversal resmi, transaksi pembalik <code>TRX-2026-000024</code> berhasil dibuat. "
     "Namun entitas <code>BankReconciliation</code> tetap berstatus MATCHED terhadap journal_line transaksi asal yang kini sudah <code>is_reversed=True</code>. "
     "Mutasi bank tetap tercatat telah cocok dengan jurnal yang secara hukum akuntansi sudah dibatalkan.<br/>"
     "<b>Rekomendasi:</b> ReversalService wajib memeriksa apakah ada BankReconciliation aktif pada jurnal yang dibatalkan, dan secara otomatis membatalkan linkage-nya.")
]

for f_id, f_sev, f_title, f_desc in findings:
    f_box = [
        [Paragraph(f"<b>[{f_id}] {f_title}</b>", table_header_style), Paragraph(f"<b>SEVERITAS: {f_sev}</b>", table_header_style)],
        [Paragraph(f_desc, table_cell_style), ""]
    ]
    t_f = Table(f_box, colWidths=[410, 130])
    t_f.setStyle(TableStyle([
        ('SPAN', (0, 1), (1, 1)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155') if f_sev == 'MEDIUM' else colors.HexColor('#b91c1c')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_f)
    story.append(Spacer(1, 4))

story.append(Spacer(1, 6))

# Dogfood & Adversarial UX Persona
story.append(Paragraph("5. Evaluasi UX & Persona Adversarial", h1_style))
ux_text = (
    "<b>Persona:</b> Pak Bambang (52 th), Staf Keuangan Senior PT Kontraktor Utama Indonesia.<br/>"
    "<i>\"Saya klik menu Rekonsiliasi Bank langsung muncul kotak merah besar bilang koneksi internet saya bermasalah. "
    "Padahal saya buka web lain lancar. Lalu kalaupun jalan, mana daftar rekening koran yang sudah diimpor? "
    "Masa cuma ada 4 kotak angka ringkasan? Kalau ada mutasi aneh dari bank, bagaimana saya tahu transaksi mana yang dicocokkan oleh sistem? "
    "Dan kalau sistem salah cocok, tidak ada tombol untuk batalkan! Sangat berisiko untuk urusan pembukuan bank perusahaan.\"</i><br/><br/>"
    "<b>Metrik UX Terukur:</b><br/>"
    "• Jumlah Klik Menuju Layar: 2 klik (Kas & Bank -> Rekonsiliasi Bank)<br/>"
    "• Drop-off Point: 100% pada pemuatan awal akibat bug URL 404 (WF-009)<br/>"
    "• Visibilitas Status Rekonsiliasi: Buruk (hanya ada metrik persen kelengkapan, tanpa daftar mutasi riil)<br/>"
    "• Kemampuan Koreksi (Recovery): 0% (tidak ada fitur unmatch/re-open di UI)"
)
story.append(Paragraph(ux_text, body_style))
story.append(Spacer(1, 8))

# Evidence Screenshots Section
story.append(PageBreak())
story.append(Paragraph("6. Lampiran Bukti Visual Otentik (Browser Headless CDP)", h1_style))
story.append(Paragraph("Seluruh tangkapan layar di bawah ini direkam langsung dari sesi Chrome headless selama audit berjalan.", subtitle_style))
story.append(Spacer(1, 6))

screenshots_to_include = [
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/04-bank-reconciliation-loaded.png", "Gambar 1: Halaman Rekonsiliasi Bank Terblokir Alert Error 404 Akibat Duplikasi Prefix URL (WF-009)"),
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/06-bank-recon-selected-account-error.png", "Gambar 2: Pemilihan Rekening Bank Mandiri Tetap Menghasilkan Error 404 Permanen pada Dasbor"),
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/08-transaction-create-filled.png", "Gambar 3: Form Pencatatan Transaksi Pembelian Langsung Rp 2.500.000 Melalui Bank Mandiri"),
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/10-transaction-posted.png", "Gambar 4: Transaksi TRX-2026-000023 Berhasil Diposting ke Buku Besar (Siap Direkonsiliasikan)"),
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/15-payment-accounts-after-recon.png", "Gambar 5: Halaman Akun Kas & Bank (/payment-accounts) Menampilkan Saldo Berjalan Riil Bank Mandiri"),
    ("docs/audits/E2E-TEST-20260920-1350/screenshots/16-reversal-modal.png", "Gambar 6: Modal Konfirmasi Reversal Transaksi TRX-2026-000023 untuk Cleanup Pasca Rekonsiliasi"),
]

for img_rel_path, caption in screenshots_to_include:
    full_path = os.path.abspath(img_rel_path)
    if os.path.exists(full_path):
        img = Image(full_path, width=495, height=245)
        caption_para = Paragraph(caption, subtitle_style)
        story.append(KeepTogether([img, Spacer(1, 2), caption_para, Spacer(1, 6)]))

doc.build(story)
print(f"Primary PDF generated at: {pdf_path}")

os.makedirs(os.path.dirname(dogfood_pdf_path), exist_ok=True)
shutil.copyfile(pdf_path, dogfood_pdf_path)
print(f"Dogfood copy generated at: {dogfood_pdf_path}")
