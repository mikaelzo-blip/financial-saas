# MASTER CONCEPT FINAL
## Sistem Keuangan Otomatis Perusahaan Kontraktor
### Single Input • Project-Based Accounting • WhatsApp + Hermes Agent • Excel Financial Database

**Versi:** Final Concept v1  
**Status:** Phase 1 selesai — siap masuk Phase 2 (Data Model)  
**Bahasa:** Indonesia  
**Prinsip utama:** **Akurasi → Traceability → Kemudahan Penggunaan → Automation**

---

# 1. TUJUAN SISTEM

Sistem ini dirancang untuk perusahaan kontraktor/project-based company agar pencatatan keuangan dapat dimulai dari bukti transaksi sehari-hari seperti:

- screenshot bukti transfer dari WhatsApp;
- invoice supplier;
- nota/foto kuitansi;
- PO;
- SPK;
- BAST;
- surat jalan;
- mutasi bank;
- invoice kepada customer;
- dokumen pajak;
- dokumen proyek lainnya.

Target akhirnya:

```text
Dokumen / Bukti
→ Dibaca Hermes
→ Diekstrak
→ Dicocokkan
→ Diklasifikasikan
→ Direview jika perlu
→ Dibuat jurnal otomatis
→ Masuk database
→ Update project
→ Update piutang/utang
→ Update laporan
→ Analisis otomatis
```

Pengguna tidak perlu menjadi akuntan.

---

# 2. PRINSIP DESAIN

Sistem mengikuti prinsip:

> **Simple for user, structured underneath.**

Artinya:

- user cukup memasukkan transaksi sekali;
- user tidak mengisi debit/kredit;
- user tidak menginput piutang secara manual;
- user tidak menginput utang secara manual;
- user tidak menginput Project Cost secara terpisah;
- user tidak menginput angka langsung ke Neraca/Laba Rugi;
- laporan dibentuk otomatis dari database transaksi dan jurnal;
- detail tetap tersimpan agar dapat diaudit dan dianalisis.

---

# 3. SINGLE INPUT — KEPUTUSAN UTAMA

## 3.1 Definisi

**Satu kejadian bisnis hanya diinput satu kali.**

Contoh:

```text
20 Agustus 2026
Invoice Customer Rp100.000.000
```

adalah satu kejadian.

Kemudian:

```text
15 September 2026
Customer membayar Rp100.000.000
```

adalah kejadian berbeda, sehingga dicatat satu kali lagi.

Yang tidak boleh terjadi:

```text
Input invoice ke Transactions
+ input ulang ke Piutang
+ input ulang ke Journal
+ input ulang ke Project Cost
+ input ulang ke Laba Rugi
```

---

# 4. ARSITEKTUR FINAL SISTEM

```text
WhatsApp / PDF / Invoice / Nota / Bank
                    │
                    ▼
              RAW DOCUMENT
                    │
                    ▼
             OCR / EXTRACTION
                    │
                    ▼
           TRANSACTION STAGING
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
       MATCHING           DUPLICATE CHECK
          │                   │
          └─────────┬─────────┘
                    ▼
            TRANSACTION TYPE
                    │
                    ▼
                 PROJECT
                    │
                    ▼
                CATEGORY
                    │
                    ▼
             ACCOUNTING RULE
                    │
                    ▼
              DRAFT JOURNAL
                    │
                    ▼
               VALIDATION
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
        PASS                REVIEW
          │                   │
          ▼                   │
       APPROVE ◄──────────────┘
          │
          ▼
        POSTED
          │
      ┌───┼──────────────┐
      ▼   ▼              ▼
   JOURNAL PROJECT      AR/AP
      │   │              │
      └───┼──────────────┘
          ▼
   FINANCIAL DATABASE
          │
    ┌─────┼──────────────┐
    ▼     ▼              ▼
 NERACA LABA RUGI     CASH FLOW
          │
          ▼
    PROJECT REPORT
          │
          ▼
     AI ANALYSIS
```

---

# 5. POSISI WHATSAPP

WhatsApp akan menjadi **input channel utama** untuk penggunaan sehari-hari.

Pengguna dapat mengirim:

- bukti transfer;
- invoice vendor;
- invoice customer;
- PO;
- SPK;
- BAST;
- surat jalan;
- nota;
- mutasi bank;
- dokumen pendukung lain.

Target:

> **Kirim dokumen melalui WhatsApp → Hermes memproses → user hanya mereview yang perlu → sistem keuangan ter-update.**

---

# 6. CONTOH WORKFLOW WHATSAPP

## 6.1 Bukti Transfer

User kirim screenshot transfer:

```text
Rp8.500.000
Penerima: PT ABC
```

Hermes mencoba membaca:

- tanggal;
- waktu;
- nominal;
- bank asal;
- bank tujuan;
- nama penerima;
- nomor rekening jika terlihat;
- referensi;
- biaya admin;
- caption WhatsApp;
- project candidate;
- invoice candidate.

Hasil contoh:

```text
Document ID:
DOC-2026-000231

Candidate Transaction:
TRX-2026-000151

Penerima:
PT ABC

Nominal:
Rp8.500.000

Jenis Kandidat:
Pembayaran Vendor

Project:
PRJ-2026-014

Invoice:
INV-032/2026

Confidence:
98%

Status:
READY_FOR_APPROVAL
```

---

## 6.2 Bukti Tidak Cukup

Jika transfer hanya menunjukkan:

```text
Rp18.500.000
Penerima: Budi
```

dan tidak ada invoice/project yang cocok:

```text
REVIEW_REQUIRED
PROJECT_UNKNOWN
MISSING_DOCUMENT
```

Hermes tidak boleh menebak.

Contoh pesan review:

```text
⚠ Perlu Review

Nominal:
Rp18.500.000

Penerima:
Budi

Project:
Belum diketahui

Kemungkinan:
- subcontractor
- tenaga kerja
- uang muka operasional
- reimbursement

Pilih project dan jenis transaksi.
```

---

# 7. WHATSAPP TIDAK MENJADI DATABASE

WhatsApp hanya channel masuk.

Setelah dokumen diterima:

```text
WhatsApp
→ download file
→ simpan ke raw_documents
→ generate Document ID
→ proses
```

File asli tidak boleh bergantung pada histori WhatsApp sebagai satu-satunya arsip.

---

# 8. RAW DATA PROTECTION

Struktur penyimpanan yang direkomendasikan:

```text
/Finance_System

  /raw_documents
      /2026
          /01
          /02
          /03

  /processed_documents

  /financial_database

  /reports

  /backup
```

Raw document:

- tidak dimodifikasi;
- tidak ditimpa;
- mempunyai hash/checksum;
- tetap dapat ditelusuri.

---

# 9. IDENTIFIER

## Project

```text
PRJ-2026-001
PRJ-2026-002
```

## Transaction

```text
TRX-2026-000001
TRX-2026-000002
```

## Document

```text
DOC-2026-000001
DOC-2026-000002
```

---

# 10. MODEL ACCOUNTING

Sistem menggunakan:

## Accrual Accounting

Transaksi dicatat ketika hak/kewajiban ekonominya timbul, bukan hanya ketika uang bergerak.

## Double Entry

Setiap jurnal harus memenuhi:

```text
Total Debit = Total Credit
```

Namun user tidak mengisi debit/kredit.

## Project Accounting

Biaya dan pendapatan dianalisis menggunakan:

```text
Project_ID
```

---

# 11. CASH MOVEMENT ≠ EXPENSE

Transfer uang tidak otomatis menjadi biaya.

Contoh transfer Rp10.000.000 ke vendor dapat berarti:

### Bayar invoice lama

```text
Dr Utang Usaha
Cr Kas dan Bank
```

### Uang muka vendor

```text
Dr Uang Muka
Cr Kas dan Bank
```

### Pembelian langsung

```text
Dr Harga Pokok Proyek / Expense
Cr Kas dan Bank
```

### Pembelian aset

```text
Dr Aset Tetap
Cr Kas dan Bank
```

Hermes harus memahami **substansi transaksi**, bukan hanya keyword.

---

# 12. REVENUE, INVOICE, DAN CASH HARUS DIPISAH

Sistem harus menyimpan secara terpisah:

```text
Contract Value
Revenue Recognized
Invoice Issued
Cash Received
```

Contoh:

```text
Contract Value       Rp1.000.000.000
Revenue Recognized   Rp700.000.000
Invoice Issued       Rp800.000.000
Cash Received        Rp500.000.000
```

Keempatnya dapat berbeda.

---

# 13. PROJECT MASTER

Setiap project minimal mempunyai:

```text
Project_ID
Project_Name
Customer
PO_SPK_No
PO_SPK_Date

Original_Contract_Value
Variation_Order
Revised_Contract_Value

Start_Date
Target_End_Date
Actual_End_Date

PIC

Project_Status
Billing_Status
Collection_Status
```

---

# 14. STATUS PROJECT

## Project Status

```text
PLANNED
ACTIVE
ON_HOLD
COMPLETED
CLOSED
CANCELLED
```

## Billing Status

```text
NOT_INVOICED
PARTIALLY_INVOICED
FULLY_INVOICED
```

## Collection Status

```text
NOT_DUE
PARTIALLY_PAID
PAID
OVERDUE
```

---

# 15. COA FINAL — VERSI SEDERHANA

COA dibuat kecil. Detail ditangani melalui:

```text
Transaction Type
Project
Cost Category
Expense Category
Vendor
Customer
Payment Account
Tax Type
```

---

# 16. 1000 — ASET

| Kode | Nama Akun |
|---:|---|
| 1101 | Kas dan Bank |
| 1201 | Piutang Usaha |
| 1301 | Persediaan |
| 1401 | Uang Muka |
| 1402 | Pajak Dibayar Dimuka |
| 1501 | Aset Tetap |
| 1502 | Akumulasi Penyusutan |

---

# 17. PIUTANG USAHA

Piutang Usaha tetap diperlukan.

Artinya:

> customer sudah ditagih tetapi belum membayar seluruh tagihan.

User tidak pernah menginput piutang secara manual.

Contoh:

```text
Invoice Customer       Rp100.000.000
Customer Membayar       Rp60.000.000
────────────────────────────────────
Piutang                  Rp40.000.000
```

Piutang dihitung otomatis.

---

# 18. PIUTANG LAIN-LAIN

Untuk MVP:

> **tidak dibuat sebagai akun aktif.**

Jika nanti dibutuhkan, baru ditambahkan.

---

# 19. KAS DAN BANK SATU AKUN

Laporan utama cukup menunjukkan:

```text
Kas dan Bank
```

Tetapi database tetap membedakan:

```text
Kas
Bank Mandiri
BCA
BRI
Petty Cash
dll.
```

melalui:

```text
Payment_Account_ID
```

Contoh:

```text
Kas                  231.619.410
Mandiri              701.099.934
───────────────────────────────
Kas dan Bank         932.719.344
```

---

# 20. 2000 — KEWAJIBAN

| Kode | Nama Akun |
|---:|---|
| 2101 | Utang Usaha |
| 2102 | Utang Bank & Leasing |
| 2103 | Utang Pajak |
| 2104 | Utang Lainnya |
| 2201 | Uang Muka Customer |

Detail pajak tidak perlu menjadi puluhan COA terpisah.

---

# 21. 3000 — EKUITAS

| Kode | Nama Akun |
|---:|---|
| 3101 | Modal |
| 3102 | Saldo Laba |
| 3103 | Laba/Rugi Tahun Berjalan |
| 3104 | Penarikan / Distribusi Pemilik |

Laba/Rugi Tahun Berjalan dihitung otomatis.

---

# 22. 4000 — PENDAPATAN

| Kode | Nama Akun |
|---:|---|
| 4101 | Pendapatan Proyek dan Jasa |
| 4201 | Pendapatan Lainnya |

Tidak dibuat akun pendapatan untuk setiap project.

Project ditentukan oleh `Project_ID`.

---

# 23. 5000 — HARGA POKOK PROYEK

| Kode | Nama Akun |
|---:|---|
| 5101 | Harga Pokok Proyek / Biaya Langsung Proyek |

Tidak digunakan istilah “Pembelian Barang dan Jasa” sebagai satu-satunya dasar biaya karena:

- pembelian bisa menjadi aset;
- pembelian bisa menjadi persediaan;
- pembayaran bisa menjadi uang muka;
- pembayaran bisa menjadi pelunasan utang.

---

# 24. PROJECT COST CATEGORY

Detail Project Cost tidak dibuat menjadi banyak COA.

Gunakan:

## MAT — Material & Goods

```text
Material
Spare Part
Consumable
Barang Proyek
```

## SUB — Subcontractor

```text
Subcontractor
Specialist Service
```

## LAB — Labor

```text
Tenaga Kerja
Teknisi
Freelance
```

## TRN — Transportation

```text
BBM
Tol
Parkir
Transport Lokal
```

## TRV — Travel

```text
Tiket
Hotel
Akomodasi
Perjalanan
```

## LOG — Logistics

```text
Ongkir
Freight
Trucking
Handling
Delivery
```

## EQP — Equipment

```text
Sewa Alat
Temporary Tools
```

## SIT — Site

```text
PPE
Administrasi Site
Permit Site
Site Expense
```

## OTH — Other Direct Cost

---

# 25. 6000 — BIAYA OPERASIONAL

Gaji dan Fee **dipisahkan**.

| Kode | Nama Akun |
|---:|---|
| 6101 | Gaji & THR |
| 6102 | Fee / Honorarium |
| 6103 | Kantor & Administrasi |
| 6104 | Perjalanan & Transportasi Kantor |
| 6105 | Perizinan |
| 6106 | Professional Service |
| 6107 | Administrasi Bank |
| 6108 | Penyusutan |
| 6199 | Biaya Operasional Lainnya |

---

# 26. GAJI VS FEE

## Gaji & THR

Untuk:

- gaji karyawan;
- payroll;
- THR;
- kompensasi rutin karyawan.

## Fee / Honorarium

Untuk:

- honor tertentu;
- fee marketing;
- referral fee;
- fee non-project;
- pembayaran jasa individu yang bukan payroll.

## Professional Service

Untuk:

- accountant;
- konsultan pajak;
- auditor;
- notaris;
- lawyer;
- konsultan profesional lainnya.

---

# 27. FEE YANG LANGSUNG TERKAIT PROJECT

Jika fee benar-benar merupakan biaya langsung project, jangan masuk `6102`.

Contoh:

```text
Teknisi Freelance
Project: PRJ-2026-014
```

maka:

```text
5101 Harga Pokok Proyek
Cost_Category = LAB
Project_ID = PRJ-2026-014
```

---

# 28. 7000–8000

| Kode | Nama Akun |
|---:|---|
| 7101 | Pendapatan Lain-lain / Jasa Giro |
| 7201 | Beban Lain-lain / Beban Bunga |
| 8101 | Beban Pajak Penghasilan |

---

# 29. TRANSACTION TYPE

Hermes tidak boleh bebas memilih debit/kredit.

Hermes menentukan **Transaction Type**.

Daftar utama:

```text
DIRECT_PURCHASE

VENDOR_BILL
PAY_VENDOR_BILL

VENDOR_ADVANCE
SETTLE_VENDOR_ADVANCE

SUBCONTRACTOR_BILL
PAY_SUBCONTRACTOR

EMPLOYEE_ADVANCE
EMPLOYEE_SETTLEMENT

REIMBURSEMENT
PAY_REIMBURSEMENT

PETTY_CASH_EXPENSE

BANK_TO_CASH
CASH_TO_BANK
INTERBANK_TRANSFER

ASSET_PURCHASE
INVENTORY_PURCHASE
INVENTORY_USAGE

CUSTOMER_INVOICE
CUSTOMER_PAYMENT
CUSTOMER_ADVANCE

REVENUE_RECOGNITION

CUSTOMER_REFUND
VENDOR_REFUND

OWNER_CONTRIBUTION
OWNER_WITHDRAWAL

LOAN_RECEIVED
LOAN_PAYMENT

BANK_CHARGE

OTHER_INCOME
OTHER_EXPENSE

JOURNAL_ADJUSTMENT
REVERSAL
```

---

# 30. ACCOUNTING RULE ENGINE

Accounting Engine menentukan jurnal berdasarkan Transaction Type.

## DIRECT_PURCHASE — Project

```text
Dr Harga Pokok Proyek
Cr Kas dan Bank
```

## VENDOR_BILL — Project

```text
Dr Harga Pokok Proyek
Cr Utang Usaha
```

## PAY_VENDOR_BILL

```text
Dr Utang Usaha
Cr Kas dan Bank
```

## VENDOR_ADVANCE

```text
Dr Uang Muka
Cr Kas dan Bank
```

## SUBCONTRACTOR_BILL

```text
Dr Harga Pokok Proyek
Cr Utang Usaha
```

## EMPLOYEE_ADVANCE

```text
Dr Uang Muka
Cr Kas dan Bank
```

## REIMBURSEMENT

Saat disetujui:

```text
Dr Biaya / Project Cost
Cr Utang Lainnya
```

Saat dibayar:

```text
Dr Utang Lainnya
Cr Kas dan Bank
```

## INTERBANK_TRANSFER

```text
Dr Rekening Tujuan
Cr Rekening Sumber
```

Bukan expense.

## CUSTOMER_PAYMENT

```text
Dr Kas dan Bank
Cr Piutang Usaha
```

## CUSTOMER_ADVANCE

```text
Dr Kas dan Bank
Cr Uang Muka Customer
```

## ASSET_PURCHASE

```text
Dr Aset Tetap
Cr Kas dan Bank / Utang
```

---

# 31. CUSTOMER INVOICE

User cukup memasukkan:

```text
Customer
Project
Invoice No
Amount
Date
Document
```

Sistem menangani:

- AR;
- Piutang Usaha;
- Billing Status;
- document link;
- journal sesuai rule pengakuan pendapatan.

---

# 32. CUSTOMER PAYMENT

Hermes mencari hubungan:

```text
Customer
Invoice
Nominal
Project
Reference
```

Jika cocok:

```text
Dr Kas dan Bank
Cr Piutang Usaha
```

Outstanding invoice otomatis berkurang.

---

# 33. VENDOR BILL & PAYMENT

Contoh invoice vendor:

```text
Vendor Bill Rp25.000.000
Project A
```

Accounting:

```text
Dr Harga Pokok Proyek    25.000.000
Cr Utang Usaha           25.000.000
```

Saat dibayar:

```text
Dr Utang Usaha           25.000.000
Cr Kas dan Bank          25.000.000
```

Biaya tidak tercatat dua kali.

---

# 34. DOCUMENT TYPES

## Contract

```text
PO_CUSTOMER
SPK
CONTRACT
VARIATION_ORDER
```

## Procurement

```text
PURCHASE_ORDER
QUOTATION
VENDOR_INVOICE
SUBCONTRACT_AGREEMENT
```

## Payment

```text
TRANSFER_PROOF
RECEIPT
BANK_STATEMENT
PETTY_CASH_PROOF
```

## Project

```text
SURAT_JALAN
BAST
PROGRESS_REPORT
TIMESHEET
```

## Customer Billing

```text
CUSTOMER_INVOICE
CUSTOMER_RECEIPT
```

## Tax

```text
TAX_INVOICE
WITHHOLDING_DOCUMENT
OTHER_TAX_DOCUMENT
```

---

# 35. DOCUMENT MATCHING

Matching menggunakan beberapa level.

## Exact Match

```text
Invoice No
PO/SPK No
Bank Reference
Document ID
```

## Strong Match

```text
Vendor
Customer
Amount
Date
Project
```

## Fuzzy Match

```text
Description
Vendor-name similarity
Date proximity
Amount proximity
```

---

# 36. DOCUMENT LINKING

Satu project dapat mempunyai banyak dokumen:

```text
PRJ-2026-015
│
├── DOC-001 SPK
├── DOC-004 PO
├── DOC-018 Vendor Invoice
├── DOC-031 Transfer
├── DOC-044 Surat Jalan
└── DOC-060 BAST
```

Satu transaksi juga dapat terhubung ke beberapa dokumen.

Diperlukan konsep:

```text
Transaction_Document_Link
```

---

# 37. DUPLICATE DETECTION

## File Duplicate

Gunakan hash:

```text
SHA256 / File Hash
```

Jika sama:

```text
EXACT_DUPLICATE
```

## Transaction Duplicate

Periksa:

```text
Date
Amount
Bank
Recipient
Reference
```

Jika mencurigakan:

```text
DUPLICATE_SUSPECTED
```

Tidak langsung membuat transaksi kedua.

---

# 38. CONFIDENCE SYSTEM

Gunakan beberapa skor:

```text
OCR_Confidence
Identity_Confidence
Document_Match_Confidence
Project_Confidence
Classification_Confidence
```

Jangan hanya satu skor AI.

Jika satu field kritis rendah, transaksi tetap masuk review.

---

# 39. WORKFLOW STATUS

```text
CAPTURED
EXTRACTED
STAGED
REVIEW_REQUIRED
APPROVED
POSTED
RECONCILED
REVERSED
```

---

# 40. REVIEW FLAGS

Terpisah dari Workflow Status:

```text
OCR_LOW_CONFIDENCE
MISSING_DOCUMENT
DUPLICATE_SUSPECTED
PROJECT_UNKNOWN
VENDOR_UNKNOWN
CUSTOMER_UNKNOWN
AMOUNT_MISMATCH
DATE_MISMATCH
TAX_REVIEW
ACCOUNT_REVIEW
RELATED_PARTY_REVIEW
```

Satu transaksi dapat memiliki beberapa flag.

---

# 41. SAFE TO AUTOMATE

Hermes boleh otomatis:

- membuat Document ID;
- membuat Transaction ID;
- membaca OCR;
- mengambil tanggal;
- mengambil nominal;
- mengambil nama vendor/customer;
- membaca nomor invoice/PO;
- membaca nomor referensi;
- melakukan file hashing;
- mencari vendor;
- mencari project;
- melakukan invoice matching;
- mendeteksi duplicate;
- memilih candidate Transaction Type;
- memilih candidate Cost Category;
- accounting rule lookup;
- membuat draft journal;
- menghitung project cost;
- menghitung outstanding;
- menghitung margin;
- melakukan balance check;
- memperbarui dashboard setelah posting.

---

# 42. REQUIRES REVIEW

Review diperlukan jika:

- project tidak diketahui;
- vendor baru;
- customer baru;
- invoice tidak ditemukan;
- amount mismatch;
- pembayaran sebagian;
- pembayaran gabungan;
- DP vendor;
- DP customer;
- reimbursement;
- cash withdrawal;
- asset vs expense ambigu;
- transaksi owner;
- transaksi pihak terkait;
- tax ambiguity;
- revenue recognition ambiguity;
- split ke beberapa project;
- OCR tidak jelas.

---

# 43. NEVER AUTO-POST PADA MVP

Jangan otomatis posting:

```text
OWNER_TRANSACTION
RELATED_PARTY_TRANSACTION
TAX_ADJUSTMENT
OPENING_BALANCE_ADJUSTMENT
ASSET_CAPITALIZATION_AMBIGUOUS
REVENUE_RECOGNITION_AMBIGUOUS
WRITE_OFF
MANUAL_JOURNAL_ADJUSTMENT
REVERSAL
YEAR_END_ADJUSTMENT
```

Hermes boleh memberi rekomendasi.

User tetap harus approve.

---

# 44. TAX ARCHITECTURE

Accounting dan tax dipisahkan.

```text
Accounting Treatment
≠
Tax Treatment
```

Field minimum:

```text
Tax_Relevance
Tax_Type
Tax_Document_Required
Tax_Document_Available
Tax_Base
Tax_Amount
Tax_Status
Tax_Review
```

Tidak boleh hard-code tarif pajak tanpa verifikasi aturan terbaru.

---

# 45. AUDIT TRAIL

Setiap record penting menyimpan:

```text
Created_At
Created_By

Modified_At
Modified_By

Approved_At
Approved_By

Old_Value
New_Value
Reason
```

---

# 46. POSTED TRANSACTION TIDAK BOLEH DIHAPUS

Jika salah:

```text
Original Transaction
+
Reversal
+
Correct Transaction
```

Bukan overwrite angka lama.

---

# 47. VALIDATION

Sebelum posting:

```text
Transaction ID valid
Date valid
Amount > 0
Transaction Type valid
COA valid
Project valid jika required
Vendor/customer valid jika required
Bank/Cash valid jika required
Document check
Duplicate check
```

Kemudian:

```text
TOTAL DEBIT = TOTAL CREDIT
```

Jika tidak balance:

```text
POSTING_BLOCKED
```

---

# 48. ACCOUNTING VALIDATION

Harus memenuhi:

```text
Assets = Liabilities + Equity
```

Jika selisih:

```text
STOP REPORT FINALIZATION
```

Jangan menyesuaikan angka otomatis hanya agar balance.

---

# 49. PROJECT VALIDATION

```text
Original Contract
+ Variation Order
= Revised Contract Value
```

```text
Invoice Issued
- Customer Payment Allocated
= Outstanding Receivable
```

```text
Revenue Recognized
- Project Cost
= Project Profit
```

---

# 50. LABA RUGI FINAL

```text
LAPORAN LABA RUGI


PENDAPATAN

Pendapatan Proyek dan Jasa
────────────────────────────
TOTAL PENDAPATAN


HARGA POKOK PROYEK

Biaya Langsung Proyek
────────────────────────────
TOTAL HARGA POKOK PROYEK


LABA KOTOR


BEBAN OPERASIONAL

Gaji & THR
Fee / Honorarium
Kantor & Administrasi
Perjalanan & Transportasi
Perizinan
Professional Service
Administrasi Bank
Penyusutan
Biaya Operasional Lainnya
────────────────────────────
TOTAL BEBAN OPERASIONAL


LABA USAHA


PENDAPATAN / BEBAN LAIN-LAIN

Pendapatan Lain-lain / Jasa Giro
Beban Lain-lain / Bunga
────────────────────────────


LABA SEBELUM PAJAK

Beban Pajak Penghasilan

────────────────────────────
LABA BERSIH
```

---

# 51. NERACA FINAL

```text
NERACA


ASET

ASET LANCAR
Kas dan Bank
Piutang Usaha
Persediaan
Uang Muka
Pajak Dibayar Dimuka
────────────────────────────
TOTAL ASET LANCAR


ASET TETAP
Aset Tetap
Akumulasi Penyusutan
────────────────────────────
TOTAL ASET TETAP


TOTAL ASET
```

```text
KEWAJIBAN

Utang Usaha
Utang Bank & Leasing
Utang Pajak
Utang Lainnya
Uang Muka Customer
────────────────────────────
TOTAL KEWAJIBAN


EKUITAS

Modal
Saldo Laba
Laba/Rugi Tahun Berjalan
Penarikan / Distribusi Pemilik
────────────────────────────
TOTAL EKUITAS


TOTAL KEWAJIBAN + EKUITAS
```

---

# 52. PROJECT P&L

```text
PROJECT PRJ-2026-014


Original Contract
+ Variation Order
────────────────────────
Revised Contract Value


Revenue Recognized


PROJECT COST

Material
Barang / Spare Part
Subcontractor
Labor
Technician
Transport
Travel
Logistics
Rental
Site
Other
────────────────────────
TOTAL PROJECT COST


PROJECT PROFIT


PROJECT MARGIN %
```

---

# 53. PROJECT CASH INFORMATION

Dipisahkan dari profit:

```text
Invoice Issued
Payment Received
Receivable

Cash Received
Cash Spent
Project Cash Surplus / Deficit
```

Karena:

> **Project Profit ≠ Project Cash Position**

---

# 54. BUDGET VS ACTUAL

Setiap project dapat mempunyai:

```text
Budget
Actual
Variance
```

Contoh:

```text
Material

Budget     Rp50.000.000
Actual     Rp60.000.000
Variance   Rp10.000.000 unfavorable
```

Hermes dapat memberi warning ketika biaya mendekati/melewati budget.

---

# 55. DASHBOARD

Dashboard utama:

```text
Kas dan Bank
Pendapatan
Harga Pokok Proyek
Laba Kotor
Biaya Operasional
Laba Bersih
Piutang
Utang
Project Aktif
Project Cost
Project Margin
Outstanding Invoice
Cash Flow
```

---

# 56. AI MANAGEMENT INSIGHT

Hermes dapat mendeteksi:

- project margin rendah;
- biaya terlalu tinggi;
- budget overrun;
- overdue invoice;
- piutang terlalu lama;
- vendor outstanding;
- transaksi tanpa project;
- transaksi tanpa dokumen;
- transaksi duplicate;
- unusual transaction;
- expense spike;
- negative project cash flow;
- bank mismatch;
- missing tax document.

Contoh:

```text
Project PRJ-2026-012 memiliki margin 8,4%,
lebih rendah dari rata-rata project.

Penyebab terbesar:
Subcontractor Rp42.000.000,
35% di atas budget.
```

---

# 57. EXCEL TARGET STRUCTURE

Workbook target:

```text
00_DASHBOARD
01_PROJECTS
02_TRANSACTIONS
03_JOURNAL
04_COA

05_VENDORS
06_CUSTOMERS

07_INVOICES_AR
08_BILLS_AP

09_BANK
10_DOCUMENTS

11_TAX
12_BUDGET
13_PROJECT_COST
14_RECONCILIATION

15_SETTINGS
16_REVIEW_QUEUE
17_AUDIT_LOG
```

Tidak semua sheet harus dibangun penuh di MVP pertama.

---

# 58. 04_COA TIDAK MENYIMPAN SALDO

Struktur:

```text
Account_Code
Account_Name
Account_Type
Normal_Balance
Report_Group
Active
```

Tidak ada:

```text
Debit Balance
Credit Balance
```

Saldo dihitung dari `03_JOURNAL`.

---

# 59. 02_TRANSACTIONS MENJADI SUMBER INPUT UTAMA

Konsep field:

```text
Transaction_ID
Date

Transaction_Type
Description
Amount

Project_ID

Counterparty

Vendor_ID
Customer_ID

Cost_Category
Expense_Category

Payment_Account

Invoice_No
PO_SPK_No

Document_ID

Tax_Status

Confidence

Workflow_Status
Review_Flag
```

---

# 60. 03_JOURNAL OTOMATIS

Field:

```text
Journal_ID
Transaction_ID
Date

Account_Code
Account_Name

Debit
Credit

Project_ID

Description
```

User tidak menginput journal manual untuk transaksi normal.

---

# 61. DATA WHATSAPP YANG PERLU DISIMPAN

Untuk setiap pesan/dokumen:

```text
Source_Channel
Source_Message_ID
Source_Chat_ID
Source_Sender
Source_Timestamp
Original_File_Name
Original_Mime_Type
File_Hash
Caption
```

---

# 62. MESSAGE / DOCUMENT RELATIONSHIP

Target Phase 2:

```text
WHATSAPP MESSAGE
       │
       ▼
    DOCUMENT
       │
       ▼
DOCUMENT LINK
       │
       ├── PROJECT
       ├── TRANSACTION
       ├── INVOICE
       ├── PO/SPK
       └── PAYMENT
```

---

# 63. REFERENSI LAPORAN KONSULTAN

Laporan konsultan perusahaan akan digunakan sebagai:

- reference layout;
- reconciliation benchmark;
- saldo awal;
- referensi struktur Neraca;
- referensi struktur Laba Rugi;
- referensi aset tetap;
- referensi akumulasi penyusutan;
- referensi laba ditahan;
- referensi laba tahun berjalan;
- referensi pajak.

Namun sistem tidak meniru mentah jika ada klasifikasi yang perlu disederhanakan atau diperbaiki.

---

# 64. PERBEDAAN ANTARA TAMPILAN DAN DATABASE

User melihat sederhana:

```text
Jenis Transaksi
Customer / Vendor
Project
Nominal
Kategori
Bayar dari / diterima ke
Dokumen
```

Sistem di belakang menyimpan detail:

```text
Transaction Type
COA
Debit
Credit
Project ID
Vendor ID
Customer ID
Cost Category
Expense Category
Payment Account
Document ID
Confidence
Tax Status
Audit Trail
```

---

# 65. CONTOH UI SEDERHANA

```text
Jenis:
Pembelian Project

Project:
Docking Kapal A

Kategori:
Material

Vendor:
PT ABC

Nominal:
Rp8.500.000

Pembayaran:
Mandiri

Dokumen:
invoice.pdf
```

User tekan:

```text
APPROVE
```

Accounting Engine menghasilkan:

```text
Dr 5101 Harga Pokok Proyek
Cr 1101 Kas dan Bank
```

User tidak perlu melihat jurnal jika tidak ingin.

---

# 66. MVP YANG DIREKOMENDASIKAN

MVP awal fokus pada:

```text
Projects
Transactions
Journal
COA
Vendors
Customers
Bank
Documents
Project Cost
Review Queue
Audit Log
Dashboard
```

Modul AR/AP, Budget, Tax dan Reconciliation dapat ditambahkan bertahap setelah core stabil.

---

# 67. IMPLEMENTATION ROADMAP

## Phase 1 — Business & Accounting Design

**Status: selesai.**

Output:

- project structure;
- COA;
- transaction type;
- cost category;
- document type;
- accounting rule;
- approval logic;
- WhatsApp input concept.

---

## Phase 2 — Data Model

Selanjutnya desain:

- tabel;
- kolom;
- primary key;
- foreign key;
- relationship;
- required/optional field;
- validation rule.

---

## Phase 3 — Excel MVP

Bangun workbook minimum:

```text
Projects
Transactions
Journal
COA
Bank
Documents
Project Cost
Dashboard
Review Queue
Audit Log
```

---

## Phase 4 — Accounting Engine

Bangun mapping deterministic:

```text
Transaction Type
→ Accounting Rule
→ Debit
→ Credit
```

---

## Phase 5 — AR/AP

Tambahkan:

- Customer Invoice;
- Vendor Bill;
- Outstanding;
- Partial Payment;
- Aging.

---

## Phase 6 — Bank Reconciliation

Tambahkan:

```text
MATCHED
PARTIAL_MATCH
UNMATCHED_BANK
UNMATCHED_BOOK
REVIEW_REQUIRED
```

---

## Phase 7 — Document AI

Tambahkan:

- OCR screenshot;
- invoice OCR;
- receipt OCR;
- PO/SPK extraction;
- BAST extraction;
- automatic matching.

---

## Phase 8 — Hermes Review Assistant

Hermes dapat:

- meminta project;
- meminta invoice;
- menampilkan candidate transaction;
- menerima approval;
- menjelaskan discrepancy.

---

## Phase 9 — Financial Statements

Generate:

- Laba Rugi;
- Neraca;
- Cash Flow;
- General Ledger;
- Trial Balance;
- AR/AP;
- Project P&L;
- Budget vs Actual.

---

## Phase 10 — AI Analytics

Tambahkan:

- anomaly detection;
- margin warning;
- budget overrun;
- overdue invoice;
- unusual payment;
- missing document;
- cash flow warning.

---

## Phase 11 — WhatsApp Production Integration

Aktifkan WhatsApp sebagai input production setelah finance engine stabil.

---

# 68. KEPUTUSAN YANG DI-LOCK

1. **Single input.**
2. Kas dan Bank satu akun di laporan.
3. Detail rekening tetap disimpan di belakang.
4. Piutang Usaha tetap ada.
5. Piutang Usaha otomatis, bukan input manual.
6. Piutang Lain-lain tidak aktif di MVP.
7. Harga Pokok Proyek dipakai sebagai biaya langsung utama.
8. Detail Material/Subcon/BBM/Logistik ada sebagai Cost Category.
9. Gaji & THR dipisahkan dari Fee/Honorarium.
10. Professional Service dipisahkan dari Fee.
11. Project menjadi pusat analisis.
12. User tidak mengisi debit/kredit.
13. Transaction Type menentukan Accounting Rule.
14. Journal dihasilkan otomatis.
15. Semua laporan berasal dari database/journal.
16. Tidak ada angka laporan yang diketik manual.
17. WhatsApp menjadi input channel utama.
18. Dokumen asli harus disimpan.
19. Hermes boleh mengklasifikasi dan membuat draft.
20. Transaksi ambigu tetap melalui Review Queue.
21. Tax Engine terpisah dari Accounting Engine.
22. Posted transaction diperbaiki dengan reversal, bukan overwrite.
23. Semua perubahan penting memiliki audit trail.
24. Jika jurnal atau laporan tidak balance, finalization dihentikan.
25. Sistem harus tetap mudah digunakan oleh non-akuntan.

---

# 69. HAL YANG MASIH MEMERLUKAN VERIFIKASI / POLICY

Belum dikunci:

- standar akuntansi formal perusahaan;
- revenue recognition policy;
- capitalization threshold aset;
- masa manfaat aset;
- metode penyusutan;
- kebijakan persediaan;
- treatment transaksi pemilik;
- detail pajak;
- tax rate;
- tax code;
- cutoff period;
- materiality threshold.

Hermes tidak boleh membuat kebijakan ini sendiri.

---

# 70. DEFINISI FINAL SISTEM

Secara singkat:

> **Sistem Keuangan Otomatis Kontraktor adalah sistem single-input berbasis project, di mana dokumen dan transaksi dapat dikirim melalui WhatsApp, dibaca dan dicocokkan oleh Hermes, dikonversi menjadi Transaction Type dan Project, diterjemahkan oleh Accounting Rule menjadi jurnal double-entry, kemudian otomatis memperbarui database, piutang/utang, Project Cost, Neraca, Laba Rugi, Cash Flow, Dashboard dan management insight, dengan review manusia untuk transaksi ambigu.**

---

# 71. NEXT STEP

Masuk ke:

## PHASE 2 — DATA MODEL

Tujuan Phase 2:

- finalisasi tabel;
- field;
- primary key;
- foreign key;
- relationship;
- required field;
- validation rule;
- relationship WhatsApp → Document → Transaction → Journal → Report.

**Belum membuat file Excel sebelum Phase 2 selesai.**
