# PRD v2.0 — Financial SaaS Kontraktor
## WhatsApp Offline Capture + Hermes Deferred Analysis + Project-Based Accounting

**Dokumen:** Product Requirements Document + Technical Remediation Plan  
**Versi:** 2.0  
**Tanggal:** 5 September 2026  
**Status:** Draft implementasi terbaru berdasarkan konsep bisnis, keputusan Owner, contoh laporan konsultan, dan audit source code `financial-saas-main`  
**Primary User:** Owner / Direktur  
**Target fase:** Interim / MVP operasional 4–6 bulan  
**Deployment utama:** PC Windows lokal untuk Financial SaaS, PostgreSQL, OCR, Hermes, dan Accounting Engine  
**Prinsip prioritas:** **Cash Completeness → Project Cost Visibility → Accounting Integrity → Traceability → Owner Simplicity → Automation**

---

# 0. Sumber dan Aturan Keputusan

Dokumen ini menyatukan:

1. `Sistem_Keuangan_Kontraktor_Final_Concept_v1.md`
2. `Konsep_Interim_Financial_SaaS_WhatsApp_Hermes_4-6_Bulan.md`
3. Keputusan terbaru Owner dalam diskusi produk.
4. Contoh Laba Rugi dan Neraca dari konsultan keuangan.
5. Audit source code repository `financial-saas-main`.
6. Kondisi implementasi aktual pada `PROJECT_STATUS.md`, `AGENTS.md`, backend, frontend, migrations, dan test structure.

Jika terjadi konflik, urutan keputusan produk untuk implementasi berikutnya adalah:

1. keputusan Owner terbaru yang tertulis pada PRD ini;
2. accounting/document invariants pada constitution yang tidak bertentangan;
3. PRD ini;
4. konsep final sebelumnya;
5. implementation lama.

**Catatan penting:** jangan menghapus accounting invariants yang sudah benar. Perubahan requirement dilakukan melalui spec/migration/refactor terkontrol, bukan rewrite.

---

# 1. Executive Summary

Financial SaaS adalah sistem keuangan perusahaan kontraktor/project-based yang dirancang agar Owner dapat mencatat aktivitas keuangan tanpa harus memahami debit/kredit.

Dua jalur input utama:

- **WhatsApp** untuk capture cepat bukti transaksi, PDF, foto, dan deskripsi.
- **Financial SaaS Web App** untuk input manual, melihat inbox, review, koreksi, approval exception, project, cash/bank, rekonsiliasi, dan laporan.

WhatsApp **bukan** tempat approval atau percakapan akuntansi dengan Hermes pada MVP.

Saat PC Financial SaaS mati:

```text
Owner kirim foto/PDF + deskripsi melalui WhatsApp
              ↓
Remote Capture Inbox menyimpan pesan + media
              ↓
PC boleh tetap OFF
```

Saat PC hidup:

```text
Local Sync Worker
      ↓
Financial SaaS Inbox
      ↓
Hermes + OCR menganalisis backlog
      ↓
Matching / classification / allocation candidate
      ↓
Deterministic validation
      ↓
AUTO-SAFE atau REVIEW_REQUIRED
      ↓
Accounting Engine
      ↓
Journal / AR / AP / Project / Reports
```

Owner tidak perlu membalas Hermes di WhatsApp.

Semua review, koreksi, dan approval yang diperlukan dilakukan di Web App.

---

# 2. Product Vision

Membuat sistem keuangan kontraktor yang:

- mudah dipakai Owner non-akuntan;
- tidak kehilangan arus kas masuk/keluar;
- mampu menghubungkan invoice, bukti transfer, project, vendor, customer, dan rekening;
- memisahkan cash movement dari accrual accounting;
- menunjukkan pembelanjaan project dengan jelas;
- menghasilkan laporan keuangan yang dapat direkonsiliasi dengan laporan konsultan;
- menggunakan Hermes sebagai intelligence/review agent tanpa memberinya kewenangan menentukan debit/kredit;
- tetap berfungsi ketika PC lokal sering mati.

Target pengalaman:

> **Kirim bukti → sistem menyimpan → PC hidup → Hermes memahami → transaksi terhubung → project ter-update → laporan tersedia.**

---

# 3. Primary User dan Jobs-To-Be-Done

## 3.1 Primary User

**Owner / Direktur**

Karakteristik:

- bukan akuntan teknis;
- mengutamakan cashflow;
- ingin melihat biaya dan profit project;
- banyak menerima/mengirim bukti melalui WhatsApp;
- ingin laporan sederhana tetapi tetap benar;
- tidak ingin input data yang sama berulang kali.

## 3.2 Jobs-To-Be-Done

Owner ingin:

1. mencatat uang masuk/keluar dengan mudah;
2. mengirim bukti tanpa harus membuka komputer;
3. memastikan bukti tidak hilang saat PC mati;
4. melihat cash & bank secara cepat;
5. mengetahui biaya tiap project;
6. membuka satu project dan melihat arus kas, biaya, profit, transaksi, dan dokumennya;
7. melihat transaksi yang belum dapat dipahami Hermes;
8. membaca Laba Rugi dan Neraca dalam bahasa sederhana;
9. tetap dapat membuka detail sampai transaksi/jurnal/dokumen jika dibutuhkan.

---

# 4. Locked Product Principles

```text
WhatsApp ≠ Database Keuangan
WhatsApp = Asynchronous Capture Channel

Financial SaaS = Source of Truth
PostgreSQL = Transactional System of Record

Hermes = Intelligence + Orchestration + Review Agent
Hermes ≠ Accounting Engine

Accounting Engine = Final Accounting Authority

Invoice ≠ Cash Movement
Transfer Proof ≠ Automatically Expense

Project Profit ≠ Project Cash Position

Raw Document = Immutable Evidence

Cash Movement Must Not Be Missed

Ambiguity / Sensitive Event
→ Human Review in Web App

Safe Routine Event
+ Deterministic Validation PASS
+ Strong Match
→ May Auto-Process

No Financial Approval via WhatsApp in MVP

PC OFF
→ Capture tetap harus terjadi

PC ON
→ Hermes memproses backlog
```

---

# 5. Product Goals

## G1 — Cash Completeness

Semua money movement aktual harus:

- terdeteksi;
- tercatat;
- direkonsiliasi;
- atau masuk status `UNMATCHED/REVIEW_REQUIRED`.

Sistem tidak boleh menyembunyikan uang hanya karena belum tahu klasifikasinya.

## G2 — Project Cost Visibility

Owner dapat melihat:

- total pengeluaran tiap project;
- vendor terbesar;
- kategori biaya;
- transaksi detail;
- dokumen pendukung;
- uang masuk/keluar project;
- profit dan margin.

## G3 — Correct Accrual Accounting

Laporan berikut menggunakan accrual accounting:

- Laba Rugi;
- Neraca;
- Piutang;
- Utang;
- Project Profit;
- Project Spending.

Cash Flow menggunakan money movement aktual.

## G4 — Low Owner Friction

Owner tidak perlu:

- memasukkan debit/kredit;
- memilih COA untuk transaksi rutin;
- mengetik ulang nominal/tanggal/vendor jika sudah terbaca;
- approve setiap transaksi rutin.

## G5 — Traceability

Setiap angka yang tampil di laporan harus dapat ditelusuri:

```text
Report
→ Journal
→ Transaction / Business Event
→ Settlement / Money Movement
→ Document
```

---

# 6. Non-Goals MVP

Belum menjadi prioritas:

- full-cloud Financial SaaS;
- 24/7 Hermes;
- Kubernetes;
- Redis cluster;
- Kafka;
- managed PostgreSQL;
- direct bank API;
- full tax engine;
- full inventory valuation;
- RAB/budget project wajib;
- automatic retention reminder;
- multi-office;
- WhatsApp approval;
- WhatsApp clarification chat;
- high availability production-grade.

---

# 7. Operating Model Utama

## 7.1 Saat PC OFF

Owner dapat mengirim:

- PDF invoice;
- foto invoice;
- bukti transfer;
- nota;
- receipt;
- PO/SPK;
- dokumen lain;
- caption/deskripsi.

Remote Capture Inbox hanya melakukan:

```text
receive message
verify/deduplicate
store metadata
download/store media
hash file
mark PENDING_LOCAL
```

Tidak menjalankan:

- OCR;
- Hermes;
- matching;
- accounting;
- journal;
- approval.

## 7.2 Saat PC ON

Startup otomatis menjalankan:

1. PostgreSQL;
2. FastAPI;
3. Web UI;
4. Local Sync Worker;
5. Document Worker;
6. Hermes integration;
7. background jobs.

Kemudian:

```text
PENDING_LOCAL
→ SYNCING
→ SYNCED_LOCAL
→ ANALYSIS_PENDING
→ PROCESSING
→ ANALYZED
→ AUTO_PROCESSED / REVIEW_REQUIRED
```

## 7.3 Web App Harus Menampilkan Raw Inbox Lebih Dulu

Begitu dokumen sudah tersinkron ke PC, Owner harus dapat melihatnya walaupun Hermes belum selesai.

Contoh:

```text
WhatsApp Inbox

05 Sep 14:02
bukti-transfer.jpg
Caption: "PT ABC proyek Ancol"
Status: Menunggu Analisis

05 Sep 14:01
invoice-ABC.pdf
Caption: "material + jasa pemasangan"
Status: Menunggu Analisis
```

---

# 8. WhatsApp Strategy — Revised MVP

## 8.1 WhatsApp Hanya Capture

MVP WhatsApp mendukung:

- foto;
- PDF;
- caption/deskripsi;
- message metadata.

Tidak mendukung:

- approve;
- reject;
- koreksi;
- chat klarifikasi;
- query laporan;
- posting command.

## 8.2 Natural Language Tetap Diterima

Contoh:

```text
Bayar PT ABC 25jt untuk material/barang + jasa pemasangan proyek Ancol
```

Tetapi caption tidak wajib jika informasi cukup terbaca dari dokumen.

Prinsip:

> **Upload first, explain only when useful.**

## 8.3 Current Transport Constraint

Repository saat ini menggunakan Hermes Baileys bridge sebagai transport aktif karena jalur Meta Cloud API tidak tersedia pada akun developer saat ini.

**Constraint teknis penting:**

Jika Baileys hanya berjalan di PC Financial SaaS, requirement durable capture saat PC mati **tidak dapat dijamin**.

Agar PC Finance tetap boleh mati, harus ada **Capture Relay** yang hidup terpisah dari PC Finance.

### Interim Recommended Architecture

```text
Owner WhatsApp
     ↓
Always-On Capture Relay
(Node.js + WhatsApp transport adapter)
     ↓
Remote Durable Inbox
metadata + media
     ↓
PC Finance boleh OFF
     ↓
PC ON
     ↓
Local Sync Worker (outbound HTTPS pull)
     ↓
Financial SaaS
```

Hermes, OCR, accounting, dan PostgreSQL finance tetap lokal.

Transport WhatsApp harus provider-agnostic sehingga nanti dapat diganti tanpa mengubah accounting core.

**Catatan risiko:** Baileys adalah transport tidak resmi. Jadikan adapter sementara/development dan isolasikan dari domain finance.

---

# 9. Remote Durable Inbox

## 9.1 Responsibility

Remote inbox menyimpan:

- external message ID;
- sender;
- sent timestamp;
- caption;
- mime type;
- original filename;
- media object key;
- SHA-256;
- status;
- retry count;
- received timestamp.

## 9.2 Recommended Storage

Sesuai konsep interim:

- **D1 / relational metadata store** untuk state inbox;
- **R2 / object storage** untuk file sementara.

Jika transport Meta tidak tersedia, Capture Relay dapat tetap menulis ke endpoint inbox yang sama.

## 9.3 Inbox Status

```text
RECEIVED_REMOTE
MEDIA_STORED
PENDING_LOCAL
CLAIMED
SYNCING
SYNCED_LOCAL
SYNC_FAILED
EXPIRED
```

## 9.4 Retention

Default:

```text
PENDING_LOCAL
→ keep

SYNCED + fully persisted locally
→ retain recovery window

after recovery window
→ delete remote media
```

Rekomendasi awal recovery window: 7 hari setelah sukses lokal, configurable.

---

# 10. Document Intelligence

## 10.1 Pipeline

```text
RAW DOCUMENT
      ↓
FILE VALIDATION
      ↓
SHA-256 / DUPLICATE CHECK
      ↓
DOCUMENT CLASSIFICATION
      ↓
TEXT EXTRACTION / OCR
      ↓
FIELD NORMALIZATION
      ↓
ENTITY MATCHING
      ↓
PROJECT / INVOICE / PO-SPK MATCHING
      ↓
MATCH EVIDENCE
      ↓
HERMES REASONING
      ↓
STRUCTURED CANDIDATE
      ↓
DETERMINISTIC VALIDATION
```

## 10.2 Document Types

Minimal:

```text
PO_CUSTOMER
SPK
CONTRACT
VARIATION_ORDER

VENDOR_INVOICE
PURCHASE_ORDER
QUOTATION
SUBCONTRACT_AGREEMENT

TRANSFER_PROOF
RECEIPT
BANK_STATEMENT
PETTY_CASH_PROOF

SURAT_JALAN
BAST
PROGRESS_REPORT

CUSTOMER_INVOICE
CUSTOMER_RECEIPT

TAX_INVOICE
OTHER_TAX_DOCUMENT
```

## 10.3 Document Session

Beberapa pesan yang berdekatan dapat menjadi satu konteks, tetapi **waktu bukan rule utama**.

Contoh:

```text
14:01 invoice PT ABC Rp25jt
14:02 transfer PT ABC Rp25jt
```

dapat dihubungkan sebagai satu business flow.

Matching order:

1. invoice/reference exact match;
2. vendor/customer;
3. amount;
4. recipient/account;
5. PO/SPK/project;
6. date proximity;
7. semantic/text similarity.

## 10.4 Match Evidence

Jangan hanya menyimpan `confidence = 97%`.

Simpan alasan:

```text
Vendor match        ✓
Amount match        ✓
Invoice reference   ✓
Bank recipient      ✓
Project match       ✓
```

Owner dapat melihat alasan tersebut di Web App.

---

# 11. Core Finance Model — Revised

PRD v2 memisahkan empat konsep yang sebelumnya terlalu dekat:

```text
DOCUMENT
      ↓
BUSINESS EVENT / TRANSACTION
      ↘
       MONEY MOVEMENT
          ↓
       SETTLEMENT
          ↓
ACCOUNTING JOURNAL
```

## 11.1 Document

Evidence asli.

## 11.2 Transaction / Business Event

Kejadian accrual/operasional seperti:

- Vendor Bill;
- Customer Invoice;
- Direct Purchase;
- Customer Advance;
- Vendor Advance;
- Expense;
- Asset Purchase.

Existing `transactions` tetap dipertahankan dan diposisikan sebagai business/accounting event.

## 11.3 Money Movement — New First-Class Entity

Merepresentasikan uang yang benar-benar masuk/keluar.

Field minimum:

```text
MoneyMovement_ID
Organization_ID
Payment_Account_ID
Movement_Date
Direction: IN / OUT
Amount
Currency
Reference
Counterparty_Text
Bank_Description
Source
Source_Document_ID
Reconciliation_Status
Created_At
```

Sumber:

```text
TRANSFER_PROOF
BANK_STATEMENT
MANUAL
```

## 11.4 Settlement — New

Menghubungkan money movement dengan invoice/bill/business event.

Contoh:

```text
Money Movement Rp50jt
├── INV-A Rp30jt
└── INV-B Rp20jt
```

atau:

```text
Money Movement Rp50jt
├── Project Ancol Rp30jt
└── Project Batam Rp20jt
```

## 11.5 Journal

Tetap dihasilkan deterministic oleh Accounting Engine.

Hermes tidak menulis journal.

---

# 12. Invoice vs Cash

Invoice vendor tanpa pembayaran tetap penting karena sistem menggunakan accrual accounting.

Contoh:

```text
Vendor Invoice Rp100jt
Cash Out = 0

Accounting:
Dr Project Cost / Asset / Expense
Cr Accounts Payable
```

Saat dibayar:

```text
Money Movement OUT Rp100jt

Accounting:
Dr Accounts Payable
Cr Bank
```

Jadi:

```text
Invoice ≠ Cash Movement
```

Tetapi dari sisi UX Owner:

> Cash movement tetap prioritas dashboard.

---

# 13. Project Model

Setiap project memiliki dokumen dasar:

- PO;
- Surat Pesanan;
- SPK.

Minimal:

```text
Project_ID
Project_Code
Project_Name
Customer_ID

Commercial_Document_Type
Commercial_Document_No
Commercial_Document_Date

Original_Contract_Value
Variation_Order
Revised_Contract_Value

Start_Date
Target_End_Date
Actual_End_Date
Project_Status
```

Hermes boleh membaca PO/SPK untuk membuat `PROJECT_SETUP_CANDIDATE`.

---

# 14. Tidak Ada RAB Wajib pada MVP

Karena sebelum project berjalan perusahaan tidak selalu mempunyai RAB pembelian:

- Budget vs Actual bukan KPI utama.
- Menu Budget vs Actual dapat disembunyikan atau diberi label future/configurable.
- Fokus pada **Actual Project Spending**.

---

# 15. Multi-Project dan Multi-Item

## 15.1 Default

Usahakan:

```text
1 transaction → 1 project
```

tetapi backend harus mendukung split.

## 15.2 One Payment, Multiple Projects

```text
Transfer PT ABC Rp50jt
├── Ancol Rp30jt
└── Batam Rp20jt
```

Bank movement tetap satu.

## 15.3 One Receipt, Multiple Items

```text
Belanja Rp350.000
├── Materai Rp100.000
├── HVS Rp150.000
└── Pulpen Rp100.000
```

Money movement tetap satu.

Item dapat mempunyai category/project berbeda.

---

# 16. Project Cost Categories

Minimal:

```text
MAT — Material & Goods
SUB — Subcontractor
LAB — Labor
TRN — Transportation
TRV — Travel
LOG — Logistics
EQP — Equipment
SIT — Site
OTH — Other Direct Cost
```

Subcontractor dapat menjual barang + jasa dalam satu invoice. Jangan paksa Owner memisahkan menjadi dua transaksi bank.

---

# 17. Customer Payment Patterns

Sistem harus mendukung:

## 17.1 PO Tanpa DP

```text
PO
→ delivery/acceptance
→ invoice
→ payment
```

## 17.2 Customer dengan DP

```text
DP
→ goods ready
→ final payment
→ delivery
```

DP tidak otomatis menjadi seluruh revenue.

## 17.3 SPK dengan Retensi

Contoh umum:

```text
95% setelah pekerjaan selesai
5% retention setelah periode tertentu
```

Tidak perlu reminder WhatsApp.

Retention tampil pada project/accounting detail.

---

# 18. Bank & Cash

## 18.1 Multi-Bank

MVP mendukung 2–3 rekening, scalable lebih banyak.

Laporan utama:

```text
Kas & Bank
```

Drill-down:

```text
Mandiri
BCA
BRI
Petty Cash
```

## 18.2 Payment Account Harus Menjadi Accounting Dimension

Existing repo mempunyai `PaymentAccount`, tetapi journal line belum membawa `payment_account_id`.

Target:

```text
JournalLine
├── account_id = 1101 Kas & Bank
└── payment_account_id = Mandiri/BCA/BRI
```

Tanpa ini, saldo per rekening tidak authoritative.

## 18.3 Interbank Transfer

```text
Mandiri -50jt
BCA +50jt
```

bukan expense/income.

Journal:

```text
Dr 1101 Kas & Bank [BCA]
Cr 1101 Kas & Bank [Mandiri]
```

---

# 19. Bank Statement Import & Reconciliation

## 19.1 Input Manual MVP

Supported:

- CSV;
- XLS/XLSX;
- PDF.

Priority:

```text
CSV/XLSX → preferred
PDF      → fallback
```

## 19.2 Import Batch

Entity:

```text
BankStatementImport
BankStatementLine
```

`BankStatementImport`:

```text
id
organization_id
payment_account_id
period_start
period_end
file_hash
source_file
imported_at
status
```

`BankStatementLine`:

```text
id
import_id
date
description
debit
credit
balance
reference
counterparty
reconciliation_status
```

## 19.3 Reconciliation Status

```text
MATCHED
PARTIAL_MATCH
UNMATCHED_BANK
UNMATCHED_BOOK
REVIEW_REQUIRED
```

## 19.4 Dashboard Completeness

Owner harus dapat melihat:

```text
Uang Keluar bulan ini       Rp500jt
Sudah teridentifikasi       Rp450jt
Belum teridentifikasi        Rp50jt
```

---

# 20. Review & Approval Policy

## 20.1 No Approval in WhatsApp

Seluruh review/approval dilakukan di Web App.

## 20.2 Exception-Based Review

Tidak semua transaction harus mengganggu Owner.

### Auto-safe hanya jika:

- transaction type berada di whitelist;
- tidak sensitive;
- tidak ada unresolved review flag;
- deterministic validation PASS;
- duplicate check PASS;
- required counterparties/project valid;
- amount/reference matching kuat;
- accounting rule tersedia;
- period OPEN;
- reconciliation/context memadai.

### Review Required jika:

```text
PROJECT_UNKNOWN
VENDOR_UNKNOWN
CUSTOMER_UNKNOWN
AMOUNT_MISMATCH
DUPLICATE_SUSPECTED
MISSING_DOCUMENT
ACCOUNT_REVIEW
TAX_REVIEW
MULTI_PROJECT_AMBIGUOUS
ASSET_EXPENSE_AMBIGUOUS
OWNER_TRANSACTION
RELATED_PARTY
MANUAL_ADJUSTMENT
```

## 20.3 Safe Automation Rule

Jangan gunakan:

```text
confidence > 95% → auto post
```

Gunakan:

```text
risk policy
+ transaction whitelist
+ deterministic checks
+ match evidence
```

---

# 21. Accounting Engine

Tetap deterministic.

Flow:

```text
Hermes
→ Candidate Transaction Type
→ Backend validation
→ PostingRuleRegistry
→ Accounting Engine
→ Journal
```

Hermes tidak boleh menentukan debit/kredit.

Contoh:

```text
VENDOR_BILL
Dr Project Cost / Expense
Cr AP
```

```text
PAY_VENDOR_BILL
Dr AP
Cr Kas & Bank
```

```text
CUSTOMER_PAYMENT
Dr Kas & Bank
Cr AR
```

```text
INTERBANK_TRANSFER
Dr Destination Payment Account
Cr Source Payment Account
```

---

# 22. Revenue Recognition

Untuk workflow MVP saat ini, customer invoice dapat menjadi trigger revenue sesuai implementation existing.

Tetapi revenue recognition adalah **configurable accounting policy**, bukan asumsi permanen.

Jangan hard-code kebijakan yang belum dikunci konsultan/perusahaan untuk semua kasus.

---

# 23. Reporting

## 23.1 Owner Dashboard

Cash-first dan project-cost-first.

## 23.2 Formal Accounting Reports

Minimal:

- Laba Rugi;
- Neraca;
- Cash Flow;
- General Ledger;
- Trial Balance;
- AR Aging;
- AP Aging;
- Project Profitability;
- Project Cash Position;
- Project Spending.

## 23.3 Consultant Report Mapping

Laporan harus dapat disajikan mendekati struktur konsultan:

### Laba Rugi

```text
Pendapatan / Penjualan
Harga Pokok
Laba Kotor
Beban Umum & Administrasi
Laba Usaha
Pendapatan Lain-lain
Beban Lain-lain
Laba Sebelum Pajak
Pajak Penghasilan
Laba Bersih
```

### Neraca

```text
ASET
- Kas & Bank
- Piutang
- Aset Tetap
- Akumulasi Penyusutan

KEWAJIBAN
- Jangka Pendek
- Jangka Panjang

EKUITAS
- Modal
- Saldo Laba
- Laba Tahun Berjalan
```

## 23.4 Reporting Mapping Layer

Jangan menentukan posisi laporan hanya berdasarkan prefix nomor akun.

Tambahkan metadata:

```text
report_section
report_subsection
display_order
current_long_term_classification
```

Contoh `report_section`:

```text
OPERATING_REVENUE
COGS
OPERATING_EXPENSE
OTHER_INCOME
OTHER_EXPENSE
INCOME_TAX
CURRENT_ASSET
FIXED_ASSET
CURRENT_LIABILITY
LONG_TERM_LIABILITY
EQUITY
```

---

# 24. Accounting Period & Opening Balance

## 24.1 Period Status

```text
OPEN
SOFT_CLOSED
CLOSED
```

Hermes/backend tidak boleh posting ke `CLOSED`.

## 24.2 Opening Balance

Saldo awal dari laporan konsultan harus dimasukkan sebagai:

```text
OPENING BALANCE JOURNAL
```

bukan angka manual pada dashboard.

## 24.3 Year-End Close

Perlu mekanisme formal agar laba tahun sebelumnya dipindahkan ke retained earnings/saldo laba sesuai policy.

---

# 25. Fixed Asset Register

Karena laporan konsultan mempunyai aset tetap dan akumulasi penyusutan, tambahkan:

```text
Asset_ID
Asset_Name
Asset_Category
Purchase_Date
Purchase_Value
Vendor_ID
Document_ID
Useful_Life
Depreciation_Method
Accumulated_Depreciation
Status
```

Hermes tidak menentukan:

- capitalization threshold;
- useful life;
- depreciation method.

Itu tetap policy manusia/konsultan.

---

# 26. FRONTEND — Information Architecture yang Direkomendasikan

Current sidebar terlalu panjang dan bercampur antara operasi harian, master data, dan laporan.

Urutan baru harus mengikuti kebiasaan Owner.

## 26.1 Primary Navigation Order

### 1. Dashboard

Halaman pertama setiap login.

### 2. WhatsApp Inbox

Capture backlog dan status analisis.

### 3. Proyek

Project list + project detail.

### 4. Kas & Bank

Saldo per rekening, cash in/out, movement list.

### 5. Rekonsiliasi Bank

Upload rekening koran dan unmatched movements.

### 6. Perlu Review

Hanya exception.

### 7. Transaksi

Riwayat business/accounting events.

### 8. Dokumen

Seluruh immutable evidence.

### 9. Piutang

Customer invoice & AR.

### 10. Utang

Vendor bill & AP.

### 11. Laporan

Group/collapsible:

```text
Laba Rugi
Neraca
Arus Kas
Project Profitability
Project Cash Position
Project Spending
Trial Balance
General Ledger
AR Aging
AP Aging
```

### 12. Data Master

Group/collapsible:

```text
Customer
Vendor/Subcon
Akun Kas & Bank
COA
Kategori
```

### 13. Pengaturan & Sistem

```text
Company
User
Hermes
WhatsApp transport
Backup
System Health
Audit
```

---

# 27. FRONTEND — Dashboard Layout

## Row 1 — Cash First

Empat card:

```text
TOTAL KAS & BANK
UANG MASUK BULAN INI
UANG KELUAR BULAN INI
NET CASH FLOW
```

Setiap card clickable.

## Row 2 — Project Spending

```text
Pembelanjaan Project Bulan Ini

Ancol       Rp...
Project B   Rp...
Project C   Rp...
```

Tambahkan:

```text
Belum Teralokasi Rp...
```

## Row 3 — Project Performance

```text
Project Profit
Project Margin
Project Aktif
```

## Row 4 — Exceptions

```text
WhatsApp belum dianalisis
Transaksi bank unmatched
Review required
Document failed
Duplicate suspect
```

## Row 5 — Secondary Accounting

```text
Piutang
Utang
Retention
Laba Bersih
```

**Cash Runway bukan KPI utama MVP.**

---

# 28. FRONTEND — WhatsApp Inbox Page

Tab:

```text
Semua
Belum Sinkron
Menunggu Analisis
Selesai
Perlu Review
Gagal
```

Card/list row:

```text
Timestamp
Sender
Caption
File preview
File type
Sync status
Analysis status
Finance status
Linked transaction
Linked project
```

Action Web App:

- buka dokumen;
- buka hasil Hermes;
- link ke project;
- link ke vendor/customer;
- buka review;
- retry analysis jika gagal.

Tidak ada action WhatsApp approval.

---

# 29. FRONTEND — Project Detail Page

Urutan:

## Header

```text
Project Name
PO/SPK
Customer
Nilai Kontrak
Status
```

## Cash Panel

```text
Uang Masuk
Uang Keluar
Net Cash
Unallocated
```

## Accrual Panel

```text
Revenue
Project Cost
Profit
Margin
```

## Project Spending

Breakdown:

```text
Material
Subcon
Labor
Transport
Travel
Logistics
Equipment
Site
Other
```

## Vendor Spend

Top vendor/subcon.

## Transactions

Filter IN/OUT/accrual.

## Documents

PO/SPK, invoice, transfer, BAST, surat jalan.

## Receivable / Retention

Secondary area, bukan KPI utama.

---

# 30. FRONTEND — Development Sequence

Urutan implementasi frontend:

### F0 — Contract Safety

- hentikan manual enum drift;
- gunakan OpenAPI-generated TypeScript types/client atau single generated schema source;
- fix current `TRANSFER_INTERBANK` vs `INTERBANK_TRANSFER` mismatch.

### F1 — Navigation Refactor

- group menu;
- cash/project/inbox di atas;
- master/reports collapsible.

### F2 — Cash-First Dashboard

- Cash In;
- Cash Out;
- Net Cash;
- Project Spending;
- Unallocated.

### F3 — WhatsApp Inbox

- raw messages;
- preview;
- sync status;
- analysis status.

### F4 — Cash & Bank

- account drilldown;
- movement history;
- per-bank balance.

### F5 — Bank Reconciliation

- upload CSV/XLSX/PDF;
- import preview;
- matched/unmatched.

### F6 — Project Detail Upgrade

- cash + accrual separate;
- project spending;
- vendor spend.

### F7 — Review Queue Upgrade

- evidence-based review;
- one-click correction where safe;
- owner approval only for required cases.

### F8 — Consultant-Style Reports

- report mapping;
- simple view vs detailed view.

---

# 31. BACKEND — Recommended Technology

## 31.1 Keep Existing Stack

Repository saat ini sudah memakai fondasi yang tepat.

| Layer | Existing / Recommended |
|---|---|
| API | FastAPI |
| Language | Python 3.11+ |
| ORM | SQLAlchemy 2 |
| PostgreSQL driver | asyncpg |
| Migration | Alembic |
| Validation | Pydantic |
| Web server | Uvicorn |
| Database | PostgreSQL |
| OCR | RapidOCR / ONNX Runtime + PDF extraction |
| HTTP integrations | httpx |
| Excel | openpyxl |
| Frontend | React + TypeScript |
| State/server cache | TanStack Query |
| Forms | React Hook Form + Zod |
| Build | Vite |
| CSS | Tailwind |
| Tests | pytest / Vitest |

**Tidak perlu rewrite ke framework lain.**

## 31.2 Architecture Style

Gunakan **Modular Monolith**.

Tidak perlu microservices untuk fase ini.

---

# 32. BACKEND — Recommended Module Boundaries

Target struktur logis:

```text
backend/src/

api/
core/

models/
schemas/

services/
├── projects/
├── counterparties/
├── documents/
├── inbox/
├── transactions/
├── money_movements/
├── settlements/
├── banking/
├── reconciliation/
├── accounting/
├── reporting/
├── review/
├── hermes/
└── audit/

integrations/
└── whatsapp/
    ├── provider.py
    ├── baileys_provider.py
    ├── meta_provider.py
    └── remote_inbox_client.py

workers/
├── inbox_sync_worker.py
├── document_worker.py
├── hermes_worker.py
└── reconciliation_worker.py
```

Tidak harus memindahkan semua file sekaligus. Refactor incremental.

---

# 33. BACKEND — Core Entities

Pertahankan:

```text
Organization
User
Project
Counterparty
PaymentAccount
Document
Transaction
TransactionAllocation
JournalEntry
JournalLine
VendorBill
CustomerInvoice
ReviewFlag
Audit
```

Tambah:

```text
InboxMessage
InboxAttachment
DocumentSession
MatchEvidence

MoneyMovement
Settlement
SettlementAllocation

BankStatementImport
BankStatementLine
BankReconciliation

AccountingPeriod
FixedAsset

BackgroundJob
```

Optional kemudian:

```text
TransactionLine
```

untuk item-level detail jika existing allocation belum cukup.

---

# 34. BACKEND — Processing Pipeline

```text
InboxMessage
    ↓
Document
    ↓
Extraction
    ↓
Hermes Candidate
    ↓
Match Evidence
    ↓
Processing Policy
    │
    ├── REVIEW_REQUIRED
    │
    └── SAFE
          ↓
Business Event / Money Movement
          ↓
Settlement
          ↓
Accounting Engine
          ↓
Journal
```

---

# 35. BACKEND — Persistent Jobs

Untuk satu PC, tidak perlu Redis.

Gunakan PostgreSQL job table:

```text
id
job_type
payload
status
attempt_count
available_at
locked_by
locked_until
last_error
created_at
updated_at
```

Worker menggunakan transactional claim / lease, misalnya `FOR UPDATE SKIP LOCKED`.

Harus tahan:

- crash;
- restart;
- duplicate retry;
- backlog 100+ dokumen.

---

# 36. BACKEND — API Direction

Contoh endpoint target:

```text
GET  /inbox/messages
GET  /inbox/messages/{id}
POST /inbox/messages/{id}/retry-analysis

POST /bank-statements/import
GET  /bank-statements/imports/{id}
GET  /bank-statements/lines

GET  /money-movements
GET  /money-movements/{id}

POST /settlements
PATCH /settlements/{id}

GET  /reconciliation
POST /reconciliation/{line_id}/match
POST /reconciliation/{line_id}/ignore

GET  /dashboard/cash-summary
GET  /dashboard/project-spending

POST /review/{id}/resolve
POST /review/{id}/approve
```

Existing routes dapat dipertahankan dan dikembangkan.

---

# 37. Security & Audit Requirements

Minimum:

- authentication;
- organization/tenant isolation;
- role authorization;
- immutable posted journal;
- immutable raw document;
- SHA-256 duplicate protection;
- audit log untuk perubahan material;
- secret tidak disimpan di repo;
- local API tidak dibuka publik tanpa kebutuhan;
- remote sync menggunakan authenticated outbound HTTPS;
- no direct database write dari Hermes/WhatsApp bridge.

---

# 38. Backup & Recovery

Minimum:

```text
Daily PostgreSQL backup
Daily document backup
```

Tambahkan:

- backup status di System Health;
- restore test berkala;
- checksum;
- satu copy tambahan pada media/penyimpanan terpisah.

---

# 39. System Health

Web App harus mempunyai halaman/status:

```text
PostgreSQL          OK
Backend             OK
Hermes              OK
OCR                 OK
WhatsApp Relay      OK/WARN
Inbox Sync          OK
Last Sync           ...
Pending Remote      ...
Pending Analysis    ...
Failed Jobs         ...
Last Backup         ...
```

Owner tidak perlu melihat terminal.

---

# 40. Acceptance Criteria

## AC-01 — PC Offline Capture

Given PC Finance OFF  
When Owner kirim PDF/foto + caption  
Then remote inbox menyimpan media + metadata  
And status menjadi `PENDING_LOCAL`  
And tidak ada Hermes processing.

## AC-02 — Deferred Analysis

Given backlog remote  
When PC ON  
Then Local Sync Worker mengambil backlog  
And dokumen muncul di Web App  
And baru kemudian Hermes menganalisis.

## AC-03 — Invoice + Transfer Matching

Invoice dan transfer dikirim berdekatan.

Expected:

- dua document;
- satu konteks;
- match evidence;
- tidak membuat duplicate expense.

## AC-04 — Existing Invoice Payment

Bukti transfer cocok dengan invoice existing.

Expected:

- money movement dibuat;
- settlement ke invoice;
- tidak tanya Owner jika safe;
- AP/AR ter-update.

## AC-05 — Unknown Transfer

Bank OUT ditemukan tanpa project/invoice jelas.

Expected:

- cash movement tetap tercatat;
- `REVIEW_REQUIRED`;
- tampil di Web App.

## AC-06 — Multi-Project Payment

Satu payment Rp50jt dialokasikan ke dua project.

Expected:

- satu money movement;
- allocation sum = Rp50jt;
- project cost benar.

## AC-07 — Multi-Bank

Transfer Mandiri ke BCA.

Expected:

- bukan expense;
- saldo per PaymentAccount berubah;
- total Kas & Bank tetap sama.

## AC-08 — Bank Statement Import Duplicate

File yang sama di-upload dua kali.

Expected:

- hash duplicate;
- import kedua diblok/marked duplicate.

## AC-09 — Consultant Report Reconciliation

Laporan P&L dan BS berasal dari journal + report mapping.

Expected:

- debit = credit;
- Assets = Liabilities + Equity;
- section mapping benar.

## AC-10 — Period Lock

Posting ke CLOSED period.

Expected:

- backend block;
- no journal mutation.

---

# 41. Success Metrics

## Cash

- 100% bank statement lines berada dalam status matched/partial/review/explicit ignore.
- Tidak ada movement hilang akibat PC restart.

## Project

- pengeluaran project dapat ditelusuri sampai document.
- unallocated cash terlihat eksplisit.

## Automation

- transaksi rutin strong-match tidak selalu meminta Owner.
- semua ambiguity material masuk review.

## Accounting

- total debit = total credit;
- Balance Sheet balanced;
- posted history immutable.

## Reliability

- duplicate retry tidak membuat double transaction/journal.

---

# 42. CURRENT REPOSITORY AUDIT SNAPSHOT

Bagian ini adalah baseline implementasi aktual yang harus menjadi input Hermes sebelum remediation.

## 42.1 Fondasi yang Dipertahankan

Repo sudah memiliki:

- React/Vite/TypeScript frontend;
- FastAPI backend;
- PostgreSQL + SQLAlchemy;
- Alembic;
- deterministic Accounting Engine;
- PostingRuleRegistry;
- AR/AP;
- retention;
- reversal;
- document ingestion;
- SHA-256;
- Hermes integration;
- Baileys/Meta provider abstraction;
- project allocation;
- reporting;
- audit trail;
- tenant concept;
- test suite yang cukup luas menurut `PROJECT_STATUS.md`.

**Keputusan:** jangan rewrite.

---

# 43. VERIFIED TECHNICAL GAPS FROM SOURCE AUDIT

## GAP-01 — Direct Posting Endpoint Bypasses Review Service

`backend/src/api/v1/transactions.py`

Current:

```text
POST /transactions/{id}/post
POST /transactions/{id}/approve
```

langsung memanggil `AccountingEngine.post_transaction()`.

Sementara `ReviewQueueService.approve_and_post()` mempunyai unresolved-flag dan role checks.

**Risk:** posting path tidak konsisten.

**Fix:** satu `ProcessingPolicy/PostingApplicationService` sebagai entry point authoritative.

---

## GAP-02 — Frontend / Backend Enum Drift

Frontend memakai antara lain:

```text
TRANSFER_INTERBANK
```

Backend:

```text
INTERBANK_TRANSFER
```

Cost Category juga tidak identik.

**Fix:** generate frontend contract dari FastAPI OpenAPI atau automated schema generation.

---

## GAP-03 — Payment Account Tidak Masuk Journal Line

Existing `Transaction.payment_account_id` ada.

Tetapi `JournalLine` belum menyimpan `payment_account_id`.

**Impact:** saldo Mandiri/BCA/BRI tidak dapat dibentuk authoritative dari ledger.

**Fix:** tambahkan accounting dimension `payment_account_id`.

---

## GAP-04 — Bank Reconciliation Domain Belum Lengkap

Belum ada first-class:

```text
MoneyMovement
BankStatementImport
BankStatementLine
Settlement
Reconciliation
```

**Fix:** tambah domain cash/reconciliation.

---

## GAP-05 — Document Link Integrity

`TransactionDocumentLink.transaction_id` tidak mempunyai FK database yang kuat ke `transactions`.

**Fix:** migration FK + tenant validation.

---

## GAP-06 — Migration Enum Drift

Python `TransactionType` mempunyai:

```text
RETENTION_RELEASE
```

tetapi migration enum PostgreSQL awal tidak terlihat menambahkan value tersebut dan migration retention tidak menambahkannya.

**Fix:** PostgreSQL migration verification + enum migration.

---

## GAP-07 — Profit & Loss Mapping Bug

`pl_service.py` mengklasifikasikan other income dengan prefix `71xx` dan other expense dengan `72xx`.

Seeder saat ini mempunyai:

```text
4201 Pendapatan Lain-lain
7101 Beban Non-Operasional / Luar Usaha
```

Mapping ini tidak konsisten.

**Fix:** report mapping metadata, bukan prefix hard-code.

---

## GAP-08 — Balance Sheet Long-Term Liability Belum Implemented

Current Balance Sheet mengumpulkan liability ke current liabilities dan long-term section masih kosong.

**Fix:** `report_section/current_long_term_classification`.

---

## GAP-09 — Current-Year Earnings Perlu Period/Year-End Logic

Current Balance Sheet menghitung revenue-expense kumulatif.

Tanpa formal year-end close dapat mencampur laba tahun sebelumnya.

**Fix:** accounting periods + year-end close + retained earnings.

---

## GAP-10 — Current WhatsApp Transport Tidak Memenuhi Durable PC-Off Requirement

Baileys bridge aktif menurut current project status.

Jika bridge ada di PC Finance:

```text
PC OFF → bridge OFF
```

**Fix:** capture relay independent dari PC Finance + remote inbox.

---

## GAP-11 — Current WhatsApp Review Flow Lebih Luas dari Requirement Baru

Existing implementation mempertahankan human review hard-stop pada intake flows.

Requirement baru:

- no approval via WhatsApp;
- review hanya exception/sensitive;
- safe routine flow dapat auto-process setelah validation.

**Fix:** Processing Policy di backend, bukan Hermes shortcut.

---

## GAP-12 — Sequence Generation Berpotensi Race

Beberapa numbering menggunakan pola `COUNT + 1`.

Saat backlog parallel dapat collision.

**Fix:** PostgreSQL sequence/atomic counter + unique retry.

---

# 44. TECHNICAL REMEDIATION PLAN

Remediation dilakukan incremental. Tidak rewrite.

---

## P0 — Accounting & Data Integrity First

**Priority:** CRITICAL

### P0.1 Unify Posting Entry Point

Affected:

```text
backend/src/api/v1/transactions.py
backend/src/services/review_service.py
backend/src/services/accounting_engine.py
```

Create:

```text
ProcessingPolicyService
```

Responsibilities:

- load transaction;
- validate review flags;
- validate sensitivity;
- validate period;
- determine AUTO_SAFE / HUMAN_REVIEW;
- authorize approval;
- call AccountingEngine only after policy passes.

Remove/lock direct bypass.

### P0.2 API Contract Synchronization

Affected:

```text
frontend/src/types/api.ts
backend/src/models/enums.py
backend OpenAPI
```

Action:

- generate TypeScript types/client from OpenAPI;
- stop duplicate hand-maintained enums;
- add contract CI check.

### P0.3 Database Referential/Tenant Integrity

Action:

- add FK for transaction-document link;
- validate project/document/counterparty/payment account belongs to current org;
- add tests.

### P0.4 PostgreSQL Migration Gate

Action:

- add missing enum migration;
- CI starts disposable PostgreSQL;
- run `alembic upgrade head`;
- run integration tests against PostgreSQL.

SQLite tests tetap berguna, tetapi bukan satu-satunya migration gate.

### P0.5 Fix Report Classification

Affected:

```text
backend/src/services/reporting/pl_service.py
backend/src/services/reporting/balance_sheet_service.py
backend/src/models/coa.py
backend/src/services/coa_seeder.py
```

Action:

- add report mapping fields;
- migrate existing accounts;
- remove prefix-based assumptions for formal grouping;
- add consultant-format regression tests.

### P0 Exit Criteria

- no direct posting bypass;
- frontend/backend contract matches;
- Alembic head works on PostgreSQL;
- P&L grouping correct;
- Balance Sheet balanced;
- tenant/FK tests pass.

---

## P1 — Cash & Multi-Bank Foundation

**Priority:** HIGH

### P1.1 Journal Payment Account Dimension

Migration:

```text
journal_lines.payment_account_id nullable FK
```

Populate for cash/bank journal legs.

### P1.2 MoneyMovement

Create model/service/schema/API.

### P1.3 Settlement

Create:

```text
settlements
settlement_allocations
```

Support:

- one movement → many invoices;
- one movement → many projects;
- partial settlement.

### P1.4 Interbank Transfer Rewrite

Require:

```text
source_payment_account_id
destination_payment_account_id
```

No expense/revenue impact.

### P1 Exit Criteria

- per-bank balance authoritative;
- one payment can settle multiple events;
- project split works;
- total Kas & Bank = sum payment accounts.

---

## P2 — Bank Statement & Reconciliation

**Priority:** HIGH

### P2.1 New Models

```text
bank_statement_imports
bank_statement_lines
bank_reconciliations
```

### P2.2 Import Pipeline

Support:

1. CSV;
2. XLS/XLSX;
3. PDF fallback.

### P2.3 Matching Engine

Rules:

- exact reference;
- amount;
- date;
- bank;
- counterparty;
- invoice;
- project.

### P2.4 Web API

Provide import preview before commit.

### P2.5 Cash Completeness Dashboard

Expose:

- matched;
- unmatched bank;
- unmatched book;
- unallocated total.

### P2 Exit Criteria

- duplicate statement import blocked;
- unmatched movement visible;
- bank balance can be reconciled.

---

## P3 — Durable Offline WhatsApp Inbox

**Priority:** HIGH

### P3.1 Provider Boundary

Preserve:

```text
WhatsAppProvider
BaileysBridgeWhatsAppProvider
MetaProvider
```

Add:

```text
RemoteInboxClient
```

### P3.2 Capture Relay

Move only capture responsibility outside Finance PC.

Recommended interim:

```text
Node.js/Baileys relay
→ authenticated remote inbox API
→ metadata store + object storage
```

No finance DB access.

### P3.3 Local Sync Worker

Responsibilities:

- poll remote inbox;
- claim job;
- download;
- verify SHA-256;
- persist Document + InboxMessage;
- mark synced;
- enqueue local analysis;
- retry safely.

### P3.4 Web App Inbox

Raw message visible before Hermes completes.

### P3.5 Crash/Offline UAT

Test:

- PC off 72 hours;
- multiple PDF/photo/captions;
- PC on;
- backlog complete;
- no duplicate;
- no lost media.

### P3 Exit Criteria

Requirement utama:

> Owner can send while Finance PC is OFF and see the backlog after PC starts.

---

## P4 — Hermes Deferred Analysis & Exception Review

**Priority:** HIGH

### P4.1 Document Session

Group related messages using evidence, not time only.

### P4.2 Match Evidence

Persist matching reasons.

### P4.3 Processing Policy

Initial states:

```text
AUTO_SAFE
REVIEW_REQUIRED
BLOCKED
FAILED
```

### P4.4 No WhatsApp Financial Conversation

Disable/remove MVP expectation for:

- approve by WA;
- reject by WA;
- financial clarification command.

Keep only capture transport.

### P4.5 Review Queue UX

Owner sees:

- original evidence;
- Hermes candidate;
- match evidence;
- affected accounting treatment;
- correction controls.

### P4 Exit Criteria

- safe transactions do not require routine approval;
- ambiguous transactions always enter Web App review;
- Hermes cannot bypass backend validation.

---

## P5 — Project Cost & Owner Dashboard

**Priority:** MEDIUM-HIGH

### P5.1 Dashboard API

Add:

```text
cash_in_period
cash_out_period
net_cash_flow
unallocated_cash
project_spending
```

### P5.2 Project Detail API

Expose:

```text
project cash
project accrual
cost categories
vendor spend
documents
unallocated items
```

### P5.3 Remove/Deprioritize Budget View

Budget vs Actual is not primary because no RAB is available before projects.

### P5 Exit Criteria

Owner can answer:

1. uang perusahaan berapa?
2. bulan ini masuk/keluar berapa?
3. project mana paling banyak belanja?
4. project ini profit berapa?
5. ada uang yang belum teridentifikasi?

---

## P6 — Accounting Period, Opening Balance & Fixed Assets

**Priority:** MEDIUM

### P6.1 AccountingPeriod

Create:

```text
OPEN
SOFT_CLOSED
CLOSED
```

Block posting to closed period.

### P6.2 Opening Balance

Migration/import workflow for consultant starting balances.

### P6.3 Year-End Close

Formal retained earnings behavior.

### P6.4 FixedAsset Register

Asset + depreciation data.

### P6 Exit Criteria

- opening BS reconciles to consultant;
- closed periods cannot mutate silently;
- current-year earnings correct by year.

---

## P7 — Reliability & Operations

**Priority:** MEDIUM

### P7.1 Background Job Queue

Persistent jobs in PostgreSQL.

### P7.2 Sequence Safety

Replace `COUNT + 1` with PostgreSQL sequence/atomic numbering.

### P7.3 Backup Verification

Daily backup + restore test.

### P7.4 System Health Page

Expose service state.

### P7.5 Performance UAT

Backlog:

```text
20 docs
100 docs
worker crash
restart
duplicate upload
```

### P7 Exit Criteria

No duplicate, no lost files, restart-safe.

---

# 45. Proposed Migration Order

Current repository highest visible migration is `013`.

Suggested next migrations conceptually:

```text
014_reporting_mapping_and_integrity
015_payment_account_journal_dimension
016_money_movements_and_settlements
017_bank_statement_reconciliation
018_remote_inbox_and_document_session
019_accounting_periods
020_fixed_assets
021_sequence_hardening
```

Nama/nomor final harus mengikuti branch state aktual saat Hermes mulai implementasi.

Setiap migration:

- non-destructive jika memungkinkan;
- tested on PostgreSQL;
- reversible bila aman;
- no production data mutation without explicit approval.

---

# 46. Hermes Development Execution Order

Karena repo sudah memakai Hermes sebagai development orchestrator, lakukan urutan berikut.

## Phase A — Synchronize Specification

1. tambahkan PRD ini ke `docs/`;
2. update active spec;
3. update clarification bahwa:
   - WhatsApp = capture only;
   - no WA approval;
   - PC-off durable inbox required;
   - Hermes deferred until PC on;
   - review exception-only;
   - cash/project priority;
4. jalankan consistency analysis terhadap constitution.

**Constitution saat ini sebenarnya masih compatible:** ambiguity/sensitive wajib review; automation tidak boleh bypass validation/required approvals.

## Phase B — P0 Remediation

Jangan menambah AI automation sebelum P0 selesai.

## Phase C — Cash Foundation

Implement P1 + P2.

## Phase D — Offline Inbox

Implement P3.

## Phase E — Hermes Automation

Implement P4.

## Phase F — UX

Implement P5.

## Phase G — Accounting Completeness

Implement P6.

## Phase H — Hardening

Implement P7.

---

# 47. Required CI Gates

Sebelum merge setiap phase:

```text
backend unit tests
backend PostgreSQL integration tests
Alembic upgrade head
frontend typecheck
frontend tests
frontend build
lint
repository safety
financial invariant tests
tenant isolation tests
```

Financial invariants:

```text
Debit = Credit
Assets = Liabilities + Equity
No orphan AR/AP
No duplicate journal per source
No posting to CLOSED period
No cross-tenant links
```

---

# 48. Recommended Frontend Route Map

```text
/dashboard

/inbox
/inbox/:id

/projects
/projects/:id

/cash-bank
/cash-bank/:paymentAccountId

/reconciliation
/reconciliation/imports/:id

/review
/review/:id

/transactions
/transactions/:id

/documents
/documents/:id

/receivables
/payables

/reports/profit-loss
/reports/balance-sheet
/reports/cash-flow
/reports/project-profitability
/reports/project-cash
/reports/project-spending
/reports/trial-balance
/reports/general-ledger
/reports/ar-aging
/reports/ap-aging

/master/customers
/master/vendors
/master/payment-accounts
/master/chart-of-accounts

/settings
/system-health
/audit-log
```

---

# 49. Recommended Backend Package Direction

Tidak wajib refactor sekaligus, tetapi target dependency direction:

```text
API
 ↓
Application Services
 ↓
Domain Rules
 ↓
Repositories / SQLAlchemy
 ↓
PostgreSQL
```

External:

```text
Hermes
WhatsApp Relay
OCR
```

tidak boleh:

```text
write PostgreSQL directly
```

Mereka hanya menggunakan authenticated application boundary.

---

# 50. Initial Auto-Safe Whitelist Concept

Bukan final accounting policy, tetapi kandidat awal setelah P0–P4.

Dapat auto-process hanya jika exact/strong match dan seluruh validation pass:

```text
PAY_VENDOR_BILL
CUSTOMER_PAYMENT
INTERBANK_TRANSFER
BANK_CHARGE
```

`DIRECT_PURCHASE` dapat dipertimbangkan setelah klasifikasi project/expense cukup matang.

Selalu review atau policy-sensitive:

```text
OWNER_CONTRIBUTION
OWNER_WITHDRAWAL
JOURNAL_ADJUSTMENT
REVERSAL
TAX_ADJUSTMENT
ASSET_CAPITALIZATION_AMBIGUOUS
RELATED_PARTY
REVENUE_RECOGNITION_AMBIGUOUS
```

---

# 51. Key Open Policies

Belum boleh diinvent oleh Hermes:

- revenue recognition formal;
- capitalization threshold;
- useful life;
- depreciation method;
- inventory valuation;
- owner transaction treatment;
- tax code/rates;
- cutoff period;
- materiality threshold;
- related-party policy.

---

# 52. Definition of Done — MVP Interim

MVP dianggap siap digunakan secara terbatas ketika:

1. P0 selesai;
2. cash/bank per rekening benar;
3. bank statement import/reconciliation bekerja;
4. Owner dapat kirim foto/PDF saat Finance PC off melalui durable capture path;
5. setelah PC on backlog muncul di Web App;
6. Hermes memproses backlog secara deferred;
7. no approval/chat via WhatsApp;
8. review exception dilakukan di Web App;
9. project spending dapat ditelusuri;
10. Laba Rugi dan Neraca mapping benar;
11. journal balance;
12. backup dan restore test tersedia;
13. crash/retry tidak membuat duplicate.

---

# 53. Final Architecture

```text
                         OWNER
                   ┌───────┴────────┐
                   │                │
               WhatsApp          Web App
                   │                │
                   ▼                │
          ALWAYS-ON CAPTURE RELAY   │
                   │                │
                   ▼                │
            REMOTE DURABLE INBOX    │
          metadata + temp media     │
                   │                │
          Finance PC may be OFF     │
                   │                │
        ───────────┴────────────────┘
                   │ PC ON
                   ▼
             LOCAL SYNC WORKER
                   │
                   ▼
               DOCUMENTS
                   │
                   ▼
         DOCUMENT INTELLIGENCE
                   │
                   ▼
                 HERMES
                   │
        candidate + evidence
                   │
          ┌────────┴─────────┐
          ▼                  ▼
    BUSINESS EVENT      MONEY MOVEMENT
          │                  │
          └────────┬─────────┘
                   ▼
               SETTLEMENT
                   │
                   ▼
        PROJECT / ITEM ALLOCATION
                   │
                   ▼
           PROCESSING POLICY
              │          │
              ▼          ▼
         AUTO SAFE    WEB REVIEW
              │          │
              └────┬─────┘
                   ▼
          ACCOUNTING ENGINE
                   │
                   ▼
                JOURNAL
                   │
                   ▼
              POSTGRESQL
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
   CASH FLOW   PROJECT DATA   FINANCIAL
   & BANK      & SPENDING     STATEMENTS
```

---

# 54. Final Product Definition

Financial SaaS Kontraktor adalah sistem keuangan project-based yang menggunakan WhatsApp sebagai asynchronous document capture channel dan Web App sebagai pusat operasional keuangan.

Owner dapat mengirim PDF/foto beserta deskripsi ketika komputer Finance mati. Capture layer yang independen menyimpan pesan dan media lebih dulu. Setelah komputer hidup, Local Sync Worker menarik backlog ke Financial SaaS. Hermes dan OCR baru kemudian menganalisis dokumen, melakukan matching, dan menghasilkan structured candidate.

Cash movement diperlakukan sebagai data first-class dan direkonsiliasi terhadap rekening koran. Business event accrual dipisahkan dari money movement sehingga invoice, pembayaran, DP, retention, project cost, AR/AP, dan journal tidak saling tumpang tindih.

Transaksi rutin yang aman dapat diproses setelah deterministic validation, sedangkan ambiguity dan sensitive events masuk Review Queue pada Web App. Tidak ada approval keuangan melalui WhatsApp pada MVP.

Sistem tetap sederhana bagi Owner tetapi memiliki accounting foundation yang dapat diaudit, direkonsiliasi dengan laporan konsultan, dan dikembangkan ke deployment cloud penuh di masa depan.

---

# 55. Implementation Command for Hermes

Sebelum menulis kode baru, Hermes harus:

1. membaca PRD ini;
2. membaca `AGENTS.md`;
3. membaca constitution;
4. membaca `PROJECT_STATUS.md`;
5. membuat feature spec baru untuk remediation;
6. memetakan setiap requirement ke existing code;
7. menjalankan P0 lebih dulu;
8. tidak melakukan rewrite accounting engine;
9. tidak menghapus data UAT;
10. tidak memindahkan finance database ke cloud pada fase interim;
11. menjaga seluruh financial/tenant/audit invariants;
12. menjalankan PostgreSQL migration gate sebelum merge.

**Golden rule:**

> **Preserve the accounting core; remediate the boundaries, cash model, offline inbox, reporting mapping, and Owner UX.**
