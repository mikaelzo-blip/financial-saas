import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_Active_Workflow_Audit_Report.pdf')
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
    fontSize=18,
    leading=22,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=4
)
subtitle_style = ParagraphStyle(
    'DocSub',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    leading=13,
    textColor=colors.HexColor('#475569'),
    spaceAfter=8
)
h1_style = ParagraphStyle(
    'H1',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=12,
    leading=16,
    textColor=colors.HexColor('#1e293b'),
    spaceBefore=10,
    spaceAfter=5
)
h2_style = ParagraphStyle(
    'H2',
    parent=styles['Heading3'],
    fontName='Helvetica-Bold',
    fontSize=10,
    leading=14,
    textColor=colors.HexColor('#334155'),
    spaceBefore=6,
    spaceAfter=3
)
body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8.5,
    leading=12,
    textColor=colors.HexColor('#334155'),
    spaceAfter=4
)
rant_style = ParagraphStyle(
    'Rant',
    parent=styles['Normal'],
    fontName='Helvetica-Oblique',
    fontSize=8.5,
    leading=12,
    textColor=colors.HexColor('#991b1b'),
    backColor=colors.HexColor('#fef2f2'),
    borderColor=colors.HexColor('#fca5a5'),
    borderWidth=0.8,
    borderPadding=6,
    spaceBefore=4,
    spaceAfter=6
)
table_cell_style = ParagraphStyle(
    'TableCell',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=8,
    leading=11,
    textColor=colors.HexColor('#1e293b')
)
table_cell_bold = ParagraphStyle(
    'TableCellBold',
    parent=table_cell_style,
    fontName='Helvetica-Bold'
)

story = []

# Title & Metadata
story.append(Paragraph('Financial SaaS Active Workflow Audit Report', title_style))
story.append(Paragraph('Laporan Pengujian Lapangan End-to-End Workflow & UX (Browser-First)', subtitle_style))
story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cbd5e1'), spaceBefore=0, spaceAfter=8))

# Environment Table
env_data = [
    [Paragraph('<b>Parameter</b>', table_cell_bold), Paragraph('<b>Nilai / Konfigurasi</b>', table_cell_bold)],
    [Paragraph('Target URL', table_cell_style), Paragraph('http://127.0.0.1:5173 (Backend: http://127.0.0.1:8000)', table_cell_style)],
    [Paragraph('Git SHA & Branch', table_cell_style), Paragraph('26ab5affee58 (hermes/document-review-simplification-v2)', table_cell_style)],
    [Paragraph('Tipe Environment', table_cell_style), Paragraph('Local Development (Docker PostgreSQL financial-saas-postgres)', table_cell_style)],
    [Paragraph('Organisasi / Tenant', table_cell_style), Paragraph('PT Kontraktor Utama Indonesia (ID: 9670673b-c0fd-4ebe-87e4-a646358084ea)', table_cell_style)],
    [Paragraph('Run ID', table_cell_style), Paragraph('E2E-TEST-20260920-1139', table_cell_style)],
    [Paragraph('Persona Audit', table_cell_style), Paragraph('Pak Bambang (54 thn, Owner/Direktur Kontraktor Sipil, Non-akuntan)', table_cell_style)],
]
env_table = Table(env_data, colWidths=[130, 410])
env_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(env_table)
story.append(Spacer(1, 8))

# Journey & Results Summary
story.append(Paragraph('1. Ringkasan Hasil Eksekusi Journey', h1_style))
journey_text = (
    '<b>Primary Journey Teruji:</b> Dokumen Fisik (PDF) &rarr; Intake Web &rarr; Worker OCR &rarr; '
    'Review Form &rarr; Koreksi &rarr; Persetujuan &rarr; Transaksi &rarr; Posting Jurnal &rarr; '
    'Laporan Buku Besar & Neraca &rarr; Pembatalan Resmi (Reversal).'
)
story.append(Paragraph(journey_text, body_style))

res_data = [
    [Paragraph('<b>Dimensi Evaluasi</b>', table_cell_bold), Paragraph('<b>Status</b>', table_cell_bold), Paragraph('<b>Keterangan Eksekusi Riil</b>', table_cell_bold)],
    [Paragraph('Fungsional (Functional)', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Alur intake, ekstraksi OCR, koreksi, persetujuan, posting, dan reversal berhasil melalui UI.', table_cell_style)],
    [Paragraph('Integritas Akuntansi', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Debit == Kredit persis Rp 5.550.000. Reversal membalik akun secara kompensasi sempurna.', table_cell_style)],
    [Paragraph('Proteksi Duplikasi', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('SHA-256 hash mencegah upload ganda dokumen identik (HTTP 409 Conflict + modal peringatan).', table_cell_style)],
    [Paragraph('Alur Kerja (Workflow)', table_cell_style), Paragraph('<font color="#d97706"><b>FRICTION</b></font>', table_cell_style), Paragraph('Flag AMOUNT_MISMATCH mengunci form jika nominal tidak diubah manual.', table_cell_style)],
    [Paragraph('Pengalaman Pengguna (UX)', table_cell_style), Paragraph('<font color="#d97706"><b>FRICTION</b></font>', table_cell_style), Paragraph('String backend bocor ke UI; tidak ada drilldown dari laporan Buku Besar ke transaksi asal.', table_cell_style)],
    [Paragraph('Pembersihan (Cleanup)', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Dibersihkan via Reverse resmi aplikasi (TRX-2026-000012). Tanpa DELETE paksa di database.', table_cell_style)],
]
res_table = Table(res_data, colWidths=[120, 70, 350])
res_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(res_table)
story.append(Spacer(1, 8))

# Accounting Verification
story.append(Paragraph('2. Verifikasi Integritas Akuntansi & Jejak Audit', h1_style))
acct_data = [
    [Paragraph('<b>Aspek Verifikasi</b>', table_cell_bold), Paragraph('<b>Bukti Transaksi / Jurnal</b>', table_cell_bold), Paragraph('<b>Status Invarian</b>', table_cell_bold)],
    [Paragraph('Jurnal Tagihan Vendor', table_cell_style), Paragraph('JE-2026-000011 (Dr 5101 HPP Rp 5.550.000 / Cr 2101 Utang Rp 5.550.000)', table_cell_style), Paragraph('Debet = Kredit (Balanced)', table_cell_style)],
    [Paragraph('Jurnal Pembalik (Reversal)', table_cell_style), Paragraph('JE-2026-000012 (Dr 2101 Utang Rp 5.550.000 / Cr 5101 HPP Rp 5.550.000)', table_cell_style), Paragraph('Kompensasi Penuh (Net 0)', table_cell_style)],
    [Paragraph('Linkage Reversal', table_cell_style), Paragraph('JE-2026-000011 ditandai is_reversed = true & reversal_entry_id terisi', table_cell_style), Paragraph('Audit Trail Utuh', table_cell_style)],
    [Paragraph('Total Keseimbangan Neraca', table_cell_style), Paragraph('Mutasi Debet Rp 295.130.988,86 == Kredit Rp 295.130.988,86 (unbalanced = 0)', table_cell_style), Paragraph('Organisasi Seimbang', table_cell_style)],
    [Paragraph('Dampak Buku Besar', table_cell_style), Paragraph('Akun 2101 Utang Usaha merefleksikan kredit Rp 5.550.000 per 2026-09-20', table_cell_style), Paragraph('Terposting di Buku Besar', table_cell_style)],
]
acct_table = Table(acct_data, colWidths=[140, 270, 130])
acct_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(acct_table)

story.append(PageBreak())

# Findings Section
story.append(Paragraph('3. Daftar Temuan Masalah & Analisis UX', h1_style))

f1 = (
    '<b>WF-001 (High) &mdash; Flag AMOUNT_MISMATCH Mengunci Persetujuan jika Nominal Tidak Di-retype</b><br/>'
    '<i>Lokasi:</i> /documents/:id/review &bull; <i>Kategori:</i> Workflow / Form Gating<br/>'
    '<b>Gejala:</b> Faktur dengan PPN (DPP 5 jt + PPN 550 rb = Total 5,55 jt) otomatis memicu flag AMOUNT_MISMATCH. '
    'Saat pengguna memeriksa form, nominal sudah terisi benar (Rp 5.550.000). Namun saat menekan tombol Setujui, sistem menolak '
    'dengan pesan: <i>Dokumen masih memiliki review yang belum selesai: AMOUNT_MISMATCH</i>. '
    'Penyebabnya adalah frontend hanya mengirim field yang berbeda dari nilai awal (isDirty). Karena nominal tidak diubah, '
    'backend tidak menerima field amount sehingga flag tidak dihapus. Pengguna terpaksa mengetik ulang nilai nominal.<br/>'
    '<b>Rekomendasi:</b> Otomatis sertakan field amount yang terkonfirmasi saat klik Setujui, atau sediakan tombol Konfirmasi Nominal.'
)
story.append(Paragraph(f1, body_style))
story.append(Spacer(1, 4))

f2 = (
    '<b>WF-002 (High) &mdash; Pesan Galat Backend Bahasa Inggris Mentah Bocor ke UI</b><br/>'
    '<i>Lokasi:</i> /documents/:id/review &bull; <i>Kategori:</i> Terminology / Localization<br/>'
    '<b>Gejala:</b> Jika nominal diisi tidak valid (misal 0), muncul banner merah dengan pesan teknis backend Pydantic: '
    '<i>Corrected extraction data cannot be rematched</i>. Pesan ini tidak informatif bagi pemilik proyek / staf administrasi.<br/>'
    '<b>Rekomendasi:</b> Lokalisasi pesan galat menjadi bahasa Indonesia ramah pengguna: <i>Nominal dokumen tidak valid atau harus lebih besar dari Rp 0</i>.'
)
story.append(Paragraph(f2, body_style))
story.append(Spacer(1, 4))

f3 = (
    '<b>WF-003 (Medium) &mdash; Ketiadaan Drilldown dari Laporan Buku Besar ke Transaksi Sumber</b><br/>'
    '<i>Lokasi:</i> /reports/general-ledger &bull; <i>Kategori:</i> Traceability / Navigation<br/>'
    '<b>Gejala:</b> Pada tabel Buku Besar, kode jurnal JE-2026-000011 ditampilkan sebagai teks polos tanpa hyperlink. '
    'Pengguna yang sedang mereview audit tidak dapat mengklik untuk membuka rincian transaksi atau bukti fisik nota aslinya.<br/>'
    '<b>Rekomendasi:</b> Ubah kode jurnal menjadi link interaktif menuju /transactions/:id.'
)
story.append(Paragraph(f3, body_style))
story.append(Spacer(1, 4))

f4 = (
    '<b>WF-004 (Medium) &mdash; Dua Tahap Pemrosesan (Setujui &rarr; Posting) Membingungkan Non-Akuntan</b><br/>'
    '<i>Lokasi:</i> /documents &bull; <i>Kategori:</i> Workflow Efficiency<br/>'
    '<b>Gejala:</b> Tombol di form review bertuliskan <i>Setujui untuk Diposting</i>. Setelah diklik, pengguna dialihkan ke tabel '
    'dan dokumen berstatus <i>Siap Posting</i>. Pengguna non-akuntan mengira transaksi sudah selesai dibukukan, padahal harus menekan '
    'tombol <i>Posting</i> sekali lagi di baris tabel.<br/>'
    '<b>Rekomendasi:</b> Sediakan opsi tombol utama <i>Setujui & Posting Langsung</i> jika seluruh field valid.'
)
story.append(Paragraph(f4, body_style))
story.append(Spacer(1, 8))

# Adversarial UX Persona
story.append(Paragraph('4. Tinjauan Adversarial UX (Persona: Owner Kontraktor)', h1_style))
story.append(Paragraph('Roleplay pengujian dari sudut pandang Pak Bambang (54 thn, kontraktor sipil praktis):', body_style))
rant_text = (
    '<i>"Saya cuma mau upload nota dari PT Nusa terus sistem catat utang sama biayanya! Kenapa pas saya klik Setujui, '
    'malah muncul tulisan merah bahasa Inggris AMOUNT_MISMATCH?! Angkanya udah bener 5,55 juta! Kenapa saya harus '
    'otak-atik ketik ulang nominalnya baru bisa lewat?! Terus setelah disetujui, saya kira udah beres, ternyata statusnya cuma '
    'Siap Posting dan saya harus cari tombol Posting lagi di tabel. Di laporan Buku Besar kodenya juga gak bisa diklik."</i>'
)
story.append(Paragraph(rant_text, rant_style))

story.append(Paragraph('<b>Hasil Pragmatism Filter:</b>', h2_style))
triage_data = [
    [Paragraph('<b>Klasifikasi</b>', table_cell_bold), Paragraph('<b>Temuan Masalah Lapangan</b>', table_cell_bold), Paragraph('<b>Tindakan Solutif</b>', table_cell_bold)],
    [Paragraph('<font color="#dc2626"><b>RED</b></font>', table_cell_style), Paragraph('Form terkunci flag AMOUNT_MISMATCH pada invoice PPN.', table_cell_style), Paragraph('Kirim payload konfirmasi amount otomatis saat approve.', table_cell_style)],
    [Paragraph('<font color="#dc2626"><b>RED</b></font>', table_cell_style), Paragraph('String teknis bahasa Inggris bocor di validasi form.', table_cell_style), Paragraph('Ganti kamus error menjadi bahasa Indonesia operasional.', table_cell_style)],
    [Paragraph('<font color="#d97706"><b>YELLOW</b></font>', table_cell_style), Paragraph('Tabel Buku Besar tidak memiliki drilldown klik transaksi.', table_cell_style), Paragraph('Jadikan nomor jurnal hyperlink ke detail transaksi.', table_cell_style)],
    [Paragraph('<font color="#16a34a"><b>GREEN</b></font>', table_cell_style), Paragraph('Alur Setujui & Posting dapat digabung menjadi 1 langkah.', table_cell_style), Paragraph('Beri tombol Setujui & Posting Langsung.', table_cell_style)],
    [Paragraph('<font color="#64748b"><b>WHITE</b></font>', table_cell_style), Paragraph('Keluhan harus mengetik alasan pembatalan (Reversal).', table_cell_style), Paragraph('Diabaikan; wajib dipertahankan demi audit trail akuntansi.', table_cell_style)],
]
triage_table = Table(triage_data, colWidths=[60, 240, 240])
triage_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 3),
    ('BOTTOMPADDING', (0,0), (-1,-1), 3),
]))
story.append(triage_table)

story.append(PageBreak())

# Visual Evidence Section
story.append(Paragraph('5. Bukti Visual Eksekusi Browser Nyata', h1_style))
story.append(Paragraph('Berikut adalah tangkapan layar verifikasi langsung dari browser engine Financial SaaS:', body_style))
story.append(Spacer(1, 4))

screenshots = [
    ('dogfood-output/screenshots/03-review-page.png', 'Gambar 1: Form Review Dokumen DOC-2026-000017 (Hasil ekstraksi OCR faktur vendor Rp 5.550.000)'),
    ('dogfood-output/screenshots/06-posted-state.png', 'Gambar 2: Status SUDAH DIPOSTING pada Dokumen Bukti & Terbitnya Transaksi TRX-2026-000011'),
    ('dogfood-output/screenshots/08-general-ledger-report.png', 'Gambar 3: Laporan Buku Besar Akun 2101 Utang Usaha mencatat JE-2026-000011 Rp 5.550.000'),
    ('dogfood-output/screenshots/09-reversal-modal.png', 'Gambar 4: Dialog Modal Pembatalan / Reversal Transaksi Kompensasi Berbasis Audit Trail'),
    ('dogfood-output/screenshots/11-duplicate-prevention-modal.png', 'Gambar 5: Pencegahan Duplikasi Dokumen Identik Berbasis Cryptographic Hash SHA-256'),
    ('dogfood-output/screenshots/14-trial-balance-balanced.png', 'Gambar 6: Laporan Neraca Saldo Menunjukkan Keseimbangan Total Debet = Kredit Rp 295.130.988,86'),
]

for img_path, caption in screenshots:
    if os.path.exists(img_path):
        img = Image(img_path, width=470, height=205)
        story.append(KeepTogether([
            img,
            Paragraph(caption, ParagraphStyle('Cap', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=7.5, textColor=colors.HexColor('#475569'), alignment=1, spaceBefore=2, spaceAfter=8))
        ]))

doc.build(story)
print('PDF report successfully generated at:', pdf_path)
