# Feature Specification: Document Intelligence & Financial Document Intake

**Feature Branch**: `005-document-intelligence-intake`
**Created**: 2026-08-30
**Status**: Draft / Specified
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)
- [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)
- [specs/003-core-operational-ui/spec.md](file:///c:/Projects/financial-saas/specs/003-core-operational-ui/spec.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)

---

## 1. Executive Summary

Modul **Document Intelligence & Financial Document Intake** berfungsi sebagai pintu masuk (*intake gateway*) bukti transaksi fisik dan digital bagi kontraktor Indonesia. Dokumen yang diunggah (bukti transfer bank, invoice vendor, kuitansi, nota lapangan, SPK, PO, BAST, surat jalan, rekening koran) diproses secara otomatis melalui ekstraksi berbasis OCR/Vision, normalisasi data, pencocokan entitas master (*Customer, Vendor, Project*), deteksi duplikasi, dan evaluasi tingkat keyakinan (*multi-dimensional confidence*).

Sistem menghasilkan **Kandidat Transaksi Terstruktur (Structured Transaction Candidate)** yang diajukan ke pengguna atau dialihkan ke Antrean Review (*Review Queue*) jika terdapat ambiguitas. **Sistem ini tidak memotong jalur validasi, otorisasi, atau mesin akuntansi.** Mesin akuntansi (*Accounting Engine*) terverifikasi pada Feature 002/003 tetap menjadi otoritas tunggal penentu pembukuan finansial.

---

## 2. User Personas & Actors

| Aktor | Saluran Akses | Tanggung Jawab Utama |
|---|---|---|
| **Operator Keuangan / Kasir Lapangan** | Web UI (Upload Form & Batch Intake) | Mengunggah nota belanja, bukti transfer bank, surat jalan, dan kuitansi operasional harian. |
| **Project Manager (PIC Lapangan)** | Web UI / Mobile Browser | Mengunggah dokumen proyek (SPK subkon, BAST kemajuan fisik, PO material proyek). |
| **Reviewer / Manajer Keuangan** | Web UI (Document Review Workspace) | Meninjau hasil ekstraksi data, memvalidasi pencocokan proyek/vendor, mengoreksi nilai, dan menyetujui kandidat transaksi. |
| **Hermes / Bot Ingest (Future Channel)** | REST API (Authenticated Ingest Endpoint) | Mengirimkan dokumen dan metadata dari WhatsApp/Email ke endpoint intake yang sama. |

---

## 3. Core Processing Lifecycle

```text
[Source Document Upload (Web/API)]
              │
              ▼
    1. SECURE INTAKE & VALIDATION (MIME type, size limit, virus/safe name)
              │
              ▼
    2. IMMUTABLE RAW STORAGE & SHA-256 HASHING
              │
              ├────────► [Exact File Duplicate Detected?] ──► Reject / Attach Reference
              ▼
    3. DOCUMENT CLASSIFICATION & DETECTION (21 Contract, Procurement, Payment, Project, Tax types)
              │
              ▼
    4. STRUCTURED DATA EXTRACTION (Provider-Agnostic Engine)
              │
              ▼
    5. FIELD NORMALIZATION (Dates, ISO Currency, Decimal Amounts, IDR Tax, Reference Numbers)
              │
              ▼
    6. DETERMINISTIC & FUZZY MATCHING (Counterparty, Project, PO/SPK, Invoice/Bill)
              │
              ▼
    7. MULTI-DIMENSIONAL CONFIDENCE EVALUATION
              │
              ├────────► [Low Confidence / Missing Project / Ambiguity?]
              │                   │
              │                   ▼
              │          [ROUTED TO REVIEW QUEUE (With audit flags)]
              │                   │
              │                   ▼
              │          [Human Verification & Correction]
              │                   │
              ▼                   ▼
    8. STRUCTURED TRANSACTION CANDIDATE GENERATION
              │
              ▼
    [EXISTING FINANCIAL ACCOUNTING ENGINE (Feature 002/003 Posting Rules)]
```

### Status Pemrosesan Dokumen
1. `UPLOADED`: Dokumen diterima dan divalidasi keamanannya.
2. `HASHED`: Hash SHA-256 dihitung; pemeriksaan duplikasi berkas selesai.
3. `EXTRACTING`: Proses OCR / ekstraksi visi sedang berlangsung secara asinkron.
4. `EXTRACTED`: Teks dan pasangan kunci-nilai (*key-value pairs*) berhasil diekstraksi ke format JSON skema ketat.
5. `MATCHING`: Sistem melakukan pencocokan entitas, proyek, dan dokumen referensi.
6. `REVIEW_REQUIRED`: Dokumen memerlukan tinjauan manusia (tingkat keyakinan rendah atau entitas tidak dikenal).
7. `READY_FOR_APPROVAL`: Seluruh data lengkap dan tingkat keyakinan tinggi; siap diajukan menjadi transaksi.
8. `PROCESSED`: Kandidat transaksi telah disetujui dan diteruskan ke mesin transaksi.
9. `FAILED`: Pemrosesan gagal (berkas rusak, terenkripsi, atau format tidak terbaca).

---

## 4. User Scenarios & Prioritized User Journeys

### User Story 1 - Unggah & Ekstraksi Bukti Transfer Bank (Priority: P1)
**Deskripsi**: Operator mengunggah tangkapan layar (*screenshot*) bukti transfer mobile banking (BCA, Mandiri, BRI, BNI) atau struk ATM. Sistem mengekstrak tanggal, jam, nominal, bank pengirim, bank penerima, nama penerima, nomor referensi, dan biaya admin, lalu menyajikannya sebagai kandidat transaksi tanpa langsung menganggapnya sebagai beban.

**Why this priority**: Bukti transfer adalah jenis dokumen paling sering (volume tertinggi) dalam operasional harian kontraktor.

**Independent Test**: Dapat diuji secara independen dengan mengunggah gambar bukti transfer BCA/Mandiri, memeriksa JSON hasil ekstraksi terstruktur, dan memastikan saldo rekening kas/bank terpetakan dengan benar.

**Acceptance Scenarios**:
1. **Given** Operator mengunggah gambar bukti transfer BCA senilai Rp 15.000.000,00 ke rekening PT Semen Perkasa,
   **When** Dokumen diproses,
   **Then** Sistem mengekstrak nominal `15000000.00`, tanggal transaksi, nama penerima `"PT Semen Perkasa"`, dan nomor referensi bank,
   **And** Sistem menyajikan kandidat transaksi pembayaran vendor dan mencocokkannya dengan vendor terdaftar tanpa memposting otomatis.
2. **Given** Bukti transfer yang diunggah identik secara biner (SHA-256) dengan berkas yang sudah pernah diunggah,
   **When** Dokumen di-intake,
   **Then** Sistem menandai dokumen sebagai duplikat fisik (`DUPLICATE_FILE`) dan menghentikan pembuatan transaksi ganda.

---

### User Story 2 - Ekstraksi Invoice Vendor & Pencocokan Proyek (Priority: P1)
**Deskripsi**: Operator mengunggah berkas PDF/Foto invoice/nota dari vendor material (misal: Toko Besi Jaya) yang mencantumkan nama proyek atau nomor SPK. Sistem mengekstrak rincian item, PPN, nomor invoice, dan secara otomatis mencocokkannya dengan Proyek dan Vendor yang terdaftar.

**Why this priority**: Mengotomatisasi pencatatan tagihan utang (AP) dan alokasi biaya proyek langsung dari dokumen sumber.

**Independent Test**: Mengunggah PDF tagihan supplier yang memuat nomor SPK `SPK-2026-001`, memvalidasi pencocokan otomatis ke proyek terkait, dan memverifikasi rincian 9 kategori biaya.

**Acceptance Scenarios**:
1. **Given** Invoice supplier memuat teks `"Untuk Proyek Renovasi Gedung A (PRJ-2026-01)"`,
   **When** Ekstraksi selesai,
   **Then** Sistem mengenali `project_id` yang cocok dengan tingkat keyakinan tinggi (`project_confidence >= 0.90`) dan mengusulkan kategori biaya `MAT` (Material & Bahan).
2. **Given** Invoice supplier tidak menyebutkan nama atau kode proyek apapun,
   **When** Ekstraksi selesai,
   **Then** Sistem menetapkan `project_id = NULL`, menandai bendera `PROJECT_UNKNOWN`, dan mengarahkan dokumen ke Antrean Review (tidak menebak proyek).

---

### User Story 3 - Workspace Tinjauan Dokumen & Koreksi Terverifikasi (Priority: P2)
**Deskripsi**: Reviewer membuka layar peninjauan dokumen bersisi ganda (*side-by-side view*): dokumen asli di sisi kiri dan formulir data hasil ekstraksi di sisi kanan, lengkap dengan indikator keyakinan (*confidence badge*), alasan bendera review, dan tombol koreksi.

**Why this priority**: Memenuhi prinsip konstitusi bahwa manusia memegang kendali atas ambiguitas data finansial.

**Independent Test**: Membuka dokumen berstatus `REVIEW_REQUIRED`, mengoreksi nama vendor yang salah baca, dan mengklik "Setujui & Buat Transaksi".

**Acceptance Scenarios**:
1. **Given** Dokumen memiliki bendera `OCR_LOW_CONFIDENCE` pada tanggal nota,
   **When** Reviewer mengoreksi tanggal pada form sisi kanan dan menyimpannya,
   **Then** Dokumen asli tetap utuh (*immutable*), data koreksi tersimpan pada riwayat audit (*audit trail*), dan status berubah menjadi `READY_FOR_APPROVAL`.

---

### User Story 4 - Intake Dokumen Proyek & Kontrak (Priority: P3)
**Deskripsi**: Project Manager mengunggah dokumen BAST (Berita Acara Serah Terima), Surat Jalan material, atau SPK subkon. Sistem mengklasifikasikan tipe dokumen, mengekstrak nomor dokumen, tanggal berita acara, dan mengaitkannya ke proyek induk sebagai arsip bukti otentik.

**Why this priority**: Menghubungkan pembuktian fisik lapangan dengan histori proyek.

**Independent Test**: Mengunggah Surat Jalan, memeriksa klasifikasi tipe `SURAT_JALAN`, dan memastikan dokumen terhubung pada daftar dokumen proyek.

---

## 5. Edge Cases & Boundary Handling

1. **Gambar Buram / Tidak Terbaca (Unreadable Image)**: Sistem menandai status `FAILED` dengan pesan ramah *"Kualitas gambar terlalu rendah atau teks tidak terdeteksi"*, menyimpan berkas asli, dan menyediakan tombol unggah ulang.
2. **PDF Terproteksi Kata Sandi (Password-Protected PDF)**: Sistem mendeteksi enkripsi berkas, menolak pemrosesan otomatis, dan meminta pengguna mengunggah berkas tanpa proteksi kata sandi.
3. **Dokumen Multi-Halaman (Multi-Page PDF)**: Sistem mengekstrak seluruh halaman, mengagregasikan subtotal/total pada halaman rekapitulasi, dan menjaga urutan halaman.
4. **Mata Uang Asing (Foreign Currency)**: Jika terdeteksi simbol selain IDR (misal: USD, EUR), sistem menetapkan kode mata uang pada kandidat dan menandai bendera `ACCOUNT_REVIEW` untuk konfirmasi kurs.
5. **Kuitansi Tulisan Tangan (Handwritten Receipts)**: Teks dengan skor keyakinan rendah secara otomatis memicu bendera `OCR_LOW_CONFIDENCE` dan mewajibkan verifikasi manual sebelum transaksi dapat dibuat.
6. **Perbedaan Nilai Subtotal + Pajak $\neq$ Total**: Jika hasil ekstraksi angka rincian tidak klop dengan total nota, sistem memasang bendera `AMOUNT_MISMATCH`.

---

## 6. Functional Requirements

### 6.1. Intake & Perlindungan Dokumen Sumber
- **FR-001**: Sistem WAJIB mendukung unggah berkas melalui Web UI dan REST API dengan pembatasan tipe MIME: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `application/pdf` dengan batas ukuran maksimal 25 MB per berkas.
- **FR-002**: Berkas asli yang diunggah WAJIB disimpan secara **immutable** (tidak dapat diubah, ditimpa, atau dihapus secara destruktif).
- **FR-003**: Sistem WAJIB menghitung hash kriptografis **SHA-256** dari setiap berkas saat pertama kali diterima.
- **FR-004**: Sistem WAJIB menyimpan metadata lengkap: `id`, `organization_id`, `original_filename`, `mime_type`, `file_size_bytes`, `file_hash_sha256`, `source_channel` (`WEB`, `API`), `uploaded_by`, `uploaded_at`, dan `sender_metadata`.
- **FR-005**: Jika berkas dengan hash SHA-256 yang sama telah ada dalam organisasi, sistem WAJIB mendeteksi duplikat instan (`EXACT_FILE_DUPLICATE`) dan mencegah pembuatan kandidat transaksi kembar.

### 6.2. Klasifikasi Tipe Dokumen (21 Supported Types)
- **FR-006**: Sistem WAJIB mengklasifikasikan dokumen ke dalam salah satu tipe terstandarisasi berikut:
  - **KONTRAK**: `PO_CUSTOMER`, `SPK`, `CONTRACT`, `VARIATION_ORDER`
  - **PENGADAAN**: `PURCHASE_ORDER`, `QUOTATION`, `VENDOR_INVOICE`, `SUBCONTRACT_AGREEMENT`
  - **PEMBAYARAN**: `TRANSFER_PROOF`, `RECEIPT`, `BANK_STATEMENT`, `PETTY_CASH_PROOF`
  - **PROYEK**: `SURAT_JALAN`, `BAST`, `PROGRESS_REPORT`, `TIMESHEET`
  - **TAGIHAN KLIEN**: `CUSTOMER_INVOICE`, `CUSTOMER_RECEIPT`
  - **PERPAJAKAN**: `TAX_INVOICE` (Faktur Pajak), `WITHHOLDING_DOCUMENT` (Bukti Potong PPh 23/4 ayat 2), `OTHER_TAX_DOCUMENT`
  - **LAIN-LAIN**: `UNKNOWN` (jika tidak dapat diidentifikasi secara meyakinkan).

### 6.3. Ekstraksi Data Terstruktur & Normalisasi
- **FR-007**: Ekstraksi WAJIB menggunakan arsitektur *provider-agnostic* (dapat mendukung PDF parser lokal, OCR engine, dan vision model tanpa ketergantungan permanen pada satu vendor AI tertentu).
- **FR-008**: Output ekstraksi WAJIB divalidasi terhadap skema JSON terstruktur ketat (*strict structured schema*). Teks bebas tak tervalidasi dilarang dijadikan data finansial.
- **FR-009**: Bidang data (*fields*) yang diekstrak meliputi:
  - Nomor Dokumen / Nomor Invoice / Nomor SPK / Nomor BAST
  - Tanggal Transaksi & Tanggal Jatuh Tempo (*Due Date*)
  - Nama Pihak Penerbit (Vendor / Customer / Kontraktor)
  - Nama Pihak Penerima / Pembeli
  - Deskripsi / Uraian Transaksi
  - Nilai Nominal: Subtotal, Diskon, PPN, PPh, Biaya Admin, dan Total Akhir (dalam format `Decimal`)
  - Detail Bukti Transfer: Bank Asal, Bank Tujuan, No. Rekening, Nama Rekening Tujuan, No. Referensi Transfer
  - Nomor Proyek / Rujukan Proyek yang tertera pada nota.
- **FR-010**: Sistem DILARANG memalsukan atau mengarang (*hallucinate*) data yang tidak tercantum pada dokumen sumber.

### 6.4. Evaluasi Tingkat Keyakinan (Multi-Dimensional Confidence)
- **FR-011**: Sistem WAJIB menghasilkan skor keyakinan terpisah ($0.00 - 1.00$) untuk:
  - `ocr_confidence`: Kualitas pembacaan karakter fisik/teks
  - `document_type_confidence`: Keyakinan klasifikasi tipe dokumen
  - `entity_confidence`: Keyakinan pencocokan vendor/pelanggan
  - `project_confidence`: Keyakinan pencocokan proyek
  - `amount_confidence`: Keyakinan ekstraksi nilai nominal
- **FR-012**: Jika salah satu bidang penting (nominal, tanggal, entitas, proyek) memiliki skor keyakinan $< 0.85$, sistem WAJIB mengarahkan dokumen ke Antrean Review dengan bendera `OCR_LOW_CONFIDENCE`.

### 6.5. Pencocokan Entitas & Proyek (Matching Engine)
- **FR-013**: Sistem WAJIB mencoba mencocokkan nama penerbit/penerima dengan master `Counterparty` (Customer/Vendor) melalui strategi:
  - *Exact Match*: Kesesuaian nama persis atau nomor rekening/NPWP terdaftar.
  - *Fuzzy Match*: Kesamaan fonetik/teks di atas ambang batas 85%.
  - *Unknown*: Jika tidak cocok, sistem memasang bendera `VENDOR_UNKNOWN` atau `CUSTOMER_UNKNOWN`. Sistem DILARANG membuat entitas master baru secara otomatis tanpa persetujuan pengguna.
- **FR-014**: Sistem WAJIB mencoba mencocokkan dokumen ke master `Project` berdasarkan:
  - Kode Proyek (`project_code`)
  - Nomor SPK / PO Pelanggan (`po_spk_no`)
  - Nama Proyek / Nama Customer
  - Jika tidak ada kecocokan pasti, sistem memasang bendera `PROJECT_UNKNOWN` (dilarang menebak).

### 6.6. Deteksi Duplikasi Bisnis (Suspected Duplicate Detection)
- **FR-015**: Sistem WAJIB mendeteksi potensi duplikasi transaksi bisnis (*Business Duplicate*) berdasarkan kombinasi:
  - Nomor referensi / nomor invoice yang sama dari counterparty yang sama
  - Tanggal transaksi sama $\pm 1$ hari dengan nominal persis sama dan counterparty sama
- **FR-016**: Dokumen yang terindikasi duplikat bisnis dipasangi bendera `DUPLICATE_SUSPECTED` dan dilarang diposting secara otomatis.

### 6.7. Pembentukan Kandidat Transaksi & Integrasi Review Queue
- **FR-017**: Sistem Document Intelligence WAJIB mengusulkan objek `TransactionCandidate` terstruktur yang mencakup:
  - Usulan `TransactionType` (misal: `PAY_VENDOR_BILL`, `DIRECT_PURCHASE`, `CUSTOMER_PAYMENT`)
  - Usulan `Counterparty` & `Project`
  - Usulan Akun Kas/Bank (`PaymentAccount`) berdasarkan petunjuk rekening transfer
  - Usulan Kategori Biaya (misal: `MAT`, `SUB`, `LAB`, `OPEX`)
- **FR-018 (Invarian Akuntansi)**: AI dan modul ekstraksi DILARANG KERAS menentukan atau menghasilkan jurnal debet/kredit sepihak. Seluruh pembukuan wajib mengikuti *Posting Rules* otoritatif pada backend.
- **FR-019**: Dokumen bermasalah dipasangi satu atau lebih bendera pada Antrean Review:
  `OCR_LOW_CONFIDENCE`, `DUPLICATE_SUSPECTED`, `PROJECT_UNKNOWN`, `VENDOR_UNKNOWN`, `CUSTOMER_UNKNOWN`, `AMOUNT_MISMATCH`, `DATE_MISMATCH`, `TAX_REVIEW`, `ACCOUNT_REVIEW`.

### 6.8. Workspace Peninjauan & Koreksi Pengguna
- **FR-020**: UI WAJIB menyediakan antarmuka *side-by-side* yang menampilkan pratinjau dokumen sumber (PDF viewer / Image zoom) bersisian dengan formulir data ekstraksi dan daftar bendera review.
- **FR-021**: Pengguna berwenang dapat mengoreksi data ekstraksi, memilih proyek/vendor yang benar, dan menyetujui kandidat transaksi.
- **FR-022**: Setiap koreksi pengguna WAJIB dicatat dalam tabel riwayat audit (`AuditLog`) dengan merekam data sebelum dan sesudah perubahan beserta identitas pengguna dan waktu perubahan.

---

## 7. Key Data Entities

```text
Document (Physical/Digital Asset)
  ├── id (UUID)
  ├── organization_id (UUID)
  ├── file_hash_sha256 (VARCHAR 64, Indexed)
  ├── original_filename (VARCHAR 255)
  ├── storage_path (VARCHAR 500)
  ├── mime_type (VARCHAR 100)
  ├── file_size_bytes (BIGINT)
  ├── document_type (DocumentType Enum)
  ├── processing_status (DocumentProcessingStatus Enum)
  ├── source_channel (SourceChannel Enum: WEB, API)
  ├── confidence_scores (JSONB)
  ├── extracted_data (JSONB - Validated Structured Fields)
  ├── matching_results (JSONB - Matched Project/Counterparty/Invoice IDs)
  ├── candidate_transaction (JSONB - Proposed Transaction Parameters)
  ├── review_flags (List of TransactionReviewFlag)
  ├── created_at (TIMESTAMP)
  └── updated_at (TIMESTAMP)
```

---

## 8. Success Criteria & Measurable Outcomes

- **SC-001 (Immutabilitas)**: 100% berkas dokumen sumber yang diunggah tersimpan secara permanen dan tidak dapat diubah atau ditimpa.
- **SC-002 (Integritas Duplikasi)**: 100% berkas yang identik secara biner (SHA-256) terdeteksi sebelum proses ekstraksi dimulai.
- **SC-003 (Keamanan Skema Ekstraksi)**: 100% data ekstraksi yang diteruskan ke sistem transaksi telah tervalidasi skema tipenya (tidak ada string bebas tak terstruktur).
- **SC-004 (Zero Silent Guessing)**: 0% transaksi dengan proyek atau vendor tak dikenal dibuat secara otomatis tanpa melewati Antrean Review.
- **SC-005 (Auditability)**: 100% koreksi pengguna terhadap data ekstraksi tercatat dalam log audit yang mencantumkan nilai awal dan nilai koreksi.
- **SC-006 (Idempotensi)**: Percobaan ulang (*retry*) ekstraksi pada dokumen yang sama tidak menghasilkan duplikasi entitas transaksi.
- **SC-007 (Isolasi Multi-Tenant)**: 100% akses unggah, pemrosesan, dan pembacaan dokumen terisolasi ketat berdasarkan `organization_id`.

---

## 9. Assumptions & Dependencies

1. **Format File yang Didukung**: Pengguna mengunggah gambar nota/invoice yang memiliki orientasi wajar dan resolusi minimal 300 DPI untuk kualitas ekstraksi optimal.
2. **Kemandirian Penyedia OCR/AI**: Arsitektur ekstraksi dirancang modular melalui antarmuka *Adapter Pattern*, sehingga engine ekstraksi lokal, cloud vision, atau LLM vision dapat dipertukarkan tanpa mengubah domain model.
3. **Kerahasiaan Dokumen**: Berkas disimpan dalam direktori terisolasi per organisasi dengan hak akses yang diamankan oleh backend FastAPI.
4. **Ketergantungan Backend**: Modul ini memanfaatkan model master data Feature 002 (`Project`, `Counterparty`, `Transaction`, `TransactionReviewFlag`) dan alur posting Feature 003.

---

## 10. Explicit Out-of-Scope

- Integrasi langsung bot WhatsApp / Hermes (akan dikembangkan pada fitur terpisah; spesifikasi ini hanya menyediakan REST API intake yang kompatibel).
- Penilaian atau keputusan sengketa pajak secara otomatis.
- Pembuatan atau penyesuaian aturan akuntansi secara mandiri oleh AI.
- Pelatihan model (*model training / fine-tuning*) menggunakan data perusahaan.
- Penggajian karyawan (*payroll*).
