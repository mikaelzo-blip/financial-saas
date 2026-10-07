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
output_dir = os.path.abspath('docs/audits/E2E-TEST-20260920-1301')
os.makedirs(output_dir, exist_ok=True)
pdf_path = os.path.join(output_dir, 'Financial_SaaS_J3_AP_Vendor_Payment_Audit_Report.pdf')
dogfood_pdf_path = os.path.abspath('dogfood-output/Financial_SaaS_J3_AP_Vendor_Payment_Audit_Report.pdf')

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
    fontSize=17,
    leading=21,
    textColor=colors.HexColor('#0f172a'),
    spaceAfter=3
)

subtitle_style = ParagraphStyle(
    'DocSub',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    leading=13,
    textColor=colors.HexColor('#475569'),
    spaceAfter=6
)

h1_style = ParagraphStyle(
    'H1',
    parent=styles['Heading2'],
    fontName='Helvetica-Bold',
    fontSize=11.5,
    leading=15,
    textColor=colors.HexColor('#1e293b'),
    spaceBefore=9,
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
    fontSize=8.5,
    leading=12,
    textColor=colors.HexColor('#334155'),
    spaceAfter=4
)

code_style = ParagraphStyle(
    'CodeBlock',
    parent=styles['Normal'],
    fontName='Courier',
    fontSize=7.5,
    leading=10.5,
    textColor=colors.HexColor('#0f172a'),
    backColor=colors.HexColor('#f8fafc'),
    borderColor=colors.HexColor('#e2e8f0'),
    borderWidth=0.6,
    borderPadding=5,
    spaceBefore=3,
    spaceAfter=5
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

# Title & Header
story.append(Paragraph('Financial SaaS Workflow Audit Report &mdash; J3 AP / Vendor Payment', title_style))
story.append(Paragraph('Laporan Audit Lapangan End-to-End Browser & Verifikasi Integritas Akuntansi', subtitle_style))
story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cbd5e1'), spaceBefore=0, spaceAfter=6))

# Environment & Context Table
env_data = [
    [Paragraph('<b>Parameter</b>', table_cell_bold), Paragraph('<b>Nilai / Konfigurasi</b>', table_cell_bold)],
    [Paragraph('Journey Audit', table_cell_style), Paragraph('<b>J3 &mdash; AP / Vendor Payment</b> (Tagihan Vendor &rarr; Pembayaran &rarr; Pelunasan Utang)', table_cell_style)],
    [Paragraph('Target URL', table_cell_style), Paragraph('http://localhost:5173 (Frontend React/Vite) &bull; http://localhost:8000 (Backend FastAPI)', table_cell_style)],
    [Paragraph('Git SHA & Branch', table_cell_style), Paragraph('<b>26ab5af</b> (hermes/document-review-simplification-v2)', table_cell_style)],
    [Paragraph('Tenant / Organisasi', table_cell_style), Paragraph('PT Kontraktor Utama Indonesia (ID: 9670673b-c0fd-4ebe-87e4-a646358084ea)', table_cell_style)],
    [Paragraph('Run ID & Tanggal', table_cell_style), Paragraph('<b>E2E-TEST-20260920-1301</b> &bull; 20 September 2026', table_cell_style)],
    [Paragraph('Status Akhir', table_cell_style), Paragraph('<font color="#d97706"><b>PASS_WITH_FRICTION</b></font> (Akuntansi 100% Valid; 1 Temuan UX WF-005)', table_cell_style)],
]
env_table = Table(env_data, colWidths=[120, 420])
env_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(env_table)
story.append(Spacer(1, 6))

# Section 1: Ringkasan Hasil Eksekusi Journey
story.append(Paragraph('1. Ringkasan Eksekusi Alur J3 (Browser Journey)', h1_style))
journey_desc = (
    'Pengujian alur kerja J3 dijalankan menggunakan browser interaktif riil (Chrome via DevTools Protocol) '
    'dengan data transaksi sintetis ber-prefix <code>E2E-TEST-</code>. Seluruh tahap dilakukan melalui antarmuka web, '
    'mulai dari penginputan tagihan kredit, posting jurnal, alokasi pengeluaran kas/bank, hingga pengujian pembatalan kompensasi.'
)
story.append(Paragraph(journey_desc, body_style))

res_data = [
    [Paragraph('<b>Tahap Eksekusi</b>', table_cell_bold), Paragraph('<b>Status</b>', table_cell_bold), Paragraph('<b>Hasil & Bukti Lapangan</b>', table_cell_bold)],
    [Paragraph('1. Input Tagihan Vendor', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Input via <code>/transactions/new</code> (Tagihan Vendor, Rp 7.500.000, PT Nusa Engineering). Terbit <b>TRX-2026-000013</b> status SIAP POSTING.', table_cell_style)],
    [Paragraph('2. Posting Tagihan ke GL', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Klik <i>Posting ke Buku Besar</i> berhasil. Terbit <b>JE-2026-000013</b> (Dr 5101 HPP / Cr 2101 Utang Rp 7,5 jt). Status: SUDAH DIPOSTING.', table_cell_style)],
    [Paragraph('3. Muncul di Daftar Utang', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Halaman <code>/payables</code> otomatis menampilkan tagihan <code>E2E-TEST-20260920-1301-BILL</code> dengan sisa utang Rp 7.500.000.', table_cell_style)],
    [Paragraph('4. Alokasi Pembayaran', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Modal <i>Bayar Tagihan Vendor</i> terbuka via tombol aksi baris. Rekening Bank Mandiri (1101) dipilih, nominal pre-filled otomatis.', table_cell_style)],
    [Paragraph('5. Posting Pembayaran', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Terbit <b>TRX-2026-000014</b> & <b>JE-2026-000014</b> (Dr 2101 Utang / Cr 1101 Bank Rp 7,5 jt). Sisa utang tagihan menjadi <b>Rp 0 (LUNAS)</b>.', table_cell_style)],
    [Paragraph('6. Proteksi Duplikasi & Overpay', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('Tagihan lunas tidak lagi menampilkan tombol bayar di UI. Percobaan API bayar ulang & overpayment ditolak <b>HTTP 422 INVARIANT_VIOLATION</b>.', table_cell_style)],
    [Paragraph('7. Cleanup via Reversal', table_cell_style), Paragraph('<font color="#16a34a"><b>PASS</b></font>', table_cell_style), Paragraph('TRX pembayaran di-reverse (<b>TRX-2026-000015</b>), disusul tagihan vendor (<b>TRX-2026-000016</b>). Net effect saldo seluruh akun = <b>Rp 0,00</b>.', table_cell_style)],
]
res_table = Table(res_data, colWidths=[110, 55, 375])
res_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(res_table)
story.append(Spacer(1, 6))

# Section 2: Verifikasi Integritas Akuntansi
story.append(Paragraph('2. Verifikasi Integritas Akuntansi & Double-Entry', h1_style))
acct_intro = (
    'Setiap mutasi keuangan diverifikasi secara langsung pada level PostgreSQL database untuk membuktikan '
    'kepatuhan terhadap prinsip akuntansi: (1) Debet == Kredit seimbang, (2) Pembayaran utang tidak menduplikasi beban, '
    '(3) Pembatalan menggunakan jurnal kompensasi penuh.'
)
story.append(Paragraph(acct_intro, body_style))

acct_data = [
    [Paragraph('<b>Transaksi & Nomor Jurnal</b>', table_cell_bold), Paragraph('<b>Klasifikasi / Akun Terkena Dampak</b>', table_cell_bold), Paragraph('<b>Debet (Rp)</b>', table_cell_bold), Paragraph('<b>Kredit (Rp)</b>', table_cell_bold), Paragraph('<b>Status Invarian</b>', table_cell_bold)],
    [Paragraph('<b>TRX-2026-000013</b><br/>JE-2026-000013<br/><i>(Vendor Bill)</i>', table_cell_style), Paragraph('5101 Harga Pokok Proyek<br/>2101 Utang Usaha (Vendor Liability)', table_cell_style), Paragraph('7.500.000<br/>0', table_cell_style), Paragraph('0<br/>7.500.000', table_cell_style), Paragraph('<font color="#16a34a"><b>SEIMBANG</b></font><br/>Utang diakui', table_cell_style)],
    [Paragraph('<b>TRX-2026-000014</b><br/>JE-2026-000014<br/><i>(Pay Vendor Bill)</i>', table_cell_style), Paragraph('2101 Utang Usaha (Pelunasan)<br/>1101 Kas dan Bank (Bank Mandiri)', table_cell_style), Paragraph('7.500.000<br/>0', table_cell_style), Paragraph('0<br/>7.500.000', table_cell_style), Paragraph('<font color="#16a34a"><b>SEIMBANG</b></font><br/>Tanpa beban ganda', table_cell_style)],
    [Paragraph('<b>TRX-2026-000015</b><br/>JE-2026-000015<br/><i>(Reversal Payment)</i>', table_cell_style), Paragraph('1101 Kas dan Bank (Pengembalian)<br/>2101 Utang Usaha (Re-open liability)', table_cell_style), Paragraph('7.500.000<br/>0', table_cell_style), Paragraph('0<br/>7.500.000', table_cell_style), Paragraph('<font color="#16a34a"><b>SEIMBANG</b></font><br/>Kompensasi kas', table_cell_style)],
    [Paragraph('<b>TRX-2026-000016</b><br/>JE-2026-000016<br/><i>(Reversal Bill)</i>', table_cell_style), Paragraph('2101 Utang Usaha (Penghapusan utang)<br/>5101 Harga Pokok Proyek (Batal beban)', table_cell_style), Paragraph('7.500.000<br/>0', table_cell_style), Paragraph('0<br/>7.500.000', table_cell_style), Paragraph('<font color="#16a34a"><b>SEIMBANG</b></font><br/>Kompensasi HPP', table_cell_style)],
    [Paragraph('<b>Net Effect Akun:</b>', table_cell_bold), Paragraph('<b>1101 Kas/Bank: Rp 0,00 &bull; 2101 Utang: Rp 0,00 &bull; 5101 HPP: Rp 0,00</b>', table_cell_bold), Paragraph('-', table_cell_style), Paragraph('-', table_cell_style), Paragraph('<font color="#16a34a"><b>NET ZERO (100%)</b></font>', table_cell_bold)],
]
acct_table = Table(acct_data, colWidths=[120, 190, 75, 75, 80])
acct_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f8fafc')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(acct_table)

story.append(PageBreak())

# Section 3: Mandatory Backend Trace
story.append(Paragraph('3. Rantai Penelusuran Backend (Mandatory Trace)', h1_style))
trace_text = (
    '<b>Jalur Eksekusi State-Changing Pelunasan Utang (JOURNEY-SCOPED):</b><br/>'
    '<code>Klik Simpan Pengeluaran &rarr; VendorPaymentAllocationModal &rarr; payablesApi.allocatePayment &rarr; '
    'POST /api/v1/vendor-payments &rarr; Auth JWT (Admin/Manager) &rarr; VendorAPService.get_bill (validasi outstanding) &rarr; '
    'run_in_clean_transaction: [TransactionService.create_transaction(PAY_VENDOR_BILL) &rarr; '
    'AccountingEngine.post_transaction (PostingRules: Dr 2101 / Cr 1101) &rarr; '
    'VendorAPService.allocate_vendor_payment (update bill.status = PAID) &rarr; '
    'MoneyMovementService.synchronize_payment_money_movement] &rarr; HTTP 201 Response &rarr; UI Refresh</code>'
)
story.append(Paragraph(trace_text, code_style))
story.append(Spacer(1, 4))

# Section 4: Temuan Lapangan & Evaluasi UX
story.append(Paragraph('4. Temuan Lapangan & Analisis Pengalaman Pengguna (UX)', h1_style))

finding_wf005 = (
    '<b>WF-005 (Medium) &mdash; Vendor/Pelanggan & Akun Kas/Bank Tidak Ditampilkan di Detail Transaksi Pembayaran</b><br/>'
    '<i>Lokasi:</i> <code>/transactions/:id</code> &bull; <i>Kategori:</i> Traceability / Information Display<br/>'
    '<b>Gejala:</b> Pada halaman detail transaksi <code>TRX-2026-000014</code> (tipe PAY_VENDOR_BILL) maupun transaksi pembaliknya '
    '<code>TRX-2026-000015</code>, field <i>Vendor / Pelanggan</i> dan <i>Akun Kas / Bank</i> hanya menampilkan tanda strip (<code>-</code>). '
    'Padahal di database PostgreSQL, foreign key <code>counterparty_id</code> (PT Nusa Engineering) dan <code>payment_account_id</code> '
    '(Bank Mandiri) tersimpan dengan lengkap dan valid.<br/>'
    '<b>Dampak Lapangan:</b> Staf keuangan atau auditor yang membuka riwayat transaksi tidak dapat langsung mengetahui dari rekening mana '
    'pembayaran tersebut keluar atau kepada siapa pembayaran ditujukan tanpa memeriksa jurnal debet/kredit.<br/>'
    '<b>Rekomendasi:</b> Perbaiki komponen <code>TransactionDetailPage.tsx</code> agar memetakan <code>counterparty</code> dan '
    '<code>payment_account</code> pada tipe transaksi <code>PAY_VENDOR_BILL</code>.'
)
story.append(Paragraph(finding_wf005, body_style))
story.append(Spacer(1, 4))

story.append(Paragraph('<b>Evaluasi Matriks Kualitas Alur (Persona: Staf Finance Lapangan):</b>', h2_style))
ux_eval_data = [
    [Paragraph('<b>Parameter Evaluasi</b>', table_cell_bold), Paragraph('<b>Pengukuran Nyata</b>', table_cell_bold), Paragraph('<b>Catatan Pengalaman Pengguna</b>', table_cell_bold)],
    [Paragraph('Jumlah Klik (Input Bill)', table_cell_style), Paragraph('4 klik, 5 input field', table_cell_style), Paragraph('Alur terarah dan tidak membingungkan; dropdown proyek & vendor reaktif.', table_cell_style)],
    [Paragraph('Jumlah Klik (Bayar Tagihan)', table_cell_style), Paragraph('3 klik, 2 input field', table_cell_style), Paragraph('Sangat efisien: tombol aksi langsung di baris tabel, nominal otomatis terisi sisa utang.', table_cell_style)],
    [Paragraph('Pencegahan Salah Bayar', table_cell_style), Paragraph('2 Lapis Proteksi', table_cell_style), Paragraph('UI mematikan tombol bayar saat lunas; backend memblokir overpayment via HTTP 422.', table_cell_style)],
    [Paragraph('Transparansi Kas & Utang', table_cell_style), Paragraph('Tinggi di tabel, Sedang di detail', table_cell_style), Paragraph('Tabel utang sangat jelas; namun halaman detail transaksi pembayaran memiliki bug display WF-005.', table_cell_style)],
]
ux_table = Table(ux_eval_data, colWidths=[130, 100, 310])
ux_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ('TOPPADDING', (0,0), (-1,-1), 2.5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
]))
story.append(ux_table)

story.append(PageBreak())

# Section 5: Bukti Visual Eksekusi Browser Nyata
story.append(Paragraph('5. Bukti Visual Eksekusi Browser Nyata', h1_style))
story.append(Paragraph('Tangkapan layar resolusi penuh yang diambil langsung dari sesi pengujian browser riil Financial SaaS:', body_style))
story.append(Spacer(1, 4))

screenshots = [
    (
        os.path.join(output_dir, 'screenshots/02-vendor-bill-create.png'),
        'Gambar 1: Form Pencatatan Tagihan Vendor Baru (Tagihan Vendor / Kredit Rp 7.500.000 untuk PT Nusa Engineering pada Proyek PRJ-2026-001)'
    ),
    (
        os.path.join(output_dir, 'screenshots/03-vendor-bill-detail.png'),
        'Gambar 2: Detail Transaksi Tagihan Vendor TRX-2026-000013 (Status Terposting di Buku Besar & Siap Dibayarkan)'
    ),
    (
        os.path.join(output_dir, 'screenshots/04-payables-list.png'),
        'Gambar 3: Halaman Utang Usaha (/payables) Menampilkan Tagihan E2E-TEST-20260920-1301-BILL Berstatus LUNAS Pasca Pembayaran'
    ),
    (
        os.path.join(output_dir, 'screenshots/05-payment-modal.png'),
        'Gambar 4: Dialog Modal Pelunasan Utang Vendor (Memilih Akun Pengeluaran Bank Mandiri & Konfirmasi Nominal Pembayaran)'
    ),
    (
        os.path.join(output_dir, 'screenshots/06-payment-trx-detail.png'),
        'Gambar 5: Detail Transaksi Pembayaran Vendor TRX-2026-000014 (Menunjukkan Bug Display WF-005: Vendor & Rekening Bernilai "-")'
    ),
    (
        os.path.join(output_dir, 'screenshots/07-reversal-modal.png'),
        'Gambar 6: Dialog Modal Pembatalan / Reversal Transaksi Pembayaran Sesuai Prinsip Immutability Akuntansi'
    ),
    (
        os.path.join(output_dir, 'screenshots/08-trial-balance.png'),
        'Gambar 7: Laporan Neraca Saldo (/reports/trial-balance) Menunjukkan Keseimbangan Penuh (Debet = Kredit) Pasca Seluruh Reversal'
    ),
]

for img_path, caption in screenshots:
    if os.path.exists(img_path):
        # 500 pt width, proportional height (16:9 ~ 247 pt)
        img = Image(img_path, width=495, height=245)
        story.append(KeepTogether([
            img,
            Paragraph(caption, ParagraphStyle('Cap', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=7.5, textColor=colors.HexColor('#475569'), alignment=1, spaceBefore=2, spaceAfter=10))
        ]))

doc.build(story)
shutil.copyfile(pdf_path, dogfood_pdf_path)
print('PDF report successfully generated at:')
print('  1.', pdf_path)
print('  2.', dogfood_pdf_path)
