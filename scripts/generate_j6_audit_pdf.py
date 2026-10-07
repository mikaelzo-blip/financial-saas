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
output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1406')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J6_Error_Recovery_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J6_Error_Recovery_Audit_Report.pdf')
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
    leading=12,
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
    textColor=colors.HexColor('#1e293b')
)

body_bold = ParagraphStyle(
    'BodyBold',
    parent=body_style,
    fontName='Helvetica-Bold'
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
    'TableHeader',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7.5,
    leading=10,
    textColor=colors.white
)

table_body_style = ParagraphStyle(
    'TableBody',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7.5,
    leading=10,
    textColor=colors.HexColor('#1e293b')
)

table_body_bold = ParagraphStyle(
    'TableBodyBold',
    parent=table_body_style,
    fontName='Helvetica-Bold'
)

badge_style_pass = ParagraphStyle(
    'BadgePass',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=8,
    textColor=colors.HexColor('#15803d')
)

badge_style_fail = ParagraphStyle(
    'BadgeFail',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=8,
    textColor=colors.HexColor('#b91c1c')
)

caption_style = ParagraphStyle(
    'Caption',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=7.5,
    leading=10,
    textColor=colors.HexColor('#64748b'),
    spaceAfter=6
)

story = []

# Header
story.append(Paragraph("Financial SaaS &mdash; Active E2E Workflow Audit Report", title_style))
story.append(Paragraph("<b>Journey J6:</b> Error Recovery & Failure Handling &nbsp;|&nbsp; <b>Run ID:</b> E2E-TEST-20260920-1406 &nbsp;|&nbsp; <b>Date:</b> 2026-09-20", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceAfter=8))

# Meta Summary Table
meta_data = [
    [
        Paragraph("<b>Target Environment:</b> Local Development (FastAPI + React + Vite)", table_body_style),
        Paragraph("<b>Git Branch:</b> hermes/document-review-simplification-v2", table_body_style),
    ],
    [
        Paragraph("<b>Target Tenant:</b> PT Kontraktor Utama Indonesia (ID: 9670673b-...)", table_body_style),
        Paragraph("<b>Current Git SHA:</b> 26ab5affee580a061d7059ef0ebdb5a5c062e90a (short: 26ab5af)", table_body_style),
    ],
    [
        Paragraph("<b>Auditor Profile:</b> coding-agent (Hermes Agent / Browser Use)", table_body_style),
        Paragraph("<b>Final Status:</b> PASS_WITH_FRICTION", table_body_bold),
    ],
]
meta_table = Table(meta_data, colWidths=[270, 270])
meta_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(meta_table)
story.append(Spacer(1, 8))

# Section 1: Executive Summary
story.append(Paragraph("1. Executive Summary & Audit Scope", h1_style))
story.append(Paragraph(
    "Audit J6 (Error Recovery / Failure Handling) mengevaluasi ketahanan sistem Financial SaaS terhadap kesalahan pengguna, kegagalan validasi, "
    "klik ganda/konkurensi, transisi status tidak valid, interupsi alur (refresh/back), dan kebocoran kesalahan backend. "
    "Pengujian dilaksanakan secara browser-first pada UI Vite (port 5173), diverifikasi dengan penelusuran trace backend FastAPI (port 8000), "
    "serta divalidasi langsung terhadap data akuntansi di PostgreSQL Docker. Seluruh klaim temuan berlingkup JOURNEY-SCOPED.",
    body_style
))
story.append(Spacer(1, 6))

# Section 2: Error Recovery Matrix
story.append(Paragraph("2. Error Recovery Matrix", h1_style))
matrix_data = [
    [
        Paragraph("Kategori / Skenario", table_header_style),
        Paragraph("Hasil UI", table_header_style),
        Paragraph("Hasil Backend", table_header_style),
        Paragraph("Efek Akuntansi", table_header_style),
        Paragraph("Status", table_header_style)
    ],
    [
        Paragraph("<b>A1. Nominal = 0</b><br/>Input form transaksi nominal 0", table_body_style),
        Paragraph("Blokir sebelum submit: 'Nominal transaksi harus lebih besar dari 0.'", table_body_style),
        Paragraph("Tidak terpanggil", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>A2. Nominal Negatif</b><br/>Input nominal -50.000", table_body_style),
        Paragraph("Blokir sebelum submit: 'Nominal transaksi harus lebih besar dari 0.'", table_body_style),
        Paragraph("Tidak terpanggil", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>A3. Field Kosong</b><br/>Submit form tanpa bank/keterangan", table_body_style),
        Paragraph("HTML5 required alert + form banner", table_body_style),
        Paragraph("Tidak terpanggil", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>A4. Transfer Rek Asal = Tujuan</b><br/>Pilih bank asal sama dengan tujuan", table_body_style),
        Paragraph("Opsi bank asal otomatis difilter keluar dari tujuan", table_body_style),
        Paragraph("Tidak terpanggil", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>B1. Double-Click Submit</b><br/>Klik ganda cepat pada Simpan Transaksi", table_body_style),
        Paragraph("Navigasi ke detail transaksi kedua", table_body_style),
        Paragraph("HTTP 201 x 2 (terbuat 2 transaksi draft)", table_body_style),
        Paragraph("Draft STAGED (tidak ada jurnal)", table_body_style),
        Paragraph("FRICTION (WF-013)", badge_style_fail)
    ],
    [
        Paragraph("<b>B2. Double-Click Post</b><br/>Klik ganda cepat Posting ke Buku Besar", table_body_style),
        Paragraph("Tombol berubah jadi Reverse, status POSTED", table_body_style),
        Paragraph("Tepat 1 jurnal (JE-2026-000025)", table_body_style),
        Paragraph("Debit == Credit (Rp 1.5jt)", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>C1. Post Already-Posted</b><br/>POST /transactions/{id}/post pada status POSTED", table_body_style),
        Paragraph("Tombol post disembunyikan di UI", table_body_style),
        Paragraph("HTTP 500 (uq_je_transaction_id)", table_body_style),
        Paragraph("Rollback atomik (jurnal tidak ganda)", table_body_style),
        Paragraph("DEFECT (WF-014)", badge_style_fail)
    ],
    [
        Paragraph("<b>C2. Reverse Already-Reversed</b><br/>POST /transactions/{id}/reverse pada REVERSED", table_body_style),
        Paragraph("Tombol reverse disembunyikan di UI", table_body_style),
        Paragraph("HTTP 422 INVARIANT_VIOLATION", table_body_style),
        Paragraph("Tidak ada jurnal tambahan", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>C3. Approve Posted Document</b><br/>POST /documents/{id}/approve pada POSTED", table_body_style),
        Paragraph("Toast: 'Dokumen tidak sedang dalam status menunggu review.'", table_body_style),
        Paragraph("HTTP 409 Conflict", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>D1. Interrupted / Refresh Form</b><br/>Refresh halaman saat input sebagian", table_body_style),
        Paragraph("Input hilang (tanpa warning beforeunload)", table_body_style),
        Paragraph("Tidak ada request", table_body_style),
        Paragraph("Tidak ada data phantom", table_body_style),
        Paragraph("FRICTION (WF-016)", badge_style_fail)
    ],
    [
        Paragraph("<b>D2. Auth Expiration</b><br/>Token session hilang/expired", table_body_style),
        Paragraph("Redirect otomatis ke /login", table_body_style),
        Paragraph("HTTP 401 Unauthorized", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>F1. Reversal Transaksi Salah</b><br/>Batalkan transaksi operasional salah", table_body_style),
        Paragraph("Modal mewajibkan alasan; status jadi REVERSED", table_body_style),
        Paragraph("Buat jurnal pembalik JE-2026-000026", table_body_style),
        Paragraph("Net impact Rp 0,00 simetris", table_body_style),
        Paragraph("TERVALIDASI", badge_style_pass)
    ],
    [
        Paragraph("<b>E1. Kebocoran Error Teknis</b><br/>Pydantic / enum flags bocor ke UI", table_body_style),
        Paragraph("Toast memuat teks teknis / enum mentah", table_body_style),
        Paragraph("HTTP 422 skema error Pydantic", table_body_style),
        Paragraph("Tidak ada mutasi", table_body_style),
        Paragraph("OPEN (WF-002)", badge_style_fail)
    ]
]
matrix_table = Table(matrix_data, colWidths=[110, 130, 110, 110, 80])
matrix_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(matrix_table)
story.append(Spacer(1, 8))

# Section 3: Accounting Invariants & Ledger Immutability
story.append(Paragraph("3. Verifikasi Akuntansi & Immutability Buku Besar", h1_style))
story.append(Paragraph(
    "Pengujian recovery transaksi keuangan mengonfirmasi kepatuhan penuh terhadap <b>Prinsip Buku Besar Tak Berubah (Immutable Ledger)</b>. "
    "Transaksi yang salah dibukukan tidak pernah dimutasi langsung atau dihapus dari tabel PostgreSQL. Koreksi dilakukan secara ketat melalui "
    "penerbitan transaksi pembalik (REVERSAL) yang menghasilkan jurnal pembalik dengan debit dan kredit simetris.",
    body_style
))
story.append(Spacer(1, 4))

acct_data = [
    [
        Paragraph("ID Transaksi / Jurnal", table_header_style),
        Paragraph("Akun Debit", table_header_style),
        Paragraph("Akun Kredit", table_header_style),
        Paragraph("Nominal", table_header_style),
        Paragraph("Status Reversal", table_header_style),
        Paragraph("Dampak Bersih", table_header_style)
    ],
    [
        Paragraph("<b>TRX-2026-000026</b><br/>JE-2026-000025", table_body_style),
        Paragraph("6103 Beban Operasional Kantor", table_body_style),
        Paragraph("1101 Kas dan Bank (Mandiri)", table_body_style),
        Paragraph("Rp 1.500.000,00", table_body_style),
        Paragraph("is_reversed = TRUE", table_body_bold),
        Paragraph("+ Rp 1.500.000", table_body_style)
    ],
    [
        Paragraph("<b>TRX-2026-000027</b><br/>JE-2026-000026 (Pembalik)", table_body_style),
        Paragraph("1101 Kas dan Bank (Mandiri)", table_body_style),
        Paragraph("6103 Beban Operasional Kantor", table_body_style),
        Paragraph("Rp 1.500.000,00", table_body_style),
        Paragraph("is_reversed = FALSE", table_body_style),
        Paragraph("- Rp 1.500.000", table_body_style)
    ],
    [
        Paragraph("<b>TOTAL GABUNGAN</b>", table_body_bold),
        Paragraph("Debit = Rp 1.500.000,00", table_body_bold),
        Paragraph("Kredit = Rp 1.500.000,00", table_body_bold),
        Paragraph("Total Rp 3.000.000,00", table_body_bold),
        Paragraph("TERKAIT LENGKAP", table_body_bold),
        Paragraph("<b>Rp 0,00 (NET ZERO)</b>", badge_style_pass)
    ]
]
acct_table = Table(acct_data, colWidths=[100, 110, 110, 80, 80, 60])
acct_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f0fdf4')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(acct_table)
story.append(Spacer(1, 8))

# Section 4: Trace & Findings
story.append(Paragraph("4. Temuan Masalah & Analisis Akar Masalah", h1_style))

findings_data = [
    [
        Paragraph("ID", table_header_style),
        Paragraph("Severity", table_header_style),
        Paragraph("Judul & Ringkasan Temuan", table_header_style),
        Paragraph("Akar Masalah (Root Cause)", table_header_style),
        Paragraph("Status", table_header_style)
    ],
    [
        Paragraph("<b>WF-013</b>", table_body_bold),
        Paragraph("<font color='#b91c1c'><b>HIGH</b></font>", table_body_style),
        Paragraph("<b>Klik ganda submit membuat transaksi draft ganda</b><br/>Double click pada tombol 'Simpan Transaksi' menghasilkan 2 transaksi STAGED (TRX-2026-000025 dan TRX-2026-000026) dengan atribut identik.", table_body_style),
        Paragraph("Tombol submit dinonaktifkan via re-render state React (isLoading), yang tertunda dibanding event queue browser. Endpoint POST /transactions tidak memiliki idempotency key / debounce backend.", table_body_style),
        Paragraph("NEW", badge_style_fail)
    ],
    [
        Paragraph("<b>WF-014</b>", table_body_bold),
        Paragraph("<font color='#b91c1c'><b>HIGH</b></font>", table_body_style),
        Paragraph("<b>Posting transaksi yang sudah diposting menghasilkan HTTP 500</b><br/>Pemanggilan POST /transactions/{id}/post pada transaksi POSTED mengembalikan Internal Server Error alih-alih HTTP 409 Conflict.", table_body_style),
        Paragraph("ProcessingPolicyService mengubah workflow_status menjadi APPROVED di memori sebelum memanggil AccountingEngine.post_transaction, membypass validasi POSTED dan menabrak uq_je_transaction_id di Postgres.", table_body_style),
        Paragraph("NEW", badge_style_fail)
    ],
    [
        Paragraph("<b>WF-015</b>", table_body_bold),
        Paragraph("<font color='#d97706'><b>MEDIUM</b></font>", table_body_style),
        Paragraph("<b>Transaksi STAGED tidak dapat diedit, dibatalkan, atau dihapus</b><br/>Jika user salah menginput transaksi draft, UI hanya menyediakan opsi 'Posting ke Buku Besar'.", table_body_style),
        Paragraph("Ketiadaan endpoint PATCH/PUT/DELETE untuk transaksi draft. Pengguna terpaksa memposting transaksi salah lalu mereverse-nya.", table_body_style),
        Paragraph("NEW", badge_style_fail)
    ],
    [
        Paragraph("<b>WF-016</b>", table_body_bold),
        Paragraph("<font color='#64748b'><b>LOW</b></font>", table_body_style),
        Paragraph("<b>Ketiadaan guard navigasi 'beforeunload' pada form</b><br/>Refresh tidak sengaja atau klik tombol Back membersihkan seluruh input transaksi tanpa dialog konfirmasi.", table_body_style),
        Paragraph("Komponen TransactionForm dan DocumentReviewForm tidak memasang event listener window.onbeforeunload.", table_body_style),
        Paragraph("NEW", badge_style_fail)
    ],
    [
        Paragraph("<b>WF-002</b>", table_body_bold),
        Paragraph("<font color='#b91c1c'><b>HIGH</b></font>", table_body_style),
        Paragraph("<b>Kebocoran string error teknis / Pydantic ke UI</b><br/>Pesan validasi teknis bahasa Inggris dan nama flag enum (AMOUNT_MISMATCH, DATE_FAR) tampil mentah pada toast.", table_body_style),
        Paragraph("formatDocumentActionError dan ToastProvider menampilkan array detail pydantic loc.msg langsung tanpa lokalisasi.", table_body_style),
        Paragraph("REVALIDATED (OPEN)", badge_style_fail)
    ]
]
findings_table = Table(findings_data, colWidths=[40, 50, 180, 200, 70])
findings_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(findings_table)
story.append(Spacer(1, 10))

# Section 5: Browser Evidence Screenshots
story.append(PageBreak())
story.append(Paragraph("5. Bukti Eksekusi Browser & Tangkapan Layar", h1_style))

screenshots = [
    ("02-validation-empty-fields.png", "Gambar 1: Validasi HTML5 dan form memblokir submit form transaksi kosong sebelum mutasi."),
    ("03-validation-zero-amount.png", "Gambar 2: Validasi nominal = 0 menampilkan pesan berbahasa Indonesia 'Nominal transaksi harus lebih besar dari 0.'"),
    ("04-document-review-validation-flags.png", "Gambar 3: Reviu dokumen memblokir approval saat proyek belum dipilih dan terdapat flag review terbuka (WF-002)."),
    ("05-transaction-detail-staged.png", "Gambar 4: Detail transaksi hasil double-submit berstatus STAGED tanpa tombol Edit/Cancel (WF-013, WF-015)."),
    ("06-transaction-posted-single-journal.png", "Gambar 5: Transaksi berhasil diposting menghasilkan tepat 1 jurnal (JE-2026-000025); tombol beralih ke Reverse."),
    ("07-reversal-modal-reason-required.png", "Gambar 6: Modal pembatalan mewajibkan input alasan pembatalan sebelum reversal dapat dikonfirmasi."),
    ("08-transaction-reversed-no-actions.png", "Gambar 7: Transaksi berstatus REVERSED; seluruh tombol aksi mutasi dihilangkan dari antarmuka."),
    ("09-document-already-posted-approval-rejected.png", "Gambar 8: Percobaan persetujuan ulang dokumen yang sudah diposting ditolak dengan toast bahasa Indonesia yang jelas."),
    ("10-session-expired-redirect-login.png", "Gambar 9: Penghapusan sesi/token kedaluwarsa secara aman mengarahkan pengguna kembali ke halaman login.")
]

shot_dir = os.path.join(output_dir, 'screenshots')
for shot_file, caption in screenshots:
    shot_path = os.path.join(shot_dir, shot_file)
    if os.path.exists(shot_path):
        img = Image(shot_path, width=495, height=245)
        cap = Paragraph(f"<b>{caption}</b>", caption_style)
        story.append(KeepTogether([img, Spacer(1, 2), cap, Spacer(1, 6)]))

# Build Document
doc.build(story)
print(f"Audit PDF generated successfully: {pdf_path}")

# Copy to dogfood-output
shutil.copyfile(pdf_path, dogfood_pdf_path)
print(f"Dogfood copy updated: {dogfood_pdf_path}")
