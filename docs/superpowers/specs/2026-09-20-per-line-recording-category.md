# Kategori Pencatatan Per Baris & Penggabungan Barang+Jasa ke HPP — Design

## Konteks

User meminta agar pencatatan mengikuti laporan keuangan nyata perusahaannya (Laba Rugi PT SAMUDERA
TERANG JAYA 2025) dan menegaskan satu prinsip: **HPP = pembelian barang ATAU jasa yang terkait
suatu proyek** (mis. jasa pengiriman khusus proyek, jasa pasang bearing), sedangkan **jasa
administratif** (mis. jasa pembuatan dokumen) dan **materai** masuk **Beban Operasional**.

Temuan saat menelusuri kode:

1. **Laba Rugi PDF memakai SATU baris "HARGA POKOK" (HPP) = 4.174.052.006** — barang dan jasa
   tidak dipisah di laporan. Yang dipisah hanya HPP vs Beban Umum & Administrasi. Akun app
   `5101 Harga Pokok Proyek` sudah menampung `MAT`/`SUB`/`LOG`/`TRN`/`EQP` **selama ada
   `project_id`** — jadi "digabung ke satu HPP" sudah benar di level akun.
2. **Satu invoice = satu kategori saja.** `TransactionCandidate` hanya punya satu
   `cost_category`/`expense_category`, dan `document_posting_service.py` (baris 425-446) membangun
   `TransactionCreate` dengan satu kategori. Akibatnya invoice `DOC-2026-000016`
   (`JASA ANGKUT GERMAN TO JAKARTA` 19.927.250 + `STAMP` 10.000) diposting ke **satu akun** untuk
   seluruh invoice. **User menegaskan ini salah** — jasa dan materai dalam satu invoice harus
   **beda akun**.
3. **`LOG` (logistik/freight) tidak ada di katalog UI** (`shared/recording-categories.json`),
   sehingga "JASA ANGKUT" jatuh ke default `OTHER_OPERATIONAL` (6199). `classify_expense` juga
   belum punya aturan freight/ekspedisi.
4. **Picker "Jenis Pencatatan" hanya muncul untuk `TRANSFER_PROOF`** — pada `RECEIPT`/`VENDOR_INVOICE`
   kategori diisi otomatis dan tidak bisa dikoreksi reviewer.

Kabar baik: model data **sudah mendukung** pemisahan. `TransactionAllocation` bisa banyak per
transaksi, `TransactionCreate.allocations: List[TransactionAllocationInput]` sudah ada, dan
`validate_transaction_allocations` sudah memastikan jumlah alokasi == total transaksi. Yang belum
ada adalah (a) kategori per baris, (b) UI-nya, (c) pembangunan alokasi per baris di jalur approve.

## Tujuan

1. **Satu invoice dapat diposting ke beberapa akun** sesuai isi tiap baris (jasa → HPP 5101,
   materai → operasional).
2. **HPP menampung barang DAN jasa proyek** dalam satu akun 5101 (sesuai Laba Rugi PDF).
3. **OCR menyarankan kategori per baris; reviewer memutuskan** (prinsip tetap).
4. **Jumlah alokasi selalu == total invoice** (tidak ada rupiah yang hilang/berlebih).
5. **Laporan Laba Rugi tetap 1 baris HPP** seperti PDF.

## Bukan Tujuan (Non-goals)

- **Tidak** mengubah aturan jurnal di `posting_rules.py` (5101 sudah menampung MAT/SUB/LOG/TRN/EQP;
  610x/6199 untuk operasional). Pemetaan akun tetap.
- **Tidak** merombak struktur Laba Rugi/Neraca app menjadi persis PDF (itu opsi B/C yang tidak
  dipilih). Laba Rugi tetap 1 baris HPP + Beban Operasional.
- **Tidak** menambah/mengubah akun COA.
- **Tidak** mengganti mesin OCR.
- **Tidak** menambah kolom DB baru: kategori per baris disimpan di dalam JSON
  `extracted_data.line_items` dan `candidate_transaction`, bukan tabel baru.

## Keputusan Desain

**D1 — Kategori per baris pada `LineItem`.** `LineItem` (`backend/src/schemas/document.py`) mendapat
dua field opsional: `cost_category: Optional[CostCategory]` dan `expense_category:
Optional[ExpenseCategory]`. Disimpan sebagai bagian dari JSON yang sudah ada — tidak ada migrasi DB.

**D2 — Saran kategori per baris.** Fungsi baru `classify_line_item(description, project_id,
document_text)` menjalankan `classify_expense` **per deskripsi baris** dan mengembalikan
`cost_category`/`expense_category` untuk baris itu. Aturan baru yang ditambahkan ke
`expense_classifier.py`:
- `jasa angkut|kirim|ekspedisi|freight|logistik|ongkos kirim|pengiriman` → `CostCategory.LOG`.
- `pasang|instalasi|instal|bearing|servis|perbaikan` → `CostCategory.SUB`.
- `materai|stamp|tempel|meterai` → `ExpenseCategory.OTHER_OPERATIONAL` (operasional, bukan HPP).
- `jasa pembuatan dokumen|administrasi|perizinan|dokumen` → `ExpenseCategory.OFFICE_ADMIN`.
Saran hanya *usulan*; `review_required` tetap dihormati.

**D3 — `LOG` masuk katalog bersama.** Tambah `{ "value": "LOG", "kind": "cost",
"requiresProject": true }` ke `shared/recording-categories.json` + label UI
`LOG: 'Jasa Angkut / Ekspedisi (proyek)'` di `frontend/src/utils/recordingCategories.ts`. Karena
katalog adalah sumber tunggal lintas bahasa, perubahan ini **wajib** disertai pembaruan tes
kontrak backend (`tests/unit/test_recording_categories.py`).

**D4 — Picker per baris di UI.** Tabel "Daftar Rincian Barang / Jasa"
(`DocumentReviewForm.tsx`) mendapat kolom **"Jenis Pencatatan"** per baris berisi dropdown dari
`RECORDING_CATEGORIES`, terisi otomatis dari saran D2. Reviewer dapat mengubah tiap baris. Ini
memperluas picker yang saat ini hanya untuk `TRANSFER_PROOF` — kini juga untuk dokumen ber-rincian
(`RECEIPT`, `VENDOR_INVOICE`, `CUSTOMER_INVOICE`).

**D5 — Approve membangun alokasi per baris.** `document_posting_service.py` mengelompokkan
`line_items` **berdasarkan pasangan (project_id, cost_category, expense_category)** dan mengirim
`TransactionCreate.allocations` berisi satu `TransactionAllocationInput` per kelompok, dengan
`amount` = jumlah baris dalam kelompok. Jika tidak ada baris berkategori (mis. dokumen lama),
perilaku lama (satu kategori dokumen) dipertahankan sebagai fallback. `validate_transaction_allocations`
sudah menjamin jumlah == total; bila tidak cocok (mis. ada baris tanpa kategori), approve
**gagal dengan pesan jelas**, bukan memposting diam-diam.

**D6 — Aturan HPP vs Operasional (sesuai user).**
- **HPP (5101):** `MAT` (barang), `SUB` (jasa pemasangan/subkon), `LOG` (angkut/kirim untuk proyek),
  `TRN` (transport proyek), `EQP` (sewa alat) — **semua memerlukan `project_id`**.
- **Beban Operasional (610x/6199):** materai, jasa pembuatan dokumen, ATK, gaji, listrik, dll. —
  tidak butuh proyek.
- Konsekuensi: baris berkategori HPP pada dokumen **tanpa proyek** akan ditolak validasi
  (`PROJECT_REQUIRED_COST_CATEGORIES`) dengan pesan yang meminta reviewer menetapkan proyek — bukan
  diam-diam jatuh ke 6199 (menutup jebakan yang tercatat di skill).

**D7 — Laporan tidak berubah.** `pl_service.py` tetap menjumlahkan akun 51xx menjadi satu baris
"Harga Pokok Proyek (HPP)". Tidak ada perubahan reporting.

## Perubahan Backend

| File | Perubahan |
|---|---|
| `backend/src/schemas/document.py` | `LineItem` + `cost_category`, `expense_category` (opsional) |
| `backend/src/services/documents/expense_classifier.py` | Aturan baru: LOG (angkut/kirim/ekspedisi), SUB (pasang/servis), materai→operasional, dokumen→OFFICE_ADMIN |
| `backend/src/services/documents/line_item_classifier.py` (baru) | `classify_line_items(items, project_id, document_text)` — saran kategori per baris |
| `backend/src/services/documents/candidate.py` | `build_candidate` mengisi kategori per baris via classifier baru; kategori dokumen dipertahankan sebagai ringkasan |
| `backend/src/services/document_posting_service.py` | Bangun `TransactionCreate.allocations` dari kelompok baris (D5) + validasi jumlah |
| `backend/src/api/v1/documents.py` | Tambah `line_items` ke whitelist `allowed` di `POST /corrections` (kini **tidak ada** → kirim kategori per baris akan 422); salin ke `extracted_data` |
| `shared/recording-categories.json` | Tambah `LOG` |
| `backend/tests/unit/test_recording_categories.py` | Sesuaikan kontrak untuk `LOG` |

## Perubahan Frontend

| File | Perubahan |
|---|---|
| `frontend/src/utils/recordingCategories.ts` | Label `LOG` |
| `frontend/src/components/documents/DocumentReviewForm.tsx` | Kolom "Jenis Pencatatan" per baris di tabel rincian; sertakan kategori per baris saat simpan/approve |
| `frontend/src/utils/documentReview.ts` | Validasi: tiap baris berkategori-HPP wajib punya proyek |
| `frontend/src/api/documents.ts` | Kirim `line_items[].cost_category/expense_category` pada koreksi |

## Alur Data

```
OCR → table_extractor → LineItem[] (deskripsi + nominal)   [sudah diperbaiki: commit 5283fee]
   → classify_line_items() → LineItem[] (+ saran kategori per baris)
   → DocumentReviewForm: reviewer melihat & mengubah kategori tiap baris
   → POST /corrections (line_items dengan kategori) → candidate_transaction
   → POST /approve → document_posting_service:
         kelompokkan baris per (project, cost_category, expense_category)
         → TransactionCreate(allocations=[...])
         → PostingRuleRegistry → jurnal: 5101 (HPP) + 610x/6199 (operasional) ; kredit 1101/2101
```

Contoh `DOC-2026-000016` (tanpa proyek, jadi ilustrasi dengan proyek ditetapkan):
| Baris | Kategori | Akun |
|---|---|---|
| JASA ANGKUT GERMAN TO JAKARTA — 19.927.250 | `LOG` (+ proyek) | 5101 HPP |
| STAMP — 10.000 | `OTHER_OPERATIONAL` | 6199 Beban Operasional |
| **Total** | | **19.937.250** = total invoice ✓ |

## Dampak ke Tes

- Tes baru: klasifikasi per baris (jasa→LOG, materai→operasional, pasang bearing→SUB).
- Tes baru: approve menghasilkan **2 alokasi** dengan kategori/akun berbeda dan jumlah == total.
- Tes baru: baris HPP tanpa proyek → approve ditolak dengan pesan jelas (bukan jatuh ke 6199).
- Tes regresi: dokumen tanpa kategori per baris tetap memakai jalur lama (satu alokasi).
- Tes kontrak `test_recording_categories.py` diperbarui untuk `LOG`.
- Suite unit+security (659 tes) harus tetap hijau.

## Risiko

| Risiko | Mitigasi |
|---|---|
| Saran kategori per baris salah (mis. "STAMP" dianggap jasa) | Reviewer dapat mengubah tiap baris; OCR hanya menyarankan |
| Jumlah alokasi ≠ total karena baris tanpa kategori | Validasi eksplisit; approve gagal dengan pesan, tidak posting diam-diam |
| `LOG` baru mengubah kontrak lintas bahasa | Katalog tetap sumber tunggal; tes kontrak diperbarui sengaja |
| Dokumen lama tanpa kategori per baris rusak | Fallback ke jalur satu-kategori lama |
| Baris HPP tanpa proyek | Validasi menolak dengan pesan; tidak jatuh ke 6199 |

## Pertanyaan Terbuka

Tidak ada — lingkup telah disepakati user: pemisahan kategori per baris **ya** (jasa → HPP, materai
→ operasional dalam satu invoice), HPP = barang atau jasa terkait proyek, aturan jurnal & COA tidak
diubah, laporan tetap 1 baris HPP.
