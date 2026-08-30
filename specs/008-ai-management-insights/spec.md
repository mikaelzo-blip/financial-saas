# Feature Specification: AI-Assisted Management Insights & Decision Support

**Feature Branch**: `008-ai-management-insights`  
**Status**: SPECIFIED & CLARIFIED  
**Created**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)
- [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)
- [specs/005-document-intelligence-intake/spec.md](file:///c:/Projects/financial-saas/specs/005-document-intelligence-intake/spec.md)
- [specs/006-hermes-automation-integration/spec.md](file:///c:/Projects/financial-saas/specs/006-hermes-automation-integration/spec.md)
- [specs/007-whatsapp-integration/spec.md](file:///c:/Projects/financial-saas/specs/007-whatsapp-integration/spec.md)

---

## 1. Executive Summary

Fitur **AI-Assisted Management Insights & Decision Support** menyediakan lapisan kecerdasan buatan penasihat (*advisory AI intelligence*) yang menganalisis data laporan keuangan otoritatif SaaS (Feature 004), antrean review dokumen (Feature 005), dan histori transaksi (Feature 002) untuk menghasilkan narasi ringkasan eksekutif, deteksi anomali finansial, observasi likuiditas arus kas, peringatan risiko piutang/utang, dan evaluasi margin proyek.

Fitur ini melayani manajemen puncak (*Owner / Direktur Utama*), Manajer Keuangan, dan Project Manager melalui antarmuka web interaktif serta kanal perpesanan Hermes/WhatsApp. **AI bersifat penasihat murni (*advisory only*) dan bukan pengambil keputusan akuntansi.**

### Architectural Invariants & Non-Negotiable Boundaries:
1. **AI BUKAN Mesin Akuntansi**: AI dilarang keras menentukan akun debit/kredit, dilarang membuat atau memposting baris jurnal secara mandiri, dan dilarang mengubah angka laporan keuangan.
2. **AI BUKAN System of Record**: Seluruh angka finansial wajib berasal dari DTO laporan keuangan backend yang telah terverifikasi (*Authoritative Reporting DTOs*). AI dilarang mengarang (*hallucinate*) nilai moneter.
3. **Pemisahan Tegas Fakta vs Interpretasi**: Setiap insight wajib menyertakan metrik sumber (*source metrics*), periode laporan, referensi data, tingkat keyakinan, dan label pemisah antara fakta numerik otoritatif dengan analisis naratif AI.
4. **Bukan Klien Langsung Database**: Layanan AI dan provider LLM dilarang keras memiliki koneksi langsung ke database PostgreSQL. Seluruh data disuplai melalui API agregasi pelaporan terautentikasi dan terisolasi per tenant.
5. **Fallback Deterministik**: Jika layanan AI eksternal offline, mengalami timeout, atau kuota habis, sistem wajib menyediakan ringkasan berbasis aturan (*rule-based heuristic fallback*) tanpa menghentikan ketersediaan dashboard pelaporan.

---

## 2. Clarifications

### Session 2026-08-30

- **Q01: Sumber Data Masukan AI (Grounding Data)** → **Decision**: AI hanya mengonsumsi payload data terstruktur dari API Reporting Feature 004 (`ProfitLossReportResponse`, `BalanceSheetReportResponse`, `CashFlowReportResponse`, `ARAgingReportResponse`, `APAgingReportResponse`, `ProjectProfitabilityReportResponse`, `BudgetVsActualReportResponse`, `DashboardSummaryResponse`) dan status agregat Review Queue. AI dilarang melakukan scraping terhadap tampilan teks HTML UI.
- **Q02: Penanganan Data yang Tidak Tersedia** → **Decision**: Jika sebuah indikator finansial (misal: anggaran proyek yang belum diinput atau data komparatif tahun lalu) tidak tersedia, AI wajib secara eksplisit menyatakan *"Data tidak tersedia"* dan dilarang memalsukan angka 0 atau estimasi spekulatif.
- **Q03: Pertanyaan Tanya-Jawab Finansial (Natural Language Q&A)** → **Decision**: MVP mendukung 5 kategori kueri manajemen terstruktur:
  1. *Kondisi Finansial Periode Berjalan* (P&L, Neraca, Likuiditas)
  2. *Analisis Profitabilitas & Margin Proyek*
  3. *Risiko Penagihan Piutang & Umur Piutang (AR Aging)*
  4. *Analisis Likuiditas Kas vs Laba Akrual (Arus Kas)*
  5. *Status & Anomali Antrean Review Dokumen*
- **Q04: Edukasi Pemisahan Laba vs Kas Proyek** → **Decision**: Setiap kali AI menganalisis kas proyek yang defisit saat laba akrual positif, AI wajib menyertakan penjelasan edukatif bahwa laba akrual mencerminkan progres pekerjaan/invoice, sedangkan posisi kas mencerminkan waktu penerimaan uang riil dari customer dan pembayaran lapangan.
- **Q05: Pencegahan Prompt Injection dari Bukti Transaksi** → **Decision**: Seluruh teks mentah dari pihak luar (seperti caption WhatsApp, catatan nota, deskripsi vendor) disanitasi dan dibungkus dalam tag data berpagar (*delimited JSON blocks*) dengan instruksi sistem tegas bahwa instruksi di dalam data transaksi dilarang dieksekusi.
- **Q06: Strategi Caching & Kontrol Biaya Token** → **Decision**: Payload insight di-cache berdasarkan hash data metrik + `organization_id` + `period_key`. Permintaan insight berulang untuk data laporan yang sama tidak akan memanggil ulang model LLM. Batasan token output maksimal 500 token per narasi.
- **Q07: Abstraksi Provider AI** → **Decision**: Arsitektur menggunakan antarmuka `AIInsightProvider` yang dapat di-switch melalui environment variable (`MOCK`, `GEMINI`, `OPENAI_COMPATIBLE`). Pengujian unit dan CI/CD berjalan 100% menggunakan `MockAIInsightProvider`.
- **Q08: Deteksi Anomali Finansial Berbasis Heuristik & AI** → **Decision**: Anomali dideteksi melalui kombinasi formula aturan ambang batas (contoh: margin proyek $< 10\%$, biaya aktual $> 100\%$ anggaran, AR $> 60$ hari $> 30\%$ total AR) yang kemudian dinarasikan secara kontekstual oleh AI.
- **Q09: Keamanan Privasi Data Multi-Tenant** → **Decision**: Data laporan keuangan difilter secara ketat berdasarkan `organization_id` sebelum dikirim ke prompt AI. Tidak ada identitas global atau data lintas tenant yang digabungkan dalam satu prompt.
- **Q10: Batasan Ruang Lingkup (Out of Scope)** → **Decision**: AI dilarang melakukan peramalan pasar saham/investasi, dilarang memberikan opini hukum pajak formal, dilarang menyetujui dokumen, dan dilarang menginisiasi pembayaran uang.

---

## 3. User Personas & Actors

| Persona | Saluran Akses | Kebutuhan Utama |
|---|---|---|
| **Direktur Utama / Owner Kontraktor** | Web Executive Dashboard & WhatsApp | Ringkasan narasi kesehatan finansial bulanan, deteksi proyek yang mengalami kebocoran biaya, dan kondisi runway kas. |
| **Manajer Keuangan** | Web Reporting Workspace | Penjelasan selisih anggaran vs realisasi, identifikasi tagihan macet, dan tren antrean review dokumen bermasalah. |
| **Project Manager** | Web Project Insight Panel | Penjelasan komposisi biaya 9 kategori proyek, margin laba kotor, dan posisi kas masuk vs kas keluar proyeknya. |
| **Hermes Assistant** | WhatsApp & API Client | Mengirimkan ringkasan berkala dan menjawab pertanyaan tanya-jawab operasional dari direktur via WhatsApp. |

---

## 4. User Scenarios & Acceptance Criteria

### User Story 1 — Ringkasan Eksekutif & Narasi Finansial Bulanan (Priority: P1) 🎯 MVP

Sebagai Direktur Utama, saya ingin membaca ringkasan naratif bahasa Indonesia yang padat dan jelas mengenai kinerja keuangan bulanan perusahaan langsung pada Dashboard Eksekutif, sehingga saya dapat memahami kesehatan bisnis tanpa harus menelaah ratusan baris neraca dan laba rugi.

**Why this priority**: Mengubah data tabel angka kaku menjadi wawasan bisnis yang langsung dapat ditindaklanjuti oleh pemilik bisnis non-akuntan.

**Independent Test**: Masukkan payload laporan keuangan Agustus 2026 ke layanan insight. Sistem mengembalikan narasi eksekutif berisi: ringkasan pendapatan, margin kotor, laba bersih, kondisi kas likuid, dan 3 sorotan utama dengan pemisahan fakta vs analisis.

**Acceptance Scenarios**:
1. **Given** laporan keuangan Agustus 2026 dengan Pendapatan Rp 1 Miliar dan Laba Bersih Rp 150 Juta (15%), **When** pengguna membuka Dashboard Eksekutif, **Then** kartu "AI Executive Summary" menyajikan ringkasan bahasa Indonesia yang menyebutkan angka Rp 1 Miliar dan Rp 150 Juta secara akurat, menyoroti rasio profitabilitas, dan melampirkan badge referensi periode.
2. **Given** layanan AI provider sedang tidak dapat dijangkau (timeout/error), **When** ringkasan diminta, **Then** sistem menampilkan ringkasan deterministik berbasis aturan (*rule-based fallback summary*) dengan label *"Ringkasan Berbasis Metrik Standar (AI Offline)"*.

---

### User Story 2 — Analisis Kesehatan & Margin Proyek Berkelanjutan (Priority: P1)

Sebagai Project Manager / Direksi, saya ingin melihat kartu wawasan AI pada halaman detail proyek yang membedakan antara Laba Proyek (Akrual) dan Posisi Kas Proyek (Likuiditas) serta menyoroti kategori biaya yang mengalami lonjakan (*cost overrun*).

**Why this priority**: Menghindari kesalahpahaman fatal di mana proyek dianggap aman karena menguntungkan di atas kertas padahal mengalami krisis likuiditas kas di lapangan.

**Independent Test**: Berikan data proyek dengan Nilai Kontrak Rp 500 Juta, Invoice Rp 300 Juta, Kas Masuk Rp 100 Juta, Biaya Aktual Rp 250 Juta (Overrun pada Material). Sistem menghasilkan insight yang menyatakan laba akrual Rp 50 Juta tetapi kas defisit -Rp 150 Juta, serta menandai biaya material sebagai anomali.

**Acceptance Scenarios**:
1. **Given** data proyek dengan margin laba kotor di bawah target ($< 15\%$), **When** halaman Profitabilitas Proyek dibuka, **Then** AI menampilkan peringatan risiko margin kuning/merah disertai rekomendasi audit biaya material/upah.
2. **Given** kas keluar proyek melebihi kas masuk dari termin, **When** tab Posisi Kas dibuka, **Then** AI menampilkan narasi edukatif: *"Proyek ini mencatat laba akrual Rp X, namun posisi kas mengalami defisit Rp Y karena termin penagihan belum cair."*

---

### User Story 3 — Tanya Jawab Finansial Terstruktur (Financial Q&A) (Priority: P2)

Sebagai Manajer Keuangan / Direktur, saya ingin mengajukan pertanyaan dalam bahasa Indonesia sehari-hari seperti *"Piutang mana yang paling mendesak ditagih?"* atau *"Kenapa kas turun bulan ini?"* dan menerima jawaban berbasis data riil.

**Why this priority**: Memfasilitasi eksplorasi data cepat bagi manajemen tanpa perlu menyusun query filter manual.

**Independent Test**: Kirim pertanyaan *"Piutang mana yang kritis?"*. Sistem memetakan kueri ke sub-ledger AR Aging, mengidentifikasi invoice di atas 90 hari, dan menyusun jawaban berbobot dengan daftar debitur dan nominal terkait.

**Acceptance Scenarios**:
1. **Given** terdapat 2 invoice customer dengan umur $> 90$ hari senilai total Rp 85 Juta, **When** pengguna bertanya *"Piutang mana yang jatuh tempo?"*, **Then** AI menjawab dengan menyebutkan nama pelanggan, nomor invoice, dan total Rp 85 Juta tanpa menambah-nambahkan klaim palsu.
2. **Given** pengguna menanyakan hal di luar cakupan finansial (misal: *"Saham apa yang bagus dibeli?"*), **When** kueri diproses, **Then** AI menjawab dengan sopan: *"Saya hanya dapat menganalisis data operasional dan keuangan internal perusahaan Anda."*

---

### User Story 4 — Deteksi Anomali & Tren Antrean Review Dokumen (Priority: P3)

Sebagai Manajer Keuangan, saya ingin sistem memberikan sinyal anomali terhadap transaksi mencurigakan (misal: lonjakan biaya mendadak atau dokumen ganda berulang di Review Queue) untuk mempercepat verifikasi sebelum penutupan buku.

**Why this priority**: Memperkuat fungsi pengendalian internal (*internal control*) dan mencegah kebocoran dana operasional.

**Independent Test**: Masukkan data transaksi dengan lonjakan beban perjalanan dinas 300% dari rata-rata 3 bulan. Sistem menghasilkan flag anomali kategori `UNUSUAL_EXPENSE_SPIKE` dengan data komparatif.

**Acceptance Scenarios**:
1. **Given** ada 15 dokumen tersangkut di Review Queue dengan alasan `PROJECT_AMBIGUOUS`, **When** AI menganalisis antrean intake, **Then** AI memberikan saran perbaikan: *"Banyak nota belanja lapangan tidak mencantumkan nama proyek. Pertimbangkan menyosialisasikan penulisan kode proyek kepada mandor lapangan."*

---

## 5. Functional Requirements

### Data Aggregation & Grounding Interface
- **FR-001**: Sistem WAJIB mengumpulkan data analisis murni dari backend reporting service terverifikasi (`ProfitLossService`, `BalanceSheetService`, `CashFlowService`, `ARAgingService`, `APAgingService`, `ProjectReportingService`, `BudgetService`, `IntegrityService`).
- **FR-002**: Data input ke modul AI WAJIB diformat dalam Pydantic DTO terstruktur dengan presisi moneter penuh (`Decimal` dikonversi ke representasi numerik tepat).
- **FR-003**: Sistem DILARANG KERAS menyuplai data mentah unverified atau melakukan query bebas SQL dari layer AI ke database.

### Insight Generation Engine & Prompt Architecture
- **FR-004**: Sistem WAJIB menghasilkan 4 jenis artefak wawasan terstruktur:
  1. `ExecutiveSummaryInsight`: Ringkasan laba rugi, neraca, likuiditas, dan KPI utama.
  2. `ProjectHealthInsight`: Evaluasi margin, 9 kategori biaya, varians anggaran, dan arus kas proyek.
  3. `CashAndWorkingCapitalInsight`: Likuiditas kas, umur piutang kritis, dan tekanan utang vendor.
  4. `OperationalReviewInsight`: Statistik throughput review queue dan anomali bukti transaksi.
- **FR-005**: Setiap insight WAJIB menyertakan metadata: `organization_id`, `period_label`, `as_of_date`, `generated_at`, `confidence_category` (`HIGH`, `MEDIUM`, `LOW`), dan daftar `source_references`.
- **FR-006**: Prompt template WAJIB menyertakan instruksi sistem anti-halusinasi: jika angka tidak tercantum dalam konteks data, model WAJIB menyatakan *"tidak tersedia"* dan dilarang mengarang angka.

### Structured Management Q&A Service
- **FR-007**: Sistem WAJIB menyediakan endpoint `POST /api/v1/insights/query` yang memproses pertanyaan teks manajemen dalam bahasa Indonesia.
- **FR-008**: Query engine WAJIB mengklasifikasikan maksud pertanyaan (*intent classification*) ke domain laporan yang relevan (P&L, Neraca, Cash Flow, AR, AP, Proyek, Review Queue) dan hanya menyertakan data DTO terkait ke dalam prompt.
- **FR-009**: Pertanyaan di luar cakupan keuangan internal WAJIB ditolak secara aman dengan pesan penolakan standar tanpa memicu pemrosesan data finansial.

### Security, Injection Defense & Tenant Isolation
- **FR-010**: Seluruh teks input eksternal (caption, catatan vendor) WAJIB disanitasi dari tag prompt injection (`[SYSTEM]`, `IGNORE PREVIOUS INSTRUCTIONS`, dll) dan dibungkus dalam tag data JSON berpagar.
- **FR-011**: Seluruh query, cache, dan riwayat tanya jawab WAJIB diisolasi secara ketat berdasarkan `organization_id`.
- **FR-012**: Kredensial API AI provider WAJIB dikelola melalui environment configuration terenkripsi dan tidak boleh tercatat pada log atau respon klien.

### Caching, Cost Control & Fallback Architecture
- **FR-013**: Sistem WAJIB mengimplementasikan caching cerdas: kunci cache adalah hash SHA-256 dari `(organization_id, period_key, report_payload_hash)`. Jika data laporan tidak berubah, insight disajikan dari cache.
- **FR-014**: Batasan panjang token output WAJIB dibatasi maksimal 500 token untuk ringkasan kartu dan 1.000 token untuk sesi tanya-jawab.
- **FR-015**: Jika AI provider mengalami kegagalan, timeout ($> 10$ detik), atau limit kuota, sistem WAJIB secara otomatis mengembalikan ringkasan deterministik berbasis aturan (*rule-based fallback summary*) dengan status `provider: "DETERMINISTIC_FALLBACK"`.

---

## 6. Key Entities

1. **AIInsightLog**:
   - `id`: UUID (Primary Key)
   - `organization_id`: UUID (Foreign Key ke `Organization`)
   - `insight_type`: Enum (`EXECUTIVE_SUMMARY`, `PROJECT_HEALTH`, `CASH_WORKING_CAPITAL`, `ANOMALY_AUDIT`, `MANAGEMENT_QA`)
   - `period_key`: String (e.g. `2026-08`, `2026-Q3`, `PROJECT-uuid`)
   - `prompt_payload_hash`: String (SHA-256 fingerprint dari input data)
   - `response_json`: JSONB (Menyimpan fakta numerik, narasi, rekomendasi, dan referensi)
   - `provider_used`: String (`mock`, `gemini`, `openai_compatible`, `deterministic_fallback`)
   - `tokens_used`: Integer
   - `latency_ms`: Integer
   - `created_at`: Timestamp

2. **AIConversationSession**:
   - `id`: UUID (Primary Key)
   - `organization_id`: UUID
   - `user_id`: UUID
   - `session_title`: String
   - `created_at` / `updated_at`: Timestamp

3. **AIConversationMessage**:
   - `id`: UUID (Primary Key)
   - `session_id`: UUID (Foreign Key ke `AIConversationSession`)
   - `sender`: Enum (`USER`, `ASSISTANT`)
   - `message_text`: Text
   - `context_intent`: String
   - `source_references`: JSONB (Daftar laporan/dokumen/proyek rujukan)
   - `created_at`: Timestamp

---

## 7. Success Criteria

- **SC-001 (Zero Hallucination)**: 100% angka moneter yang dikutip dalam narasi AI cocok persis ($\Delta = 0.00$) dengan angka pada DTO laporan backend otoritatif.
- **SC-002 (Fact vs Interpretation Separation)**: 100% respons insight menyertakan blok metrik sumber terpisah dari narasi interpretasi.
- **SC-003 (Robust Fallback)**: 100% kegagalan koneksi provider eksternal dialihkan ke mesin ringkasan heuristik deterministik dalam waktu $\le 500$ ms tanpa menghasilkan HTTP 500 error ke pengguna.
- **SC-004 (Tenant Isolation)**: 0% data bocor lintas tenant dalam uji penetrasi kueri multi-tenant.
- **SC-005 (Prompt Injection Defense)**: 100% upaya manipulasi prompt dari caption/teks dokumen dinetralkan tanpa mengeksekusi instruksi liar.
- **SC-006 (Cost & Latency Control)**: $\ge 80\%$ permintaan insight pada data laporan yang tidak berubah dilayani dari cache lokal dalam waktu $\le 50$ ms.
- **SC-007 (Offline CI/CD Testability)**: Seluruh test suite dapat dijalankan secara mandiri dalam mode CI/CD menggunakan `MockAIInsightProvider` tanpa memerlukan API key eksternal.

---

## 8. Provider Abstraction & Prerequisites

Layanan AI diabstraksikan melalui interface `AIInsightProvider`:
- **`MockAIInsightProvider`** (Default dev & CI/CD): Menggunakan generator template berbasis data deterministik untuk menghasilkan respon realistis tanpa koneksi internet.
- **`GeminiInsightProvider`** (Google Gemini 1.5 / 2.0 via Google GenAI SDK): Menggunakan model efisien untuk penalaran kontekstual bahasa Indonesia.
- **`OpenAICompatibleInsightProvider`** (Format universal OpenAI / Ollama / Local vLLM): Mendukung model lokal mandiri atau gateway pihak ketiga.

**Environment Configuration**:
```env
AI_INSIGHT_PROVIDER=mock          # 'mock' | 'gemini' | 'openai_compatible'
AI_INSIGHT_CACHE_TTL_SECONDS=3600 # 1 jam
AI_INSIGHT_TIMEOUT_SECONDS=10
GEMINI_API_KEY=                   # Opsional untuk mode live
OPENAI_API_KEY=                   # Opsional untuk mode live
OPENAI_BASE_URL=                  # Opsional untuk endpoint lokal
```
