import os
import sys
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1505')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J8_WhatsApp_Web_Review_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J8_WhatsApp_Web_Review_Audit_Report.pdf')
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
    fontSize=14,
    leading=18,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=3
)

subtitle_style = ParagraphStyle(
    'DocSub',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#475569'),
    spaceAfter=6
)

h1_style = ParagraphStyle(
    'H1',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=10.5,
    leading=13,
    textColor=colors.HexColor('#1e293b'),
    spaceBefore=7,
    spaceAfter=3
)

h2_style = ParagraphStyle(
    'H2',
    parent=styles['Heading3'],
    fontName='Helvetica-Bold',
    fontSize=9,
    leading=12,
    textColor=colors.HexColor('#334155'),
    spaceBefore=5,
    spaceAfter=2
)

body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7.5,
    leading=10.5,
    textColor=colors.HexColor('#334155')
)

table_header_style = ParagraphStyle(
    'TH',
    parent=styles['Normal'],
    fontName='Helvetica-Bold',
    fontSize=7,
    leading=9.5,
    textColor=colors.HexColor('#ffffff')
)

table_cell_style = ParagraphStyle(
    'TD',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=7,
    leading=9.5,
    textColor=colors.HexColor('#1e293b')
)

code_style = ParagraphStyle(
    'CodeStyle',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=6.5,
    leading=8.5,
    textColor=colors.HexColor('#0f172a')
)

caption_style = ParagraphStyle(
    'Caption',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=6.5,
    leading=8.5,
    textColor=colors.HexColor('#64748b'),
    alignment=1
)

story = []

# Header
story.append(Paragraph("Financial SaaS — E2E Workflow Audit Report: J8", title_style))
story.append(Paragraph("<b>Workflow:</b> WhatsApp Intake → Web Review &bull; <b>Run ID:</b> E2E-TEST-20260920-1505 &bull; <b>Git SHA:</b> 26ab5af &bull; <b>Date:</b> 2026-09-20", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=6))

# Meta Table
meta_data = [
    [Paragraph("<b>Status Workflow:</b>", table_cell_style), Paragraph("<font color='#d97706'><b>PARTIAL (Verifikasi Internal Lengkap; Transport Eksternal Tidak Dapat Diuji)</b></font>", table_cell_style),
     Paragraph("<b>Lingkungan:</b>", table_cell_style), Paragraph("Local Development (PostgreSQL, FastAPI, Vite, Baileys Bridge)", table_cell_style)],
    [Paragraph("<b>Tenant Uji:</b>", table_cell_style), Paragraph("PT Kontraktor Utama Indonesia (9670673b-c0fd-4ebe-87e4-a646358084ea)", table_cell_style),
     Paragraph("<b>Transport Mode:</b>", table_cell_style), Paragraph("INTERNAL_INGESTION_ONLY (Baileys Connected, No Live Mobile Sender)", table_cell_style)],
    [Paragraph("<b>Dokumen Uji:</b>", table_cell_style), Paragraph("Sintetis: DOC-WA-27300435 (Invoice Rp 3.750.000) & DOC-2026-000018 (Receipt Rp 1.250.000)", table_cell_style),
     Paragraph("<b>Temuan Baru:</b>", table_cell_style), Paragraph("<font color='#dc2626'><b>WF-019 (Medium)</b></font> — Duplikasi prefix /api/v1 di inboxApi", table_cell_style)]
]
meta_table = Table(meta_data, colWidths=[90, 180, 90, 180])
meta_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(meta_table)
story.append(Spacer(1, 6))

# Ringkasan Eksekutif
story.append(Paragraph("1. Ringkasan Eksekutif & Klasifikasi Transport", h1_style))
story.append(Paragraph(
    "Audit alur kerja J8 (WhatsApp Intake → Web Review) dieksekusi menggunakan metodologi pengujian aktif non-destruktif v3. "
    "Berdasarkan investigasi arsitektur live, stack lokal menjalankan layanan jembatan <b>Baileys Bridge</b> pada port 3000 (status terhubung) "
    "dan worker analitik lokal. Namun, karena tidak ada pengirim perangkat seluler fisik eksternal yang aktif mengirimkan pesan melalui jaringan "
    "seluler/WhatsApp publik saat sesi otomatis ini berjalan, lingkungan diklasifikasikan secara ketat sebagai <b>INTERNAL_INGESTION_ONLY</b>. "
    "Sesuai aturan audit, status transport eksternal dicatat <b>NOT_VERIFIED</b> dan status alur J8 ditandai <b>PARTIAL</b> tanpa fabrikasi klaim.",
    body_style
))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "Seluruh lapisan internal berhasil diverifikasi secara end-to-end: penyerapan berkas melalui <i>Remote Relay Capture</i> dan <i>Hermes Document Intake</i>, "
    "penyimpanan blob & hashing kriptografis SHA-256, eksekusi OCR dan ekstraksi data oleh background worker, pengenalan entitas dan deteksi flag review, "
    "visibilitas pada antarmuka web, persetujuan review pengguna, posting otomatis ke buku besar umum (General Ledger), serta pembalikan (reversal) "
    "akuntansi bersih dengan dampak finansial nol.",
    body_style
))
story.append(Spacer(1, 6))

# Arsitektur & Trace Ingestion
story.append(Paragraph("2. Pemetaan Arsitektur & Jalur Penyerapan Berkas", h1_style))
arch_data = [
    [Paragraph("Komponen / Lapisan", table_header_style), Paragraph("Implementasi Live", table_header_style), Paragraph("Metode / Endpoint", table_header_style), Paragraph("Status Verifikasi", table_header_style)],
    [Paragraph("Transport Provider", table_cell_style), Paragraph("Baileys Bridge (Node.js port 3000) & Meta Webhook", table_cell_style), Paragraph("GET /messages; POST /webhook", table_cell_style), Paragraph("PARTIAL (Bridge Connected)", table_cell_style)],
    [Paragraph("Hermes Intake Boundary", table_cell_style), Paragraph("HermesApiClient + Tenant Token Auth", table_cell_style), Paragraph("POST /api/v1/hermes/documents/upload", table_cell_style), Paragraph("VERIFIED (202 Accepted)", table_cell_style)],
    [Paragraph("Remote Relay Intake", table_cell_style), Paragraph("RemoteInboxService (Capture & Backlog Sync)", table_cell_style), Paragraph("POST /api/v1/inbox/capture & /sync", table_cell_style), Paragraph("VERIFIED (201 Created & 200 OK)", table_cell_style)],
    [Paragraph("Storage & Hashing", table_cell_style), Paragraph("StorageService + SHA-256 Cryptographic Hash", table_cell_style), Paragraph("storage_path & file_hash", table_cell_style), Paragraph("VERIFIED (Invarian Terpenuhi)", table_cell_style)],
    [Paragraph("Async Worker Pipeline", table_cell_style), Paragraph("DocumentPipeline + DeferredAnalysisService", table_cell_style), Paragraph("JobQueue: DOCUMENT_DEFERRED_ANALYSIS", table_cell_style), Paragraph("VERIFIED (Ekstraksi Berhasil)", table_cell_style)],
    [Paragraph("Web Review UI", table_cell_style), Paragraph("DocumentListPage.tsx & DocumentReviewPage.tsx", table_cell_style), Paragraph("GET /documents & /review", table_cell_style), Paragraph("VERIFIED (Status & Metadata Tampil)", table_cell_style)],
    [Paragraph("Financial Posting", table_cell_style), Paragraph("DocumentPostingService & Accounting Engine", table_cell_style), Paragraph("POST /api/v1/documents/{id}/post", table_cell_style), Paragraph("VERIFIED (Debit = Kredit = 3.750.000)", table_cell_style)]
]
arch_table = Table(arch_data, colWidths=[110, 160, 150, 120])
arch_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(arch_table)
story.append(Spacer(1, 6))

# Bukti Pengujian & Tangkapan Layar (Page 1 Screenshots)
story.append(Paragraph("3. Bukti Verifikasi Antarmuka Browser (Web Review)", h1_style))

img1_path = os.path.abspath('docs/audits/E2E-TEST-20260920-1505/screenshots/01_document_list_page.png')
img2_path = os.path.abspath('docs/audits/E2E-TEST-20260920-1505/screenshots/02_documents_filtered_whatsapp.png')

shot_data = []
row1 = []
if os.path.exists(img1_path):
    row1.append(Image(img1_path, width=265, height=135))
else:
    row1.append(Paragraph("Screenshot 01 missing", body_style))
if os.path.exists(img2_path):
    row1.append(Image(img2_path, width=265, height=135))
else:
    row1.append(Paragraph("Screenshot 02 missing", body_style))
shot_data.append(row1)

shot_table = Table(shot_data, colWidths=[270, 270])
shot_table.setStyle(TableStyle([
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 1),
    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
]))
story.append(shot_table)

cap_data = [
    [Paragraph("Gbr 1: Kartu Status Integrasi WhatsApp (Terhubung, Antrean: 1, Masuk: 20 Sep 2026)", caption_style),
     Paragraph("Gbr 2: Filter Saluran WhatsApp (DOC-2026-000018 & DOC-WA-27300435 masuk antrean)", caption_style)]
]
cap_table = Table(cap_data, colWidths=[270, 270])
cap_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
story.append(cap_table)
story.append(Spacer(1, 6))

story.append(PageBreak())

# Halaman 2: Detail Review, Posting, dan Temuan WF-019
story.append(Paragraph("4. Ekstraksi OCR, Review Pengguna & Posting Finansial", h1_style))

img4_path = os.path.abspath('docs/audits/E2E-TEST-20260920-1505/screenshots/04_document_review_page.png')
img5_path = os.path.abspath('docs/audits/E2E-TEST-20260920-1505/screenshots/05_document_approved_ready_to_post.png')

shot_data2 = []
row2 = []
if os.path.exists(img4_path):
    row2.append(Image(img4_path, width=265, height=135))
else:
    row2.append(Paragraph("Screenshot 04 missing", body_style))
if os.path.exists(img5_path):
    row2.append(Image(img5_path, width=265, height=135))
else:
    row2.append(Paragraph("Screenshot 05 missing", body_style))
shot_data2.append(row2)

shot_table2 = Table(shot_data2, colWidths=[270, 270])
shot_table2.setStyle(TableStyle([
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 1),
    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
]))
story.append(shot_table2)

cap_data2 = [
    [Paragraph("Gbr 3: Form Review Dokumen WhatsApp (Keterangan Pengirim, Keyakinan OCR 98%, Flags)", caption_style),
     Paragraph("Gbr 4: Persetujuan Berhasil (Status berpindah ke SIAP POSTING, metrik diperbarui)", caption_style)]
]
cap_table2 = Table(cap_data2, colWidths=[270, 270])
cap_table2.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
story.append(cap_table2)
story.append(Spacer(1, 6))

# Posting & Invarian Finansial
story.append(Paragraph("Pencatatan Akuntansi & Rekonsiliasi Jurnal (GL Audit):", h2_style))
story.append(Paragraph(
    "Dokumen <b>DOC-WA-27300435</b> diposting langsung melalui aksi pengguna di web review. Sistem secara deterministik "
    "menghasilkan transaksi tagihan vendor dan jurnal berimbang ganda:",
    body_style
))
story.append(Spacer(1, 3))

fin_data = [
    [Paragraph("Entitas / Atribut", table_header_style), Paragraph("Nilai Audit Riil", table_header_style), Paragraph("Status Invarian", table_header_style)],
    [Paragraph("Kode Transaksi", table_cell_style), Paragraph("TRX-2026-000028 (VENDOR_BILL)", table_cell_style), Paragraph("VALID (Sesuai skema urutan)", table_cell_style)],
    [Paragraph("Nomor Jurnal", table_cell_style), Paragraph("JE-2026-000027", table_cell_style), Paragraph("VALID (Immutable Double-Entry)", table_cell_style)],
    [Paragraph("Total Debet & Kredit", table_cell_style), Paragraph("Debet: Rp 3.750.000,00 | Kredit: Rp 3.750.000,00", table_cell_style), Paragraph("<font color='#16a34a'><b>SEIMBANG (Debet = Kredit)</b></font>", table_cell_style)],
    [Paragraph("Baris Debet", table_cell_style), Paragraph("Akun 5101 (Harga Pokok Proyek) &bull; Proyek: PRJ-2026-001", table_cell_style), Paragraph("VALID (Teratribusi ke Proyek)", table_cell_style)],
    [Paragraph("Baris Kredit", table_cell_style), Paragraph("Akun 2101 (Utang Usaha) &bull; Vendor: PT Nusa Engineering", table_cell_style), Paragraph("VALID (Teratribusi ke Vendor)", table_cell_style)],
    [Paragraph("Pembersihan (Cleanup)", table_cell_style), Paragraph("TRX-2026-000029 & JE-2026-000028 (Reversal Otomatis)", table_cell_style), Paragraph("<font color='#16a34a'><b>DAMPAK FINANSIAL BERSIH NOL</b></font>", table_cell_style)]
]
fin_table = Table(fin_data, colWidths=[120, 270, 150])
fin_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f172a')),
    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(fin_table)
story.append(Spacer(1, 6))

# Temuan Baru WF-019
story.append(Paragraph("5. Temuan Audit Baru: WF-019 (Duplikasi Prefix API)", h1_style))

img3_path = os.path.abspath('docs/audits/E2E-TEST-20260920-1505/screenshots/03_whatsapp_inbox_page.png')
wf_data = []
if os.path.exists(img3_path):
    wf_data.append([
        Image(img3_path, width=200, height=105),
        Paragraph(
            "<b>Temuan WF-019 (Severity: MEDIUM):</b><br/>"
            "Modul frontend <code>src/api/inbox.ts</code> memanggil <code>apiClient</code> dengan string URL berawalan <code>/api/v1/inbox/...</code>. "
            "Karena <code>apiClient.baseURL</code> sudah secara default bernilai <code>/api/v1</code>, Axios menggabungkan URL menjadi "
            "<code>/api/v1/api/v1/inbox/messages</code> yang mengembalikan respons <b>HTTP 404 Not Found</b>.<br/><br/>"
            "<b>Dampak UX:</b> Halaman <code>WhatsAppInboxPage.tsx</code> menelan error tersebut tanpa menampilkan banner atau tombol coba lagi, "
            "sehingga menampilkan pesan keliru: <i>'Tidak ada pesan WhatsApp - Belum ada bukti transaksi yang diterima untuk filter status ini'</i>.",
            body_style
        )
    ])
    wf_table = Table(wf_data, colWidths=[210, 330])
    wf_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#fca5a5')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fff1f2')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(wf_table)
story.append(Spacer(1, 6))

# Ketahanan & Idempotensi
story.append(Paragraph("6. Ketahanan Sistem, Idempotensi & Batas Keamanan", h1_style))
story.append(Paragraph(
    "&bull; <b>Idempotensi Penyerapan:</b> Pengiriman ulang pesan yang sama mengembalikan ID yang sama persis tanpa duplikasi rekaman.<br/>"
    "&bull; <b>Deteksi Hash Duplikat (Feature 005):</b> Berkas dengan hash SHA-256 yang identik tidak diduplikasi di basis data.<br/>"
    "&bull; <b>Penolakan Pengirim Tak Dikenal:</b> Permintaan dari nomor seluler yang belum terpetakan ditolak secara aman dengan HTTP 403 Forbidden.<br/>"
    "&bull; <b>Isolasi Webhook:</b> Permintaan webhook tanpa tanda tangan kriptografis HMAC-SHA256 ditolak dengan HTTP 401 Unauthorized.<br/>"
    "&bull; <b>Ketahanan Worker Downtime:</b> Berkas dan keterangan tersimpan aman saat worker offline, dan diproses otomatis saat worker online.",
    body_style
))

doc.build(story)
print("Built PDF report at:", pdf_path)
shutil.copyfile(pdf_path, dogfood_pdf_path)
print("Copied to dogfood output:", dogfood_pdf_path)
