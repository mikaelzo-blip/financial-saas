# Financial SaaS Active Workflow Audit Report: J8 WhatsApp Intake → Web Review

- **Run ID:** `E2E-TEST-20260920-1505`
- **Tanggal:** 20 September 2026
- **Git Commit SHA:** `26ab5affee58` (`26ab5af`)
- **Git Branch:** `hermes/document-review-simplification-v2`
- **Tenant:** `PT Kontraktor Utama Indonesia` (`9670673b-c0fd-4ebe-87e4-a646358084ea`)
- **Lingkungan:** `local-development` (PostgreSQL Docker, FastAPI backend port 8000, Vite frontend port 5173, Baileys WhatsApp Bridge port 3000)
- **Klasifikasi Transport:** `INTERNAL_INGESTION_ONLY`
- **Status Akhir Workflow J8:** `PARTIAL`
  *(Catatan: Lapisan internal penyerapan berkas, worker OCR, antarmuka review web, persetujuan pengguna, posting GL, dan reversal terverifikasi penuh; transport eksternal WhatsApp seluler/Meta ditandai `NOT_VERIFIED` karena ketiadaan pengirim seluler fisik eksternal dalam sesi otomatis ini).*

---

## 1. Executive Summary & Ringkasan Hasil

Audit alur kerja **J8 (WhatsApp Intake → Web Review)** dilakukan dengan menjalankan verifikasi end-to-end berbasis browser, API, worker latar belakang, dan basis data PostgreSQL.

### Ringkasan Status Pengujian:
1. **Transport Real/Provider:** Ditandai **`NOT_VERIFIED`** (diklasifikasikan sebagai `INTERNAL_INGESTION_ONLY`). Meskipun proses jembatan Baileys (`bridge.js` pada port 3000) aktif dan terhubung (`status: "connected"`), tidak ada perangkat ponsel fisik eksternal yang aktif mengirimkan pesan WhatsApp melalui jaringan seluler/Meta selama pengujian. Sesuai instruksi audit, pengujian tidak memfabrikasi ketersediaan transport riil.
2. **Penyerapan Internal (Internal Ingestion):** **`VERIFIED`**. Dua mekanisme penyerapan internal diuji dan berhasil 100%:
   - **Jalur Remote Relay Backlog Sync:** `POST /api/v1/inbox/capture` + `POST /api/v1/inbox/sync` berhasil menyerap berkas invoice sintetis (`DOC-WA-27300435`), menyimpan blob dengan hash SHA-256 terverifikasi, dan membuat antrean analitik worker.
   - **Jalur Mesin Hermes Document Upload:** `POST /api/v1/hermes/documents/upload` berhasil menyerap bukti transaksi sintetis (`DOC-2026-000018`) dengan autentikasi token mesin per-tenant, mencatat metadata WhatsApp (`source_channel="WHATSAPP"`), dan memicu background processing.
3. **Background Worker & Offline Resilience:** **`VERIFIED`**. Berkas dan metadata (caption/keterangan) tersimpan aman di basis data dan penyimpanan lokal saat berada dalam status tunggu (`RECEIVED` / `UPLOADED`), dan diproses secara asinkron saat worker aktif tanpa kehilangan data.
4. **Visibilitas Web Review:** **`VERIFIED`**. Dokumen WhatsApp muncul pada daftar dokumen dengan indikator saluran WhatsApp, kartu status "Integrasi WhatsApp: Terhubung", dan filter saluran. Halaman review menampilkan kartu khusus "Keterangan dari Pengirim", skor keyakinan OCR (98%), serta flag integritas (vendor/proyek belum dikenal).
5. **Penyelesaian Finansial (Financial Completion):** **`VERIFIED`**. Dokumen `DOC-WA-27300435` disetujui melalui form review dan diposting ke Buku Besar Umum (GL):
   - Transaksi: `TRX-2026-000028` (`VENDOR_BILL`, Rp 3.750.000,00)
   - Jurnal: `JE-2026-000027`
   - Invarian: **Debet = Kredit = Rp 3.750.000,00** (Debet 5101 HPP Proyek PRJ-2026-001, Kredit 2101 Utang Usaha PT Nusa Engineering).
6. **Pembersihan Bersih (Reversal Cleanup):** **`VERIFIED`**. Transaksi `TRX-2026-000028` dibalik secara otomatis menggunakan `ReversalService` menjadi `TRX-2026-000029` (`REVERSAL`) dan `JE-2026-000028`. Dampak finansial bersih terhadap buku besar adalah **tepat Rp 0,00 (nol)**. Dokumen uji tetap tersimpan dalam riwayat audit.
7. **Temuan Baru Teridentifikasi:** **`WF-019 (Medium)`** — Duplikasi prefix `/api/v1` pada `frontend/src/api/inbox.ts` menyebabkan panggilan ke `/api/v1/api/v1/inbox/messages` menghasilkan HTTP 404 pada halaman `/whatsapp-inbox`.

---

## 2. Pemetaan Arsitektur Live WhatsApp

Berdasarkan inspeksi langsung terhadap kode sumber dan proses sistem yang berjalan:

| Komponen | Implementasi Live | Peran & Tanggung Jawab |
| :--- | :--- | :--- |
| **WhatsApp Provider / Bridge** | Baileys Bridge (`bridge.js` port 3000, Node.js PID 19580) & Meta Webhook Handler | Menjaga koneksi socket WhatsApp Web, menerima webhook masuk, menyediakan long-poll buffer pesan. |
| **SaaS Adapter Boundary** | `HermesApiClient` (`src/services/hermes/client.py`) & `WhatsAppWebhookService` | Memvalidasi token adapter (`WHATSAPP_ADAPTER_TOKEN`) dan token tenant (`WHATSAPP_TENANT_TOKENS`). Tidak memegang ketergantungan database akuntansi. |
| **SaaS Document Intake** | `POST /api/v1/hermes/documents/upload` (`src/api/v1/hermes.py`) | Titik masuk resmi penyerapan berkas WhatsApp. Menerapkan idempotensi `wa-msg-<sha256(wamid)>`, menetapkan `source_channel="WHATSAPP"`. |
| **Remote Relay & Inbox** | `RemoteInboxService` (`src/api/v1/inbox.py` & `src/services/remote_inbox_service.py`) | Mengelola penyerapan tangkapan pesan remote (`/capture`), sinkronisasi antrean backlog (`/sync`), dan sesi dokumen (`DocumentSession`). |
| **Penyimpanan Berkas (Storage)** | `StorageService` (`src/services/storage_service.py`) | Menyimpan berkas asli tak terubahkan (immutable), menghitung hash SHA-256 untuk pencegahan duplikasi. |
| **Async Processing Pipeline** | `DocumentPipeline` & `DeferredAnalysisService` via `src.worker` | Menjalankan OCR (Tesseract / EasyOCR / LLM fallback), klasifikasi tipe dokumen, ekstraksi bidang, dan deteksi kandidat transaksi. |
| **Web Review Interface** | `DocumentListPage.tsx`, `DocumentReviewPage.tsx`, `WhatsAppInboxPage.tsx` | Memungkinkan verifikator melihat kartu integrasi WhatsApp, membaca keterangan pengirim, mengoreksi entitas, dan menyetujui dokumen. |
| **Posting Akuntansi** | `DocumentPostingService` (`src/services/document_posting_service.py`) | Mengubah kandidat dokumen menjadi transaksi akuntansi dan entitas jurnal ganda berimbang. |

---

## 3. Klasifikasi Kapabilitas Transport: INTERNAL_INGESTION_ONLY

- **Klasifikasi Terpilih:** **`INTERNAL_INGESTION_ONLY`**
- **Bukti & Justifikasi:**
  - Jembatan lokal Baileys berjalan pada `http://127.0.0.1:3000` dengan endpoint `/health` mengembalikan status `"connected"` dan sesi tersimpan di `C:\Users\Fikri\.hermes\whatsapp\session`.
  - Backend FastAPI berjalan dengan `WHATSAPP_PROVIDER=baileys` dan `baileys_poller_loop` aktif.
  - Namun, dalam sesi pengujian otomatis ini tidak terdapat perangkat seluler fisik eksternal yang dioperasikan untuk mengirimkan pesan WhatsApp melintasi jaringan internet publik WhatsApp/Meta.
  - Webhook Meta Cloud publik juga memerlukan URL publik HTTPS (ngrok/Cloudflare tunnel) yang tidak aktif pada saat audit.
  - Oleh karena itu, pengujian tidak memalsukan status transport eksternal dan secara jujur mencatat:
    - **REAL_TRANSPORT = NOT_VERIFIED**
    - **WORKFLOW J8 = PARTIALLY_VERIFIED (Internal Ingestion + OCR + Web Review + Posting Verified)**.

---

## 4. Berkas Sintetis & Rincian Pengujian

Seluruh data dan dokumen pengujian adalah data sintetis tanpa data rahasia atau entitas bisnis nyata:

### Dokumen Sintetis A (Invoice Vendor WhatsApp):
- **Nomor Dokumen:** `DOC-WA-27300435` (ID: `2befaab5-24f6-4e73-9460-58b1c8d7e544`)
- **Nama Berkas:** `synthetic_wa_invoice.jpg` (Ukuran: 40.996 bytes)
- **Hash SHA-256:** `0cc1203f8560854685460c8bf86daba6ca7f09701db7b4afce85348ea9df0a79`
- **Keterangan / Caption Pengirim:**
  ```text
  E2E-TEST-20260920-1505
  Invoice vendor untuk pengujian workflow.
  Nominal dan seluruh data adalah sintetis.
  ```
- **Nomor Telepon Pengirim:** `+6285***760` (Terdaftar aktif sebagai peran OPERATOR)
- **Data Ekstraksi OCR:**
  - Nomor Faktur: `INV-WA-20260920-001`
  - Penerbit: `PT Semen Nusantara Jaya`
  - Nominal: `Rp 3.750.000` (Subtotal `Rp 3.750.000`)
  - Tanggal: `2026-09-20`, Jatuh Tempo: `2026-10-20`
  - Review Flags Terdeteksi: `['VENDOR_UNKNOWN', 'PROJECT_UNKNOWN']`

### Dokumen Sintetis B (Kwitansi Pembelian Material WhatsApp):
- **Nomor Dokumen:** `DOC-2026-000018` (ID: `cfd010ad-7820-4185-8f2f-c6668ab1304b`)
- **Nama Berkas:** `synthetic_wa_receipt.jpg` (Ukuran: 29.213 bytes)
- **Hash SHA-256:** `17a7811807d9b9409fe65efad1efbe70513997ef8b89d89280d0d8fb5d8bb63a`
- **Keterangan / Caption:** `E2E-TEST-20260920-1505 Pembelian Cat Tembok Propan`
- **Data Ekstraksi OCR:**
  - Penerbit: `Toko Bangunan Sumber Rejeki`
  - Nominal: `Rp 1.250.000`
  - Tipe Kandidat: `DIRECT_PURCHASE`

---

## 5. Ketahanan Sistem, Idempotensi & Batas Keamanan

1. **Idempotensi Penyerapan Pesan (Transport-Level):**
   - Pengiriman ulang payload yang sama persis (`WA-MSG-E2E-20260920-1505-001`) ke `/api/v1/inbox/capture` mengembalikan ID pesan yang sama (`4e582ffb-be13-47cd-a7d4-5be233ff2375`) tanpa menduplikasi baris pada tabel `inbox_messages`.
   - Pengiriman ulang berkas dengan `Idempotency-Key` yang sama ke `/api/v1/hermes/documents/upload` mengembalikan respons HTTP 200 dengan dokumen ID yang sama (`cfd010ad-7820-4185-8f2f-c6668ab1304b`).
2. **Pencegahan Berkas Duplikat (Feature 005 Content-Level):**
   - Berkas dengan isi identik diunggah dengan `Idempotency-Key` berbeda dan WAMID berbeda. Sistem mengenali kecocokan hash SHA-256 berkas dan mengembalikan dokumen yang sudah ada tanpa membuat entitas duplikat di basis data.
3. **Ketahanan Offline / Worker Downtime:**
   - Pesan dan lampiran yang masuk saat worker offline disimpan dengan status aman (`RECEIVED` dan `UPLOADED`).
   - Ketika worker dijalankan, antrean backlog diproses secara otomatis menjadi status `REVIEW_REQUIRED` tanpa kehilangan metadata ataupun data gambar.
4. **Isolasi Keamanan & Batas Multi-Tenant:**
   - **Pengirim Tidak Dikenal:** Permintaan dari nomor seluler `+6289999999999` yang belum dipetakan ditolak dengan respons **HTTP 403 Forbidden** (`{"detail": "Sender unavailable"}`).
   - **Webhook Tanpa Signature:** Permintaan tanpa header tanda tangan `X-Hub-Signature-256` ditolak dengan respons **HTTP 401 Unauthorized** (`{"detail": "Invalid webhook signature"}`).
   - **Token Mesin Palsu:** Permintaan dengan token Authorization tidak sah ditolak dengan **HTTP 503 / 401**.

---

## 6. Verifikasi Antarmuka Web Review & Rekonsiliasi Finansial

### Bukti Browser UI:
1. **Daftar Dokumen (`DocumentListPage.tsx`):**
   - Menampilkan kartu "INTEGRASI WHATSAPP" dengan status: *Terhubung*, Terakhir Masuk: *20 Sep 2026*, Antrean / Pending: *1*, Terakhir Berhasil: *20 Sep 2026*.
   - Filter `Saluran: WhatsApp` berfungsi menyaring berkas WhatsApp secara instan (`DOC-WA-27300435` dan `DOC-2026-000018`).
2. **Halaman Review Dokumen (`DocumentReviewPage.tsx`):**
   - Menampilkan kartu **"Keterangan dari Pengirim"** yang memuat caption WhatsApp asli dengan catatan penjelas: *"Keterangan pesan pengirim dicatat terpisah sebagai petunjuk pencocokan dan tidak menggantikan teks hasil ekstraksi OCR dokumen."*
   - Menampilkan skor keyakinan OCR (Tulisan terbaca: 98%, Jenis dokumen: 95%, Jumlah uang: 98%).
   - Menampilkan peringatan integritas (*Vendor belum dikenali*, *Proyek belum dikenali*).
3. **Persetujuan & Koreksi:**
   - Verifikator melengkapi proyek (`PRJ-2026-001`), kategori pencatatan (`Beli Barang / Material`), dan counterparty (`PT Nusa Engineering`).
   - Tombol *Setujui untuk Diposting* diklik; status dokumen berubah menjadi `SIAP POSTING`.
4. **Posting Akuntansi (General Ledger Audit):**
   - Tombol *Posting* diklik; backend menghasilkan:
     - **Transaksi:** `TRX-2026-000028` (Tipe: `VENDOR_BILL`, Status: `POSTED`, Nominal: Rp 3.750.000,00)
     - **Jurnal:** `JE-2026-000027` (Balanced: `True`)
     - **Debet:** Akun 5101 (Harga Pokok Proyek) = `Rp 3.750.000,00` (terkait Proyek `PRJ-2026-001`)
     - **Kredit:** Akun 2101 (Utang Usaha) = `Rp 3.750.000,00` (terkait Vendor `PT Nusa Engineering`)
     - **Invarian Finansial:** Total Debet == Total Kredit terbukti seimbang presisi (Rp 3.750.000,00 == Rp 3.750.000,00).

### Pembersihan Bersih (Reversal Cleanup):
- Transaksi `TRX-2026-000028` dibalik secara otomatis melalui `ReversalService`:
  - **Transaksi Pembalik:** `TRX-2026-000029` (`REVERSAL`)
  - **Jurnal Pembalik:** `JE-2026-000028`
  - **Baris Pembalik 1:** Debet 0,00 / Kredit 3.750.000,00 (Akun 5101 HPP Proyek)
  - **Baris Pembalik 2:** Debet 3.750.000,00 / Kredit 0,00 (Akun 2101 Utang Usaha)
  - **Dampak Finansial Bersih:** **Tepat Rp 0,00 (Nol)**. Integritas buku besar umum tetap bersih tanpa saldo liar pasca audit.

---

## 7. Temuan Audit (Findings)

### Temuan Baru: WF-019
- **ID Temuan:** `WF-019`
- **Judul:** *Duplicate /api/v1 URL prefix in inboxApi breaks WhatsApp Inbox page*
- **Tingkat Keparahan:** `MEDIUM`
- **Status:** `OPEN`
- **Alur Kerja Terkait:** `J8_whatsapp_to_web_review`
- **Lokasi Kode:**
  - `frontend/src/api/inbox.ts:17,22,34,39`
  - `frontend/src/pages/inbox/WhatsAppInboxPage.tsx:45`
- **Deskripsi Masalah:**
  `inboxApi` mendefinisikan URL panggilan API dengan string berawalan `/api/v1/inbox/messages`, `/api/v1/inbox/sync`, dan `/api/v1/inbox/sessions`. Karena `apiClient.baseURL` sudah secara default menyertakan `/api/v1`, Axios merangkai URL menjadi `/api/v1/api/v1/inbox/messages` yang mengembalikan respons **HTTP 404 Not Found**.
- **Dampak Pengguna (UX Failure):**
  Pada `WhatsAppInboxPage.tsx`, kegagalan kueri `useQuery` tidak menampilkan komponen peringatan kesalahan (error alert) atau tombol coba lagi, melainkan langsung jatuh ke status kosong (*empty state*):
  > *"Tidak ada pesan WhatsApp — Belum ada bukti transaksi yang diterima untuk filter status ini."*
  Hal ini menyesatkan pengguna operasional yang mengira antrean benar-benar kosong padahal terjadi kegagalan jaringan/rute API.
- **Rekomendasi Perbaikan:**
  Hapus prefix `/api/v1` dari `frontend/src/api/inbox.ts` sehingga memanggil `/inbox/messages`, `/inbox/sync`, dan `/inbox/sessions`. Tambahkan penanganan `isError` eksplisit pada `WhatsAppInboxPage.tsx` agar kesalahan jaringan tertampil jelas.

---

## 8. Tangkapan Layar Bukti Audit

Seluruh tangkapan layar tersimpan pada direktori audit `docs/audits/E2E-TEST-20260920-1505/screenshots/`:
1. `01_document_list_page.png` — Kartu Integrasi WhatsApp (Status Terhubung, statistik antrean, status worker).
2. `02_documents_filtered_whatsapp.png` — Penyaringan daftar dokumen berdasarkan Saluran WhatsApp.
3. `03_whatsapp_inbox_page.png` — Halaman Kotak Masuk WhatsApp mereproduksi status kosong akibat temuan WF-019.
4. `04_document_review_page.png` — Form review dokumen WhatsApp (kartu keterangan pengirim, nilai keyakinan OCR, flag integritas).
5. `05_document_approved_ready_to_post.png` — Dokumen berpindah ke status `SIAP POSTING` setelah verifikasi pengguna.
6. `06_document_posted_gl.png` — Dokumen berhasil diposting ke Buku Besar Umum (`TRX-2026-000028`).
7. `07_kas_bank_page.png` — Dasbor keuangan mengonfirmasi *Integritas: SEIMBANG (Debet = Kredit)*.

Laporan PDF ringkas berformat resmi tersedia di:
- `docs/audits/E2E-TEST-20260920-1505/Financial_SaaS_J8_WhatsApp_Web_Review_Audit_Report.pdf`
- `dogfood-output/Financial_SaaS_J8_WhatsApp_Web_Review_Audit_Report.pdf`
