
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

out_path = os.path.abspath("dogfood-output/Backend_Trace_Reconciliation_Report.pdf")
os.makedirs("dogfood-output", exist_ok=True)

doc = SimpleDocTemplate(out_path, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

styles = getSampleStyleSheet()

def sty(name, **kw):
    base = styles["Normal"]
    return ParagraphStyle(name, parent=base, **kw)

title_sty  = sty("T", fontSize=16, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f172a"), spaceAfter=4, leading=20)
sub_sty    = sty("S", fontSize=8.5, fontName="Helvetica", textColor=colors.HexColor("#475569"), spaceAfter=6)
h1_sty     = sty("H1", fontSize=12, fontName="Helvetica-Bold", textColor=colors.HexColor("#1e293b"), spaceBefore=12, spaceAfter=4, leading=16)
h2_sty     = sty("H2", fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#334155"), spaceBefore=8, spaceAfter=3, leading=14)
h3_sty     = sty("H3", fontSize=9, fontName="Helvetica-Bold", textColor=colors.HexColor("#475569"), spaceBefore=6, spaceAfter=2)
body_sty   = sty("B", fontSize=8.5, fontName="Helvetica", textColor=colors.HexColor("#334155"), spaceAfter=3, leading=12)
mono_sty   = sty("M", fontSize=7.5, fontName="Courier", textColor=colors.HexColor("#1e293b"), spaceAfter=2, leading=11)
warn_sty   = sty("W", fontSize=8.5, fontName="Helvetica-Oblique", textColor=colors.HexColor("#991b1b"),
                 backColor=colors.HexColor("#fef2f2"), borderColor=colors.HexColor("#fca5a5"),
                 borderWidth=0.5, borderPadding=5, spaceBefore=3, spaceAfter=5, leading=12)
ok_sty     = sty("OK", fontSize=8.5, fontName="Helvetica", textColor=colors.HexColor("#166534"),
                 backColor=colors.HexColor("#f0fdf4"), borderColor=colors.HexColor("#86efac"),
                 borderWidth=0.5, borderPadding=5, spaceBefore=3, spaceAfter=5, leading=12)

tc = ParagraphStyle("TC", parent=styles["Normal"], fontSize=7.5, fontName="Helvetica", textColor=colors.HexColor("#1e293b"), leading=10)
tcb = ParagraphStyle("TCB", parent=tc, fontName="Helvetica-Bold")

def tbl(data, col_widths, header_row=True):
    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]
    if header_row:
        style_cmds += [
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style_cmds))
    return t

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=4, spaceAfter=4)

def P(text, style=body_sty):
    return Paragraph(text, style)

def bullet(text):
    return Paragraph(f"&#8226;&nbsp; {text}", body_sty)

story = []

# ── TITLE ────────────────────────────────────────────────────────────────────
story.append(P("Backend Trace Reconciliation Report", title_sty))
story.append(P("Laporan Rekonsiliasi Jejak Backend — Financial SaaS", sub_sty))
story.append(hr())
story.append(Spacer(1, 4))

# ── AUDIT CONTEXT ─────────────────────────────────────────────────────────────
story.append(P("1. Audit Context", h1_sty))
ctx = [
    [P("<b>Parameter</b>", tcb), P("<b>Nilai</b>", tcb)],
    [P("Repository", tc), P("C:\\Projects\\financial-saas", tc)],
    [P("Branch", tc), P("hermes/document-review-simplification-v2", tc)],
    [P("Git SHA", tc), P("26ab5affee58", tc)],
    [P("Audit Run ID", tc), P("E2E-TEST-20260920-1139", tc)],
    [P("Environment", tc), P("Local Development (Docker PostgreSQL financial-saas-postgres)", tc)],
    [P("Tenant", tc), P("PT Kontraktor Utama Indonesia (9670673b-c0fd-4ebe-87e4-a646358084ea)", tc)],
]
story.append(tbl(ctx, [4*cm, 13*cm]))
story.append(Spacer(1, 8))

# ── MUTATIONS TRACED ──────────────────────────────────────────────────────────
story.append(P("2. Mutations Traced", h1_sty))
mut = [
    [P("<b>#</b>",tcb), P("<b>Mutation</b>",tcb), P("<b>Browser</b>",tcb), P("<b>Backend</b>",tcb), P("<b>Accounting</b>",tcb), P("<b>Status</b>",tcb)],
    [P("1",tc), P("Koreksi Ekstraksi (CORRECT_EXTRACTION)",tc), P("MATCH",tc), P("CONFIRMED",tc), P("Non-mutating",tc), P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>",tc)],
    [P("2",tc), P("Persetujuan Dokumen (APPROVE_CANDIDATE)",tc), P("MATCH",tc), P("CONFIRMED",tc), P("Non-mutating",tc), P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>",tc)],
    [P("3",tc), P("Posting Transaksi (POST_ACCOUNTING)",tc), P("MATCH",tc), P("CONFIRMED",tc), P("Dr 5101 / Cr 2101 Rp 5.550.000",tc), P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>",tc)],
    [P("4",tc), P("Pembatalan / Reversal (REVERSAL)",tc), P("MATCH",tc), P("CONFIRMED",tc), P("Dr 2101 / Cr 5101 Rp 5.550.000",tc), P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>",tc)],
    [P("5",tc), P("Proteksi Duplikasi (DUPLICATE_GUARD)",tc), P("MATCH",tc), P("CONFIRMED",tc), P("Non-mutating (HTTP 409)",tc), P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>",tc)],
]
story.append(tbl(mut, [0.6*cm, 5*cm, 2*cm, 2.2*cm, 4.2*cm, 3*cm]))
story.append(Spacer(1, 8))

# ── ACCOUNTING VERIFICATION ───────────────────────────────────────────────────
story.append(P("3. Accounting Verification", h1_sty))
acc = [
    [P("<b>Aspek</b>",tcb), P("<b>Bukti</b>",tcb), P("<b>Status</b>",tcb)],
    [P("Jurnal Tagihan Vendor",tc), P("JE-2026-000011: Dr 5101 HPP Rp 5.550.000 / Cr 2101 Utang Rp 5.550.000",tc), P("<font color='#16a34a'>Balanced</font>",tc)],
    [P("Jurnal Pembalik",tc), P("JE-2026-000012: Dr 2101 Utang Rp 5.550.000 / Cr 5101 HPP Rp 5.550.000",tc), P("<font color='#16a34a'>Kompensasi Penuh</font>",tc)],
    [P("Linkage Reversal",tc), P("JE-2026-000011.is_reversed=true, reversal_entry_id=JE-2026-000012.id", tc), P("<font color='#16a34a'>Audit Trail Utuh</font>",tc)],
    [P("Neraca Saldo",tc), P("Total Debet Rp 295.130.988,86 == Total Kredit Rp 295.130.988,86 (unbalanced=0)",tc), P("<font color='#16a34a'>Seimbang</font>",tc)],
    [P("Duplikasi Posting",tc), P("Idempotency guard: uq_je_transaction_id + converted_transaction_id check",tc), P("<font color='#16a34a'>Terlindungi</font>",tc)],
    [P("Reversal kedua",tc), P("InvariantViolationException dilempar jika is_reversed=true",tc), P("<font color='#16a34a'>Terlindungi</font>",tc)],
]
story.append(tbl(acc, [3.5*cm, 10.5*cm, 3*cm]))
story.append(Spacer(1, 8))

story.append(PageBreak())

# ── MUTATION DETAILS ──────────────────────────────────────────────────────────
story.append(P("4. Detail Trace Per Mutasi", h1_sty))

mutations = [
    {
        "title": "Mutation 1 — Koreksi Ekstraksi Dokumen (CORRECT_EXTRACTION)",
        "browser": "URL: /documents/045d3835-.../review | Aksi: Edit form, ketik ulang nominal Rp 5.550.000",
        "frontend": [
            ("Component", "DocumentReviewPage.tsx + DocumentReviewForm.tsx"),
            ("Handler", "handleSave (L116)"),
            ("API", "documentsApi.correct → POST /documents/{id}/corrections"),
            ("Payload", '{"changes": {"amount": "5550000.00", "counterparty_id": "...", "project_id": "..."}, "reason": "..."}'),
        ],
        "backend": [
            ("Router", "backend/src/api/v1/documents.py:correct_document (L243)"),
            ("Auth", "require_application_user (JWT)"),
            ("Authz", "require_reviewer(db, org_id, user_id) + organization_id isolation"),
        ],
        "accounting": [
            ("Tipe akuntansi", "Non-mutating — staged candidate update"),
            ("Perlindungan", "Pessimistic lock with_for_update=True"),
            ("Flag cleared", "AMOUNT_MISMATCH dibersihkan hanya jika field amount ada di payload"),
        ],
        "persistence": [
            ("Tabel", "documents, document_corrections, audit_logs"),
            ("Doc ID", "045d3835-4467-492c-a421-aa35be0bb63f"),
        ],
        "risk": "UX / FUNCTIONAL",
        "status": "MATCH",
        "notes": "WF-001: Frontend hanya mengirim dirty diff — nominal tidak berubah, flag tidak terhapus.",
    },
    {
        "title": "Mutation 2 — Persetujuan Dokumen (APPROVE_CANDIDATE)",
        "browser": "URL: /documents/.../review | Aksi: klik 'Setujui untuk Diposting'",
        "frontend": [
            ("Component", "DocumentReviewPage.tsx"),
            ("Handler", "handleApprove (L125)"),
            ("API", "documentsApi.approve → POST /documents/{id}/approve"),
            ("Payload", "None (empty body)"),
        ],
        "backend": [
            ("Router", "backend/src/api/v1/documents.py:approve_document_candidate (L537)"),
            ("Auth", "require_roles(ADMIN, MANAGER)"),
            ("Authz", "organization_id isolation + peran manajerial"),
        ],
        "accounting": [
            ("Tipe akuntansi", "Non-mutating — status READY_TO_POST"),
            ("Validasi", "is_candidate_ready_for_approval + PostingRuleRegistry.validate_generic_ingestion"),
            ("Idempotency", "HTTP 409 jika status sudah READY_TO_POST atau PROCESSED"),
        ],
        "persistence": [
            ("Tabel", "documents, audit_logs"),
            ("Status transition", "REVIEW_REQUIRED → READY_TO_POST"),
        ],
        "risk": "UX",
        "status": "MATCH",
        "notes": "WF-004: Non-akuntan mengira transaksi sudah dibukukan setelah tombol ini diklik.",
    },
    {
        "title": "Mutation 3 — Pembuatan & Posting Transaksi (POST_ACCOUNTING)",
        "browser": "URL: /documents | Aksi: klik tombol 'Posting' pada baris DOC-2026-000017",
        "frontend": [
            ("Component", "DocumentListPage.tsx"),
            ("Handler", "handlePostAccounting (L220)"),
            ("API", "documentsApi.postAccounting → POST /documents/{id}/post"),
            ("Response", 'transaction_code: "TRX-2026-000011", entry_number: "JE-2026-000011"'),
        ],
        "backend": [
            ("Router", "backend/src/api/v1/documents.py:post_document_candidate (L711)"),
            ("Service", "DocumentPostingService.post_document → TransactionService → AccountingEngine"),
            ("Auth", "require_roles(ADMIN, MANAGER)"),
        ],
        "accounting": [
            ("Aturan posting", "TransactionType.VENDOR_BILL (posting_rules.py L151)"),
            ("Debet", "5101 Harga Pokok Proyek Rp 5.550.000,00"),
            ("Kredit", "2101 Utang Usaha Rp 5.550.000,00"),
            ("Balanced", "Debet == Kredit ✓ (is_balanced=True)"),
            ("Idempotency", "ALREADY_POSTED guard + uq_je_transaction_id constraint"),
        ],
        "persistence": [
            ("Tabel", "transactions, journal_entries, journal_lines, documents, audit_logs"),
            ("Transaction ID", "c2a0c51b-6735-46e2-8656-e59f1bff659d (TRX-2026-000011)"),
            ("Journal ID", "14b4eb19-9437-42b3-a315-8a9c1d22d811 (JE-2026-000011)"),
            ("Status transition", "READY_TO_POST → POSTED"),
        ],
        "risk": "NONE",
        "status": "MATCH",
        "notes": "Tidak ada bypass AccountingEngine. Integritas pembukuan 100% terjaga.",
    },
    {
        "title": "Mutation 4 — Pembatalan Transaksi / Reversal (REVERSAL)",
        "browser": "URL: /transactions/c2a0c51b-... | Aksi: modal pembatalan + alasan E2E-TEST",
        "frontend": [
            ("Component", "TransactionDetailPage.tsx"),
            ("Handler", "reverseMutation.mutateAsync(reason) (L192)"),
            ("API", "transactionsApi.reverse → POST /transactions/{id}/reverse"),
            ("Payload", '{"reason": "E2E-TEST-20260920-1139: Pembatalan pengujian..."}'),
        ],
        "backend": [
            ("Router", "backend/src/api/v1/reversals.py:reverse_transaction (L48)"),
            ("Service", "ReversalService.reverse_transaction"),
            ("Auth", "require_roles(ADMIN, MANAGER)"),
            ("Period check", "assert_period_allows_posting(session, org_id, r_date, actor_role)"),
        ],
        "accounting": [
            ("Metode", "Inverted legs: setiap debet asal menjadi kredit, setiap kredit asal menjadi debet"),
            ("Debet", "2101 Utang Usaha Rp 5.550.000,00"),
            ("Kredit", "5101 Harga Pokok Proyek Rp 5.550.000,00"),
            ("Net impact", "Rp 0,00 (kompensasi sempurna)"),
            ("Linkage", "original_je.reversal_entry_id = rev_je.id (bilateral)"),
            ("Idempotency", "is_reversed=True guard mencegah pembatalan ganda"),
        ],
        "persistence": [
            ("Tabel", "transactions, journal_entries, journal_lines, audit_logs"),
            ("Rev Transaction ID", "de0db39c-d95c-4529-9d3c-1f884a428038 (TRX-2026-000012)"),
            ("Rev Journal ID", "35b7471e-cf4d-4140-8b39-e5a53b77ce06 (JE-2026-000012)"),
            ("Status asal", "TRX-2026-000011: POSTED → REVERSED"),
        ],
        "risk": "NONE",
        "status": "MATCH",
        "notes": "Immutable ledger terjaga. Tidak ada DELETE fisik pada data historis.",
    },
    {
        "title": "Mutation 5 — Proteksi Duplikasi Dokumen (DUPLICATE_GUARD)",
        "browser": "URL: /documents | Aksi: upload ulang E2E-TEST-INV-1139.pdf identik",
        "frontend": [
            ("Component", "FileDropzone.tsx + DocumentListPage.tsx"),
            ("API", "documentsApi.upload → POST /documents/upload"),
            ("Response", "HTTP 409 Conflict → modal peringatan duplikasi"),
        ],
        "backend": [
            ("Router", "backend/src/api/v1/documents.py:upload_document (L164)"),
            ("Service", "DocumentService.create_document → compute_sha256 → DuplicateEntityException"),
            ("Guard", "UniqueConstraint(organization_id, file_hash) di PostgreSQL"),
        ],
        "accounting": [
            ("Tipe akuntansi", "Non-mutating — request ditolak sebelum transaksi terbentuk"),
            ("Hash", "SHA-256: fce779980ac7312e4f05474c12e4d9738560bae24ba66825433e52e089118e02"),
        ],
        "persistence": [
            ("Tabel", "Tidak ada mutasi (rollback)"),
            ("HTTP status", "409 Conflict + detail {document_code, existing_document_id}"),
        ],
        "risk": "NONE",
        "status": "MATCH",
        "notes": "Perlindungan berlapis: service-level SHA-256 check + RDBMS constraint.",
    },
]

for m in mutations:
    story.append(KeepTogether([
        P(m["title"], h2_sty),
        P(f"<b>Browser:</b> {m['browser']}", body_sty),
    ]))

    # Frontend
    story.append(P("Frontend Trace", h3_sty))
    rows = [[P("<b>Field</b>", tcb), P("<b>Nilai</b>", tcb)]]
    for k, v in m["frontend"]:
        rows.append([P(k, tc), P(v, tc)])
    story.append(tbl(rows, [3*cm, 14*cm]))
    story.append(Spacer(1, 3))

    # Backend
    story.append(P("Backend Entry", h3_sty))
    rows = [[P("<b>Field</b>", tcb), P("<b>Nilai</b>", tcb)]]
    for k, v in m["backend"]:
        rows.append([P(k, tc), P(v, tc)])
    story.append(tbl(rows, [3*cm, 14*cm]))
    story.append(Spacer(1, 3))

    # Accounting
    story.append(P("Accounting Flow", h3_sty))
    rows = [[P("<b>Field</b>", tcb), P("<b>Nilai</b>", tcb)]]
    for k, v in m["accounting"]:
        rows.append([P(k, tc), P(v, tc)])
    story.append(tbl(rows, [3*cm, 14*cm]))
    story.append(Spacer(1, 3))

    # Persistence
    story.append(P("Persistence", h3_sty))
    rows = [[P("<b>Field</b>", tcb), P("<b>Nilai</b>", tcb)]]
    for k, v in m["persistence"]:
        rows.append([P(k, tc), P(v, tc)])
    story.append(tbl(rows, [3*cm, 14*cm]))
    story.append(Spacer(1, 3))

    # Risk / Status / Notes
    risk_color = "#dc2626" if m["risk"] not in ("NONE",) else "#16a34a"
    story.append(P(f"<b>Risk:</b> <font color='{risk_color}'>{m['risk']}</font> &nbsp;&nbsp; <b>UI ↔ Backend:</b> <font color='#16a34a'>{m['status']}</font>", body_sty))
    story.append(P(f"<i>Catatan: {m['notes']}</i>", body_sty))
    story.append(hr())

story.append(PageBreak())

# ── MISMATCHES ────────────────────────────────────────────────────────────────
story.append(P("5. Mismatches & Temuan Penting", h1_sty))

mismatches = [
    ("WF-001", "High", "AMOUNT_MISMATCH Flag Gating",
     "Flag tidak dibersihkan jika field nominal tidak dikirim frontend (dirty-only diff). "
     "Pengguna terpaksa mengetik ulang nilai yang sudah benar.",
     "Kirim payload konfirmasi amount otomatis saat klik Setujui, atau sediakan tombol Konfirmasi Nominal."),
    ("WF-002", "High", "Pesan Galat Backend Bocor ke UI",
     "String Python mentah 'Corrected extraction data cannot be rematched' tampil langsung di UI "
     "tanpa lokalisasi bahasa Indonesia.",
     "Ganti dengan pesan operasional: 'Nominal dokumen tidak valid atau harus lebih besar dari Rp 0'."),
    ("WF-003", "Medium", "Tidak Ada Drilldown dari Buku Besar ke Transaksi",
     "Nomor jurnal JE-2026-000011 pada tabel Buku Besar berupa teks polos tanpa hyperlink.",
     "Jadikan nomor jurnal link interaktif ke /transactions/:id."),
    ("WF-004", "Medium", "Dua Tahap Setujui → Posting Membingungkan Non-Akuntan",
     "Setelah klik 'Setujui untuk Diposting', status hanya 'Siap Posting'. "
     "Non-akuntan mengira transaksi sudah tercatat di laporan keuangan.",
     "Sediakan tombol 'Setujui & Posting Langsung' jika semua field valid."),
]

sev_color = {"High": "#dc2626", "Medium": "#d97706", "Low": "#64748b"}

for code, sev, title, desc, rec in mismatches:
    sc = sev_color.get(sev, "#64748b")
    story.append(P(f"<b>{code}</b> — <font color='{sc}'>[{sev}]</font> {title}", h2_sty))
    story.append(P(f"<b>Gejala:</b> {desc}", body_sty))
    story.append(P(f"<b>Rekomendasi:</b> {rec}", body_sty))
    story.append(Spacer(1, 4))

story.append(hr())

# ── BACKEND ARCHITECTURE ──────────────────────────────────────────────────────
story.append(P("6. Backend Architecture Findings", h1_sty))
arch = [
    ("Canonical posting path", "Document approve → READY_TO_POST → DocumentPostingService → TransactionService.create_transaction → AccountingEngine.post_transaction → journal_entries"),
    ("Policy boundaries", "PostingRuleRegistry.validate_generic_ingestion blokir tipe ilegal. Hak akses ketat: ADMIN/MANAGER untuk posting & reversal."),
    ("Direct bypasses found", "Nihil. Tidak ada jalur yang mengabaikan AccountingEngine atau validasi Debet=Kredit."),
    ("Tenant-safety", "Semua query menyertakan filter organization_id. FK counterparty/project divalidasi dalam tenant aktif."),
    ("Idempotency", "Hash SHA-256 dokumen + pessimistic lock + ALREADY_POSTED guard + uq_je_transaction_id constraint + is_reversed guard."),
    ("Immutability", "Reversal menggunakan pola Original → Reversal tanpa DELETE fisik data historis."),
]
rows = [[P("<b>Aspek</b>", tcb), P("<b>Temuan</b>", tcb)]]
for k, v in arch:
    rows.append([P(k, tc), P(v, tc)])
story.append(tbl(rows, [4*cm, 13*cm]))
story.append(Spacer(1, 8))

# ── GRAPHIFY ──────────────────────────────────────────────────────────────────
story.append(P("7. Graphify Findings", h1_sty))
gf = [
    ("Graph stats", "4.999 nodes, 21.749 edges, 196 communities (fresh extraction)"),
    ("God Nodes", "Organization (341), UserRole (295), TransactionType (272), DocumentType (262), Transaction (240)"),
    ("Useful paths", "DocumentPostingService → TransactionService → AccountingEngine → PostingRuleRegistry → JournalEntry (Community 2 & 5). ReversalService → AccountingEngine → JournalEntry (Community 34)."),
    ("Missing edges", "Frontend React komponen tidak terhubung ke router FastAPI — relasi HTTP network tidak di-extract oleh AST code-only mode."),
    ("Live source", "Semua temuan Graphify dikonfirmasi terhadap source code nyata. Tidak ada pertentangan."),
]
rows = [[P("<b>Aspek</b>", tcb), P("<b>Detail</b>", tcb)]]
for k, v in gf:
    rows.append([P(k, tc), P(v, tc)])
story.append(tbl(rows, [3.5*cm, 13.5*cm]))
story.append(Spacer(1, 8))

# ── JOURNEY STATUS ────────────────────────────────────────────────────────────
story.append(P("8. Journey Status", h1_sty))
js = [
    [P("<b>Status</b>", tcb), P("<b>Journey</b>", tcb)],
    [P("<font color='#16a34a'><b>FULLY VERIFIED</b></font>", tc), P("Intake & Ekstraksi Dokumen, Koreksi & Resolusi Flag, Persetujuan, Posting Jurnal, Verifikasi Neraca Saldo, Reversal Resmi, Pencegahan Duplikasi SHA-256", tc)],
    [P("<font color='#64748b'>PARTIAL</font>", tc), P("—", tc)],
    [P("<font color='#dc2626'>FAILED</font>", tc), P("—", tc)],
    [P("<font color='#64748b'>NOT TESTED</font>", tc), P("AP Payment (PAY_VENDOR_BILL), AR Receipt (CUSTOMER_PAYMENT), Bank Reconciliation, WhatsApp transport nyata", tc)],
]
story.append(tbl(js, [3.5*cm, 13.5*cm]))
story.append(Spacer(1, 8))

# ── FOOTER NOTE ───────────────────────────────────────────────────────────────
story.append(hr())
story.append(P("<i>Laporan ini dihasilkan oleh Hermes Agent — Financial SaaS Backend Trace Reconciliation. "
               "Tidak ada kode sumber yang dimodifikasi. Tidak ada data produksi yang dimutasi.</i>", sub_sty))

doc.build(story)
print("PDF OK:", out_path)
