# Design: Bukti Transfer sebagai Biaya Langsung (Jenis Pencatatan)

- **Status**: DRAFT (menunggu review)
- **Tanggal**: 2026-09-19
- **Konteks**: Dokumen bukti transfer (`TRANSFER_PROOF`) saat ini **tidak bisa** disetujui
  ketika tidak ada tagihan/faktur untuk dialokasikan, karena `proposed_transaction_type`
  tetap `null`. Pemilik ingin bisa mencatat pengeluaran langsung (beli barang/jasa, bensin,
  operasional) dari bukti transfer, dengan pengaman anti double-count.

## Masalah

1. `backend/src/services/documents/candidate.py:32-41` hanya menetapkan tipe bukti transfer
   (`PAY_VENDOR_BILL` / `CUSTOMER_PAYMENT`) dari target alokasi. Tanpa kandidat cocok,
   `proposed_transaction_type = null`.
2. Guard `backend/src/api/v1/documents.py:475` **melarang** bukti transfer menjadi
   `DIRECT_PURCHASE`, `VENDOR_BILL`, atau `CUSTOMER_INVOICE` — sengaja, untuk mencegah
   double-count (prinsip "Cash Movement ≠ Expense", `specs/002.../spec.md:421`).
3. Form review (`DocumentReviewForm.tsx`) **tidak punya** field jenis pencatatan/kategori COA,
   sehingga reviewer tidak punya jalan mengisi tipe transaksi.

## Tujuan

Bukti transfer dapat dicatat sebagai **biaya langsung** (`DIRECT_PURCHASE`) bila reviewer
memilih **Jenis Pencatatan** (kategori COA) secara eksplisit, dengan:
- pengaman kuat anti double-count,
- proyek wajib untuk kategori proyek (akun 5101),
- rekening kas/bank (asal dana) tetap wajib,
- aturan jurnal & double-entry **tidak diubah**.

## Non-Tujuan

- Mengubah `posting_rules.py` atau aturan jurnal.
- Mengubah alur alokasi (bayar utang/piutang) sebagai default.
- Menghapus prinsip "Cash Movement ≠ Expense" — hanya menambah jalur eksplisit & teraudit.

## Keputusan yang Disetujui

| # | Keputusan |
|---|---|
| D1 | Sistem **menyarankan** kategori dari teks OCR (`classify_expense` yang ada), reviewer **dapat mengubah** via picker eksplisit. |
| D2 | Bukti transfer boleh `DIRECT_PURCHASE` **hanya jika** kategori COA terisi DAN `allocation_target_id` kosong. |
| D3 | Pengaman anti double-count dijalankan saat approve. |
| D4 | Kategori proyek (5101) **wajib** memilih proyek. Kategori operasional (610x) tidak. |
| D5 | Rekening kas/bank (asal dana) tetap wajib. |

## Peta Jenis Pencatatan → COA

| Pilihan UI | `cost_category` | `expense_category` | Akun debit | Wajib proyek |
|---|---|---|---|---|
| Beli Barang / Material | `MAT` | – | 5101 | Ya |
| Jasa / Subkontraktor | `SUB` | – | 5101 | Ya |
| Bensin & Transport (proyek) | `TRN` | – | 5101 | Ya |
| Peralatan / Sewa Alat | `EQP` | – | 5101 | Ya |
| Bensin / Kendaraan (kantor) | – | `TRAVEL_OFFICE` | 6104 | Tidak |
| ATK / Operasional Kantor | – | `OFFICE_ADMIN` | 6103 | Tidak |
| Lain-lain | – | `OTHER_OPERATIONAL` | 6199 | Tidak |

Catatan: jurnal `DIRECT_PURCHASE` (`posting_rules.py:110-148`) memakai
`project_id` untuk memilih 5101, dan `expense_category` untuk memilih 610x. Bila
`cost_category` diisi tanpa proyek, `_resolve_expense_account(None)` menghasilkan 6199 —
karena itu D4 mewajibkan proyek untuk kategori 5101.

## Perubahan

### Backend

1. **Longgarkan guard** (`documents.py:475`)
   - `DIRECT_PURCHASE` **diizinkan** untuk `TRANSFER_PROOF` **hanya jika**
     (`cost_category` atau `expense_category` terisi) DAN `allocation_target_id` kosong.
   - `VENDOR_BILL` & `CUSTOMER_INVOICE` tetap **dilarang**.
   - Bila `DIRECT_PURCHASE` dipilih tanpa kategori → 422
     `"Transfer proof as direct expense requires a recording category"`.

2. **Saran kategori dari OCR** (`candidate.py`, blok `TRANSFER_PROOF`)
   - Ketika tidak ada target alokasi, panggil `classify_expense(...)` (sudah ada) dan isi
     `cost_category`/`expense_category` usulan. `proposed_transaction_type` tetap `null`
     sampai reviewer menyetujui — saran saja, bukan keputusan.
   - Simpan `expense_classification` di `matching_results` (sudah ada polanya di
     `candidate.py:61`).

3. **Pengaman anti double-count** (baru, dipakai saat approve)
   - Modul baru `backend/src/services/documents/expense_duplicate_guard.py`.
   - Input: `org_id`, `amount`, `counterparty_id`, `transaction_date`.
   - Cari:
     - Vendor bill **belum lunas** dengan nominal dalam ±1% & vendor sama → **tolak**,
       arahkan ke alokasi (`"Similar unpaid bill <kode> exists; allocate the payment instead"`).
     - Customer invoice / transaksi terposting nominal mirip → **tolak**
       (`"Similar posted document <kode> exists; possible duplicate"`).
   - Dipanggil di endpoint approve **hanya** untuk jalur `DIRECT_PURCHASE` dari
     `TRANSFER_PROOF` (tidak mengganggu jalur alokasi).
   - Menggunakan kembali heuristik `DuplicateDetectionService` bila cocok.

4. **Validasi** (`is_candidate_ready_for_approval`, `documents.py:45`)
   - `DIRECT_PURCHASE`: wajib `payment_account_id` DAN (`project_id` bila kategori 5101;
     `expense_category` bila kategori 610x). Sudah sebagian ada; sesuaikan agar kategori
     operasional tidak menuntut proyek.

### Frontend

5. **Field "Jenis Pencatatan"** (`DocumentReviewForm.tsx`)
   - Muncul untuk `TRANSFER_PROOF` (dan tetap untuk jalur yang sudah butuh).
   - Opsi = tabel di atas. Nilai awal = saran OCR bila ada.
   - Menyetel `cost_category`/`expense_category` + `proposed_transaction_type = 'DIRECT_PURCHASE'`
     saat disimpan.
   - Proyek menjadi wajib (asterisk + validasi) ketika kategori 5101 dipilih.

6. **Validasi form** (`utils/documentReview.ts`)
   - `DIRECT_PURCHASE`: `payment_account_id` wajib; salah satu proyek/kategori wajib;
     kategori 5101 → proyek wajib.
   - Pesan galat spesifik per kondisi.

### Test

7. **Backend**
   - Guard: bukti transfer + kategori + tanpa alokasi → boleh; tanpa kategori → 422;
     `VENDOR_BILL` → tetap 422.
   - Anti double-count: bill belum lunas nominal mirip → 422; transaksi terposting mirip → 422;
     tidak ada yang mirip → lolos.
   - Jurnal: `DIRECT_PURCHASE` dari bukti transfer menghasilkan Debit 5101/610x, Kredit 1101.
   - Test lama yang meng-assert "transfer proof cannot be direct purchase" disesuaikan.

8. **Frontend**
   - Picker tampil, saran OCR terisi, proyek wajib untuk kategori 5101, validasi pesan.

## Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Double-count beban | Pengaman anti double-count (butir 3) |
| COA salah | Saran OCR + reviewer wajib mengonfirmasi eksplisit |
| 5101 tanpa proyek → 6199 | D4: proyek wajib untuk kategori proyek |
| Regresi alur alokasi | Guard hanya menambah jalur; jalur lama tidak disentuh |

## Pertanyaan Terbuka

- Ambang "nominal mirip": diusulkan ±1% (bisa disesuaikan).
- Apakah jenis pencatatan juga perlu muncul untuk `RECEIPT`? (Saat ini `RECEIPT` sudah
  otomatis `DIRECT_PURCHASE`.)
