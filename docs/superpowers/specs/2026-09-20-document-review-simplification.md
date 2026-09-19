# Perbaikan Alur Posting Dokumen, Auto-Arsip Bukti, & Penyederhanaan Halaman Review — Design

## Konteks

Deep dive atas laporan user ("tidak bisa posting", "bukti pembayaran ada deskripsi") menemukan
**tiga kelas cacat** pada alur dokumen, bukan satu:

1. **Dead-end flag.** Review flag `AMOUNT_MISMATCH` (dan `DATE_MISMATCH`) **tidak pernah bisa
   dibersihkan**. Endpoint `POST /documents/{id}/corrections` hanya memetakan koreksi `amount`/
   `total_amount` ke flag `OCR_LOW_CONFIDENCE`, bukan ke `AMOUNT_MISMATCH`. Terbukti repro:
   kirim koreksi nominal → HTTP 200, tapi `review_flags` tetap `["AMOUNT_MISMATCH"]`. Akibatnya
   `approve` → 409 ("unresolved review requirements") dan `post` → 422 ("Only READY_TO_POST...").
   Tidak ada jalan keluar dari UI.
2. **Jenis dokumen orphan.** Tujuh jenis tidak pernah menghasilkan kandidat transaksi **dan**
   tidak masuk himpunan dokumen pendukung, sehingga selalu berakhir `REVIEW_REQUIRED` tanpa
   aksi yang mungkin: `BANK_STATEMENT`, `QUOTATION`, `VARIATION_ORDER`, `SUBCONTRACT_AGREEMENT`,
   `PETTY_CASH_PROOF`, `CUSTOMER_RECEIPT`, `UNKNOWN`. Contoh nyata user: DOC-2026-000015
   (BANK_STATEMENT, mutasi Mandiri) buntu.
3. **Tabel rincian salah tampil.** Tabel "Daftar Rincian Barang / Jasa" disembunyikan hanya untuk
   `TRANSFER_PROOF`. Pada `BANK_STATEMENT` tabel tampil berisi sampah OCR (logo bank, "Transaction
   Id", "IDR" dianggap barang), dan justru **jumlah sampah inilah yang memicu `AMOUNT_MISMATCH`**
   (7 baris berjumlah Rp 1.750 vs total Rp 19.939.750).

Selain itu, user meminta halaman review **disederhanakan**: hapus panel "Riwayat Koreksi",
"Detail Teknis", dan input "Mengapa data ini diubah?" yang hanya berguna untuk debugging.

## Tujuan

1. Dokumen yang tidak berorientasi posting **tidak buntu** dan **tidak menumpuk** di antrean review.
2. Review flag yang berasal dari data yang bisa dikoreksi (`AMOUNT_MISMATCH`, `DATE_MISMATCH`)
   **dapat diselesaikan** lewat koreksi, sehingga dokumen finansial bisa disetujui & diposting.
3. Tabel rincian barang/jasa hanya tampil untuk dokumen yang memang memuat rincian (nota/faktur).
4. Halaman review jadi simpel: koreksi tersimpan otomatis, tanpa panel teknis.

## Bukan Tujuan (Non-goals)

- Tidak mengubah aturan jurnal, prinsip double-entry, maupun alur alokasi (bayar utang/piutang).
- Tidak mengubah mesin OCR/klasifikasi selain mempersempit validasi konsistensi line item.
- Tidak menambah status pemrosesan baru; memakai ulang `PROCESSED` dan `REVIEW_REQUIRED`.
- Tidak mendukung posting dari `BANK_STATEMENT` (keputusan user: bukti bank diarsipkan, bukan sumber posting).

## Keputusan Desain

**D1 — Tiga keranjang jenis dokumen.** Satu fungsi `document_kind(document_type)` di modul baru
`backend/src/services/documents/status.py` mengembalikan salah satu:
- `FINANCIAL` — menghasilkan kandidat transaksi: `TRANSFER_PROOF`, `RECEIPT`, `VENDOR_INVOICE`,
  `CUSTOMER_INVOICE`. Alur lama tidak berubah.
- `EVIDENCE` — dokumen bukti/pendukung yang tidak pernah menjadi transaksi: 11 jenis
  `SUPPORTING_DOCUMENT_TYPES` **ditambah** `BANK_STATEMENT`, `QUOTATION`, `VARIATION_ORDER`,
  `SUBCONTRACT_AGREEMENT`, `PETTY_CASH_PROOF`, `CUSTOMER_RECEIPT`.
- `UNKNOWN` — belum bisa diklasifikasi; selalu ke review agar manusia menetapkan jenis.

**D2 — Definisi "jenis yakin".** `document_type_confidence >= DOCUMENT_CONFIDENCE_THRESHOLD`
(config, 0,85) **dan** tidak ada review flag. Hanya ketepatan **jenis** yang dinilai, karena yang
menentukan arsip benar/tidak adalah klasifikasi jenis (bukan nominal/tanggal).

**D3 — Aturan routing status (satu resolver).**
`resolve_document_status(document_type, candidate, flags, confidence_scores)`:
- `FINANCIAL` → `document_status_for` lama (berbasis kandidat & flag).
- `EVIDENCE` + jenis yakin → `PROCESSED` (diarsipkan; tidak masuk antrean review).
- `EVIDENCE` + jenis meragukan → `REVIEW_REQUIRED` (agar jenis bisa dibetulkan).
- `UNKNOWN` → `REVIEW_REQUIRED`.

**D4 — Dokumen arsip bersifat final.** `PROCESSED` tetap terminal (worker & `retry` melewatinya,
`can_review=false`). Dokumen `EVIDENCE` yang **ragu** berada di `REVIEW_REQUIRED` dan di sanalah
tombol "Simpan Dokumen" tersedia untuk membetulkan jenis atau menolak.

**D5 — Flag yang bisa diselesaikan lewat koreksi.**
- `AMOUNT_MISMATCH` dibersihkan bila reviewer mengoreksi `amount`/`total_amount`.
- `DATE_MISMATCH` dibersihkan bila reviewer mengoreksi `date`/`transaction_date`.
- Pemetaan `resolved` yang keliru (`amount` → `OCR_LOW_CONFIDENCE`) diperbaiki.

**D6 — Validasi konsistensi line item dipersempit.** Flag `AMOUNT_MISMATCH` dari penjumlahan
`line_items` vs `total_amount` hanya dijalankan untuk jenis yang memang memuat rincian barang/jasa
(`RECEIPT`, `VENDOR_INVOICE`, `CUSTOMER_INVOICE`). Untuk dokumen bukti (transfer, mutasi bank, dll.)
rincian barang tidak bermakna dan tidak boleh memicu flag.

**D7 — Tabel rincian hanya untuk dokumen ber-rincian.** Tabel "Daftar Rincian Barang / Jasa" hanya
dirender untuk `FINANCIAL` ber-rincian (nota/faktur), tidak untuk dokumen bukti.

**D8 — UI review disederhanakan.**
- Hapus panel "Riwayat Koreksi", panel "Detail Teknis", dan input "Mengapa data ini diubah?".
- Alasan koreksi memakai nilai otomatis tetap `"Verifikasi dokumen sumber"` (untuk simpan,
  persetujuan, pemilihan kandidat, penolakan). Riwayat tetap tercatat di backend, hanya tidak ditampilkan.
- Kotak info "Dokumen pendukung saja" dipertahankan (informatif).

**D9 — Tombol aksi per keranjang dokumen.**
- `EVIDENCE` → satu tombol **"Simpan Dokumen"** (menyimpan koreksi jenis/field; bila ragu).
- `FINANCIAL` → **"Setujui untuk Diposting"** + **"Tolak Kandidat"**. "Setujui" menyimpan koreksi
  yang belum tersimpan terlebih dahulu (menutup dead-end bila ada flag yang bisa diselesaikan),
  lalu menyetujui. Tombol tidak lagi dinonaktifkan semata oleh adanya flag; validasi form dan
  penjagaan backend tetap berlaku.

**D10 — Tidak menyentuh aturan jurnal.** `posting_rules.py`, `accounting_engine.py`, dan alur
alokasi tidak diubah.

## Perubahan Backend

| File | Perubahan |
|---|---|
| `backend/src/services/documents/status.py` (baru) | `DocumentKind`, `document_kind()`, `EVIDENCE_DOCUMENT_TYPES`, `resolve_document_status()`, `is_evidence_only()` |
| `backend/src/services/documents/pipeline.py` | `document_status_for` tetap (alur finansial); `process()` memakai `resolve_document_status(..., document_type, confidence_scores)` |
| `backend/src/services/documents/candidate.py` | Validasi konsistensi line item (D6) dibatasi ke jenis ber-rincian |
| `backend/src/api/v1/documents.py` | Pemetaan `resolved` diperbaiki (D5); endpoint koreksi menangani dokumen `EVIDENCE` tanpa `TransactionCandidate` (hindari 500) dan menghitung ulang status lewat resolver; endpoint `approve` menolak dokumen `EVIDENCE` dengan pesan jelas |

## Perubahan Frontend

| File | Perubahan |
|---|---|
| `frontend/src/utils/documentReview.ts` | `EVIDENCE_DOCUMENT_TYPES` (selaras backend) + `isEvidenceDocument()` |
| `frontend/src/components/documents/DocumentReviewForm.tsx` | Hapus 3 blok UI debug + input alasan; alasan otomatis; tabel rincian hanya untuk dokumen ber-rincian; tombol per keranjang; "Setujui" menyimpan lalu menyetujui |
| `frontend/src/pages/documents/DocumentListPage.tsx` | Tidak ada perubahan fungsional (verifikasi tombol per status tetap benar) |

## Dampak ke Tes

Kebijakan berubah membalik ekspektasi lama — diperbarui eksplisit, bukan dihapus diam-diam:
- `backend/tests/integration/test_uat12_whatsapp_media_transport.py` — skenario 7 (SPK, confidence
  0,95) dari `REVIEW_REQUIRED` → `PROCESSED`; skenario 8 (BAST/Surat Jalan) disesuaikan.
- `backend/tests/unit/test_document_intelligence.py` — signature `document_status_for` berubah.
- `frontend/tests/pages/DocumentReviewSlice4.test.tsx` — assert "Riwayat Koreksi" dihapus.
- `frontend/tests/pages/DocumentReviewWorkspace.test.tsx` — assert "Detail Teknis" + klik "Simpan Koreksi".
- `frontend/tests/pages/DocumentReviewApprovalWorkflow.test.tsx`, `DocumentReviewNavigation.test.tsx` — klik "Simpan Koreksi".

## Celah Testing yang Ditemukan (harus ditutup)

- `test_uat14_end_to_end_stress.py:497` **curang**: menghapus flag langsung di DB
  (`doc_cand.review_flags = []`) alih-alih lewat `POST /corrections`, sehingga jalur yang buntu di
  UI tidak pernah diuji. Harus ditulis tes yang membersihkan flag **lewat API**.
- Tidak ada tes yang membuktikan `AMOUNT_MISMATCH` **bisa dilepas** (yang ada hanya membuktikan
  flag **dipasang**).
- Tidak ada tes alur nyata: pipeline OCR → koreksi → approve → post untuk dokumen ber-flag.
- Tidak ada tes `BANK_STATEMENT`/dokumen bukti → auto-arsip.

## Risiko

| Risiko | Mitigasi |
|---|---|
| Auto-arsip menyembunyikan salah klasifikasi yang "yakin" | Ambang keyakinan 0,85; dokumen ragu tetap review; "Simpan Dokumen" tersedia untuk dokumen ragu |
| `PROCESSED` terminal sehingga dokumen bukti tak bisa dikoreksi | Hanya dokumen bukti **yakin** yang diarsipkan; yang ragu tetap review |
| Memperluas `EVIDENCE` ke 6 jenis orphan berisiko menyembunyikan dokumen yang sebenarnya finansial | Tidak ada regresi: hari ini jenis-jenis itu sudah buntu (tak bisa disetujui); jenis ragu tetap review |
| Daftar jenis frontend vs backend menyimpang | Daftar disamakan + komentar rujukan ke backend |
| Tes lama gagal karena kebijakan berubah | Tes yang mengunci kebijakan lama diperbarui eksplisit |

## Pertanyaan Terbuka

Tidak ada — arah desain telah disepakati user: dokumen bukti (termasuk BANK_STATEMENT) diarsipkan
otomatis bila jenis yakin, dokumen ragu tetap review dengan tombol "Simpan Dokumen", input alasan
dihapus, dan pengerjaan bug fix + penyederhanaan UI dilakukan sekaligus dalam satu plan.
