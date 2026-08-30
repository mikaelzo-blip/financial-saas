# Feature Specification: WhatsApp Operational Messaging Integration

**Feature Branch**: `007-whatsapp-integration`  
**Status**: SPECIFIED & CLARIFIED  
**Created**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)
- [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)
- [specs/005-document-intelligence-intake/spec.md](file:///c:/Projects/financial-saas/specs/005-document-intelligence-intake/spec.md)
- [specs/006-hermes-automation-integration/spec.md](file:///c:/Projects/financial-saas/specs/006-hermes-automation-integration/spec.md)

---

## 1. Executive Summary

Modul **WhatsApp Operational Messaging Integration** menyediakan saluran perpesanan operasional bagi asisten otomasi Hermes untuk berinteraksi dengan pengguna lapangan (tukang, mandor, kasir proyek, PM, dan manajer keuangan) melalui WhatsApp. Dokumen fisik (foto nota, kuitansi, bukti transfer bank, surat jalan, invoice) dan pesan teks yang dikirimkan via WhatsApp diterima oleh *WhatsApp Ingest Adapter*, divalidasi, dan diteruskan ke asisten Hermes melalui API SaaS terautentikasi untuk diproses oleh modul *Document Intelligence (Feature 005)*.

### Architectural Invariants & Non-Negotiable Boundaries:
1. **WhatsApp BUKAN System of Record**: Seluruh data tersimpan secara permanen pada database relasional SaaS; WhatsApp hanyalah kanal transmisi pesan.
2. **WhatsApp & Hermes BUKAN Mesin Akuntansi**: Tidak boleh menentukan akun debit/kredit, tidak boleh memposting jurnal, dan tidak boleh memotong Antrean Review (*Review Queue*).
3. **Bukan Klien Langsung Database**: WhatsApp adapter dan Hermes dilarang keras membuka koneksi langsung ke PostgreSQL database. Seluruh interaksi wajib melalui HTTPS API SaaS terautentikasi.
4. **Bukti Transfer Bukan Otomatis Beban**: Bukti transfer yang diunggah via WhatsApp tidak pernah otomatis menjadi beban (*expense*) tanpa verifikasi substansi ekonomi.
5. **Provider-Agnostic Abstraction**: Arsitektur adapter WhatsApp diabstraksikan sepenuhnya sehingga implementasi dan pengujian dapat berjalan menggunakan mock/simulator lokal tanpa ketergantungan pada akun berbayar pihak ketiga (Meta Cloud API, Twilio, dll).

---

## 2. Clarifications

### Session 2026-08-30

- **Q01: Arsitektur Integrasi WhatsApp & Hermes** → **Decision**: Alur data wajib mengikuti: $\text{WhatsApp} \to \text{WhatsApp Adapter} \to \text{Hermes Client} \to \text{SaaS API} \to \text{Document Intelligence / Review Queue}$. Tidak ada jalan pintas dari WhatsApp langsung ke database atau jurnal.
- **Q02: Identifikasi & Autentikasi Pengirim (Sender Mapping)** → **Decision**: Setiap nomor WhatsApp (`wa_id` / MSISDN berformat E.164, contoh `+6281234567890`) dipetakan ke `User` dan `Organization` pada backend SaaS melalui entitas `WhatsAppSenderMapping`. Pesan dari nomor yang belum terdaftar menerima balasan instruksi verifikasi/pendaftaran dan tidak diproses ke transaksi.
- **Q03: Penanganan Dokumen dan Media WhatsApp** → **Decision**: Foto (JPEG/PNG) dan dokumen (PDF) diunduh secara aman dari endpoint media provider menggunakan token terenkripsi, divalidasi MIME type dan batasan ukuran (maksimal 25 MB), kemudian dikirimkan secara streaming ke endpoint intake Feature 005 (`/api/v1/hermes/documents/upload`).
- **Q04: Teks Pendamping / Captioning** → **Decision**: Teks caption yang menyertai gambar/PDF (contoh: *"Nota semen 50 sak proyek Ruko Thamrin"*) disertakan sebagai `source_metadata.caption` untuk memperkaya ekstraksi data dan petunjuk pencocokan (*matching hint*) tanpa menggantikan bukti fisik dokumen.
- **Q05: Idempotensi Webhook & Pencegahan Duplikasi** → **Decision**: Setiap pesan masuk memiliki `wamid` (WhatsApp Message ID) yang dicatat pada *idempotency cache*. Pengiriman ulang webhook dengan `wamid` yang sama akan menghasilkan status HTTP 200 tanpa memproses ulang file atau membuat dokumen ganda.
- **Q06: Keamanan Webhook & Verifikasi Signature** → **Decision**: Webhook publik memvalidasi handshake token (`hub.verify_token`) dan memverifikasi HMAC-SHA256 signature (`X-Hub-Signature-256`) menggunakan secret webhook sebelum memproses isi payload.
- **Q07: Notifikasi & Respon Status ke Pengguna** → **Decision**: Hermes mengirimkan pesan balasan interaktif status operasional: (1) Konfirmasi penerimaan dokumen (`DOC-xxxx`), (2) Notifikasi hasil ekstraksi, dan (3) Permintaan klarifikasi jika dokumen ambigu/membutuhkan konfirmasi proyek.
- **Q08: Permintaan Klarifikasi Aman (Safe Review Prompts)** → **Decision**: Jika OCR mendeteksi proyek atau vendor ambigu, Hermes dapat mengirimkan pertanyaan pilihan ganda via WhatsApp (contoh: *"Ketik 1 untuk Proyek Thamrin, 2 untuk Gudang Cikarang"*). Jawaban pengirim diteruskan ke API Review Queue untuk memperbarui kandidat tanpa memposting jurnal secara otomatis.
- **Q09: Rate Limiting & Perlindungan DoS** → **Decision**: Diterapkan pembatasan laju pengiriman (*rate limit*) per nomor telepon (maksimal 20 pesan/menit) dan per organisasi untuk mencegah banjir pesan atau serangan brute force.
- **Q10: Abstraksi Provider & Pengujian Tanpa Akun Berbayar** → **Decision**: Modul mendefinisikan interface `WhatsAppProvider` dengan implementasi `MockWhatsAppProvider` untuk unit/integration test dan `MetaCloudWhatsAppProvider` untuk integrasi produksi masa depan. Tidak ada keharusan mengaktifkan akun berbayar saat fase pengembangan.

---

## 3. User Personas & Actors

| Aktor | Saluran | Peran & Interaksi Utama |
|---|---|---|
| **Mandor / Kasir Lapangan** | WhatsApp Chat | Mengirimkan foto nota belanja material, bensin, kuitansi upah, dan bukti transfer bank dari lapangan beserta caption proyek. |
| **Project Manager (PIC Proyek)** | WhatsApp Chat | Menerima notifikasi berkala status dokumen proyek dan membalas konfirmasi nomor proyek untuk nota yang belum jelas. |
| **Manajer Keuangan / Owner** | WhatsApp Chat & Web UI | Menerima ringkasan notifikasi antrean review dokumen berisiko tinggi; melakukan persetujuan akhir tetap melalui Web SaaS. |
| **Hermes WhatsApp Adapter** | Background Service / Webhook | Menerima webhook dari provider, mengunduh media, memverifikasi tanda tangan, dan memanggil API SaaS. |

---

## 4. User Scenarios & Testing

### User Story 1 — Penerimaan Bukti Transaksi Media dari WhatsApp (Priority: P1) 🎯 MVP

Sebagai kasir/mandor lapangan, saya ingin mengirimkan foto nota fisik atau bukti transfer bank melalui WhatsApp disertai caption keterangan, sehingga dokumen masuk secara otomatis ke antrean intake SaaS tanpa perlu membuka laptop.

**Why this priority**: Merupakan inti fungsionalitas operasional lapangan; 80% bukti transaksi kontraktor berasal dari foto nota di WhatsApp.

**Independent Test**: Kirim payload webhook simulasi WhatsApp berisi pesan gambar nota semen beserta caption "Nota 20 sak semen Proyek Ruko Thamrin" dari nomor terdaftar. Sistem mengunduh gambar, mengirim ke endpoint `/api/v1/hermes/documents/upload`, menyimpan metadata caption, dan membalas pesan WhatsApp dengan nomor resi dokumen.

**Acceptance Scenarios**:
1. **Given** nomor WhatsApp `+6281234567890` terdaftar pada PT Konstruksi Makmur, **When** pengguna mengirim foto nota belanja beserta caption, **Then** adapter mengunduh media, memanggil API Hermes, dan mengembalikan pesan *"✅ Nota diterima [DOC-001]. Sedang diproses OCR."*
2. **Given** nomor WhatsApp yang belum terdaftar di sistem, **When** mengirimkan pesan/media, **Then** adapter membalas *"Nomor Anda belum terdaftar pada sistem keuangan. Silakan hubungi Administrator organisasi Anda."* dan tidak membuat dokumen di database.
3. **Given** file gambar yang identik (SHA-256 sama) dikirimkan dua kali, **When** webhook kedua masuk, **Then** sistem mendeteksi duplikasi dokumen dan membalas *"Dokumen ini telah diunggah sebelumnya [DOC-001]."*

---

### User Story 2 — Konfirmasi Klarifikasi Interaktif via WhatsApp (Priority: P2)

Sebagai mandor lapangan, saya ingin menerima pertanyaan singkat jika nota saya tidak terbaca jelas nama proyeknya dan menjawabnya langsung di WhatsApp, sehingga kasir kantor tidak perlu menelpon ulang.

**Why this priority**: Mengurangi friksi pada antrean review (*Review Queue*) untuk ketidaklengkapan data lapangan yang sepele (seperti nama proyek yang tidak tertulis pada nota belanja toko kelontong).

**Independent Test**: Dokumen dengan status `REVIEW_REQUIRED` (alasan: `PROJECT_AMBIGUOUS`) memicu Hermes mengirim WhatsApp berformat pilihan nomor proyek. Balasan angka dari pengguna memperbarui field `project_id` pada kandidat dokumen melalui API Review SaaS.

**Acceptance Scenarios**:
1. **Given** dokumen `DOC-002` masuk Review Queue karena nama proyek tidak ditemukan, **When** Hermes mengirim pesan *"Nota Rp 150.000 tidak memiliki info proyek. Balas 1 untuk [Ruko Thamrin] atau 2 untuk [Renovasi BSD]"*, dan pengguna membalas *"1"*, **Then** sistem memperbarui kandidat transaksi dengan Proyek Ruko Thamrin dan membalas *"Terima kasih, proyek telah diperbarui."*
2. **Given** pengguna membalas dengan format yang tidak valid (contoh: *"Halo mas"*), **When** balasan diproses, **Then** sistem merespon ramah meminta balasan angka pilihan yang sesuai.

---

### User Story 3 — Status Inquiry & Ringkasan Operasional Lapangan (Priority: P3)

Sebagai Project Manager, saya ingin mengirimkan perintah teks singkat seperti *"status proyek"* atau *"antrean nota"* ke WhatsApp bot untuk mengetahui jumlah nota pending yang belum direview.

**Why this priority**: Memberikan visibilitas cepat bagi manajemen tanpa harus login ke dashboard web saat berada di area proyek.

**Independent Test**: Kirim pesan teks `"RINGKASAN"` dari nomor PM terdaftar. Sistem mengueri API ringkasan operasional dan mengembalikan teks ringkasan jumlah dokumen diproses dan menunggu persetujuan.

**Acceptance Scenarios**:
1. **Given** pengguna dengan peran `PROJECT_MANAGER`, **When** mengirim pesan `"STATUS"`, **Then** bot mengembalikan informasi jumlah dokumen proyek aktif dan dokumen pending review.

---

## 5. Functional Requirements

### Webhook & Provider Ingestion
- **FR-001**: Sistem WAJIB menyediakan endpoint webhook publik `POST /api/v1/integrations/whatsapp/webhook` yang memproses payload pesan masuk dari provider WhatsApp.
- **FR-002**: Webhook WAJIB memvalidasi handshake GET request dengan verifikasi `hub.mode == "subscribe"` dan `hub.verify_token` sesuai konfigurasi tenant/sistem.
- **FR-003**: Webhook WAJIB memvalidasi tanda tangan kriptografis `X-Hub-Signature-256` pada setiap POST request menggunakan HMAC-SHA256. Request dengan signature tidak valid WAJIB ditolak dengan status HTTP 401 Unauthorized.
- **FR-004**: Sistem WAJIB mencatat `wamid` (WhatsApp Message ID) ke dalam store idempotensi. Jika `wamid` telah diproses dalam rentang 24 jam terakhir, sistem WAJIB merespon HTTP 200 OK seketika tanpa melakukan pemrosesan ulang (*idempotent deduplication*).

### Media Handling & Security
- **FR-005**: Sistem WAJIB mendukung tipe media: Gambar (`image/jpeg`, `image/png`, `image/webp`) dan Dokumen (`application/pdf`).
- **FR-006**: Media WAJIB diunduh melalui koneksi HTTPS terautentikasi ke API provider, divalidasi ukuran file (maksimal 25 MB), dan disanitasi nama filenya.
- **FR-007**: Unduhan media yang gagal atau URL kedaluwarsa WAJIB dicatat dengan status `DOWNLOAD_FAILED` dan memicu pesan balasan meminta pengiriman ulang dokumen.

### Multi-Tenant Mapping & User Resolution
- **FR-008**: Sistem WAJIB mencocokkan nomor WhatsApp pengirim (`from`) dengan tabel `WhatsAppSenderMapping` untuk menentukan `organization_id` dan `user_id`.
- **FR-009**: Jika nomor pengirim tidak terdaftar, sistem WAJIB mengabaikan pemrosesan dokumen finansial dan mengirimkan satu pesan balasan penolakan aman (*Unregistered Sender Notice*).
- **FR-010**: Sistem WAJIB mendukung pemetaan nomor telepon yang dinonaktifkan (`is_active = false`), di mana pesan dari nomor nonaktif otomatis ditolak.

### SaaS & Hermes Integration Boundary
- **FR-011**: WhatsApp Adapter WAJIB berinteraksi dengan SaaS backend murni melalui client Hermes terautentikasi (`HermesApiClient` dengan `Bearer HERMES_AGENT_TOKEN`).
- **FR-012**: Setiap dokumen yang diunggah WAJIB menyertakan header `Idempotency-Key` bernilai unik turunan dari `wamid` (contoh: `wa-msg-{wamid}`) dan `source_channel="WHATSAPP"`.
- **FR-013**: Caption teks dari pesan WhatsApp WAJIB disertakan ke dalam `source_metadata` dokumen sebagai petunjuk kontekstual OCR (*contextual matching hint*).
- **FR-014**: WhatsApp Adapter DILARANG KERAS membuka koneksi database langsung, mengimpor model SQLAlchemy selain untuk adapter mapping, atau mengeksekusi perintah SQL.

### Outbound Messaging & Interactive Replies
- **FR-015**: Sistem WAJIB memiliki layanan pengiriman pesan keluar (*Outbound Messaging Service*) yang mengirimkan notifikasi teks dan pesan interaktif tombol/angka.
- **FR-016**: Respon status penerimaan dokumen WAJIB dikirimkan kembali ke nomor pengirim dalam waktu $\le 5$ detik setelah dokumen diterima oleh API intake.
- **FR-017**: Jika pemrosesan dokumen menghasilkan kebutuhan klarifikasi (*Clarification Prompt*), sistem WAJIB mengirimkan pesan terstruktur berisi ID referensi dokumen dan pilihan jawaban yang valid.
- **FR-018**: Balasan pengguna atas klarifikasi WAJIB divalidasi terhadap sesi klarifikasi aktif (`WhatsAppClarificationSession`) dan diteruskan ke API Review Queue SaaS.

### Reliability, Rate Limiting & Audit
- **FR-019**: Sistem WAJIB menerapkan rate limiting maksimal 20 pesan per menit per nomor WhatsApp pengirim. Pesan yang melebihi batas WAJIB dibuang dengan respon peringatan throttling.
- **FR-020**: Seluruh interaksi pesan masuk dan keluar WAJIB dicatat dalam tabel `WhatsAppMessageLog` yang terisolasi per organisasi dengan mencatat `wamid`, nomor pengirim, tipe pesan, status pengiriman, dan referensi dokumen terkait.
- **FR-021**: Seluruh data sensitif (seperti token akses provider) WAJIB disimpan dalam environment configuration terenkripsi dan tidak boleh tercatat dalam plain text pada log aplikasi.

---

## 6. Key Entities

1. **WhatsAppSenderMapping**:
   - `id`: UUID (Primary Key)
   - `organization_id`: UUID (Foreign Key ke `Organization`)
   - `user_id`: UUID (Foreign Key ke `User`)
   - `phone_number`: String (E.164 format, e.g. `+6281234567890`, Unique)
   - `display_name`: String
   - `role_in_org`: Enum (`OPERATOR`, `PROJECT_MANAGER`, `FINANCE_MANAGER`)
   - `is_active`: Boolean
   - `created_at` / `updated_at`: Timestamp

2. **WhatsAppMessageLog**:
   - `id`: UUID (Primary Key)
   - `organization_id`: UUID
   - `wamid`: String (WhatsApp Message ID, Unique per tenant)
   - `direction`: Enum (`INBOUND`, `OUTBOUND`)
   - `phone_number`: String
   - `message_type`: Enum (`TEXT`, `IMAGE`, `DOCUMENT`, `INTERACTIVE_REPLY`)
   - `raw_text`: String (Optional, sanitized)
   - `media_mime_type`: String (Optional)
   - `media_size_bytes`: Integer (Optional)
   - `hermes_submission_id`: UUID (Optional reference)
   - `document_id`: UUID (Optional reference ke `Document`)
   - `delivery_status`: Enum (`RECEIVED`, `PROCESSING`, `DELIVERED`, `FAILED`, `REJECTED`)
   - `error_message`: String (Optional)
   - `created_at`: Timestamp

3. **WhatsAppClarificationSession**:
   - `id`: UUID (Primary Key)
   - `organization_id`: UUID
   - `phone_number`: String
   - `document_id`: UUID (Reference to `Document` in Review Queue)
   - `question_type`: Enum (`SELECT_PROJECT`, `CONFIRM_AMOUNT`, `SELECT_CATEGORY`)
   - `options_payload`: JSONB (Mapping number keys to Entity UUIDs)
   - `expires_at`: Timestamp (Default 24 hours)
   - `status`: Enum (`PENDING`, `ANSWERED`, `EXPIRED`)
   - `created_at`: Timestamp

---

## 7. Success Criteria

- **SC-001**: 100% pesan masuk dari nomor terdaftar berhasil diteruskan ke API Hermes dengan `Idempotency-Key` yang stabil; 0% duplikasi tercatat saat webhook dikirim berulang.
- **SC-002**: 100% media gambar (JPEG, PNG) dan dokumen (PDF) berukuran $\le 25$ MB berhasil diunduh dan diteruskan ke pipeline ekstraksi Feature 005.
- **SC-003**: 0 panggilan database langsung dari modul WhatsApp adapter; seluruh integrasi mematuhi prinsip boundary API-first.
- **SC-004**: Waktu respon penerimaan webhook hingga pengiriman pesan konfirmasi awal $\le 3$ detik pada kondisi jaringan normal.
- **SC-005**: 100% nomor tidak terdaftar ditolak secara anggun tanpa membuat record dokumen di database atau membocorkan data internal organisasi lain.
- **SC-006**: Seluruh test suite dapat dijalankan secara mandiri dalam mode CI/CD menggunakan `MockWhatsAppProvider` tanpa memerlukan token Meta Business aktif atau koneksi internet eksternal.
- **SC-007**: 0 transaksi otomatis terposting ke buku besar langsung dari pesan WhatsApp tanpa melalui verifikasi akuntansi yang sah.

---

## 8. Provider Prerequisites (Future Deployment)

Untuk menghubungkan adapter ini ke WhatsApp Cloud API resmi di lingkungan produksi, hal-hal berikut merupakan prasyarat eksternal yang disiapkan pada saat go-live:
1. **Meta for Developers Account & Business Manager**: Akun terverifikasi dengan App Type *Business*.
2. **WhatsApp Business Account (WABA)**: Nomor telepon bisnis khusus yang belum terhubung dengan aplikasi WhatsApp personal.
3. **Webhook Callback URL & Verify Token**: Domain HTTPS publik terdaftar (contoh: `https://api.kontraktor-saas.com/api/v1/integrations/whatsapp/webhook`).
4. **System User Permanent Access Token**: Token dengan permission `whatsapp_business_messaging` dan `whatsapp_business_management`.
5. **Konfigurasi Environment**:
   - `WHATSAPP_PROVIDER`: `meta` (atau `mock` untuk dev/testing)
   - `WHATSAPP_VERIFY_TOKEN`: Token rahasia handshake webhook
   - `WHATSAPP_API_TOKEN`: Bearer token Meta Cloud API
   - `WHATSAPP_PHONE_NUMBER_ID`: ID nomor telepon pengirim dari Meta Dashboard
   - `WHATSAPP_WEBHOOK_APP_SECRET`: App Secret untuk HMAC-SHA256 signature verification

---

## 9. Assumptions & Out of Scope

### Assumptions:
- Modul Feature 005 (Document Intelligence) dan Feature 006 (Hermes Automation API) telah selesai dan beroperasi di branch utama.
- Pengguna WhatsApp lapangan telah memiliki nomor telepon yang dicatat oleh Administrator saat pembuatan akun.
- Format penulisan nomor WhatsApp menggunakan format internasional standar (E.164).

### Explicitly Out of Scope:
- **WhatsApp Web Scraping / Unofficial Browser Automation**: Penggunaan bot browser tidak resmi dilarang demi keandalan dan keamanan audit.
- **Persetujuan Jurnal Otomatis**: WhatsApp tidak boleh digunakan untuk melakukan final journal posting bypass.
- **Modifikasi Database Langsung**: Tidak ada direct query atau bypassing API boundary.
- **Aktivasi Akun Berbayar Meta**: Penyediaan akun berbayar ditunda hingga deployment staging/production berlisensi resmi.
