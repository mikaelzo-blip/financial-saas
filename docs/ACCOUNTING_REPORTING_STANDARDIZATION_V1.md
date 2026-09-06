# Accounting & Reporting Standardization Specification (v1.0 - RC1 Locked Policy)

**Status**: OWNER-APPROVED FOR RC1  
**Standard**: SAK EP-ORIENTED (Baseline architectural orientation, NOT claimed as formally certified SAK EP compliant until reviewed by the company's accountant/consultant).  
**Architecture**: Modular Monolith. Financial PostgreSQL is authoritative system of record. Single Input, Double-Entry (`Total Debit == Total Credit`), Derived Balances, Period Guarded. Commercial accounting and fiscal reconciliation remain strictly separate.

---

## 1. Formal Profit & Loss (Authoritative Company P&L)

Formal Profit & Loss follows the company's existing consultant-style visual and logical structure. This report represents authoritative company profit and loss. Project dashboards and management summaries must **NEVER** override this result.

```text
  Pendapatan / Peredaran Usaha
- Harga Pokok Proyek / Harga Pokok Penjualan (HPP)
--------------------------------------------------
= LABA KOTOR (Gross Profit)
- Beban Umum dan Administrasi (Beban Operasional)
--------------------------------------------------
= LABA USAHA / EBIT (Operating Profit)
+ Pendapatan Lain-lain
- Biaya Lain-lain / Bank
--------------------------------------------------
= LABA SEBELUM PAJAK / EBT (Earnings Before Tax)
- Beban / Taksiran Pajak Penghasilan
--------------------------------------------------
= LABA SETELAH PAJAK / EAT (Profit After Tax / Net Profit)
```

---

## 2. Project Profitability & Project Reporting (Management Summary)

Project Profitability is a **MANAGEMENT SUMMARY ONLY**. It:
- Does NOT create journal entries.
- Does NOT recognize company revenue independently of authoritative customer invoices.
- Does NOT modify the formal company Profit & Loss statement.
- Is NOT a tax return.

### Key Dimensions to Distinguish
The project dashboard and project reports must clearly distinguish:
1. **Nilai Kontrak** (Contract Value): Original plus approved variation orders.
2. **Sudah Diinvoice** (Invoiced Amount / Revenue Recognized): Invoiced progress claims.
3. **Cash Diterima** (Cash Received): Collected customer payments.
4. **Piutang** (Receivable Outstanding): Uncollected invoiced customer claims.
5. **Retensi** (Retention): Withheld customer retention balance (`COA 1202`).
6. **Biaya Langsung Proyek** (Direct Project Cost): Attributable project costs.
7. **Laba Kotor Proyek** (Gross Project Profit): Primary project metric.
8. **Margin Proyek** (Gross Margin %): Gross profit divided by invoiced revenue.
9. **Cash Keluar Proyek** (Cash Spent): Real cash disbursements attributed to the project.
10. **Posisi Kas Proyek** (Project Cash Position): Cash received minus cash spent.

### Metrics Definitions
- **PRIMARY RESULT - Laba Kotor Proyek (Gross Project Profit)**:
  ```text
  Laba Kotor Proyek = Invoiced Project Revenue - Direct Project Costs
  ```
- **Direct Project Costs** include:
  - Material & Bahan Bangunan (`MAT`)
  - Subkontraktor & Pekerjaan Spesialis (`SUB`)
  - Upah Tenaga Kerja Langsung (`LAB`)
  - Sewa Alat Berat & Perkakas (`EQP`)
  - Transportasi & Bahan Bakar Proyek (`TRN`)
  - Perjalanan Dinas Proyek (`TRV`)
  - Logistik & Ekspedisi Proyek (`LOG`)
  - Operasional Lapangan & K3 (`SIT`)
  - Direct Project Fee / Commission
  - Biaya Langsung Proyek Lainnya (`OTH`)

- **SECONDARY MANAGEMENT RESULT - Project Net Contribution**:
  ```text
  Project Net Contribution =
      Gross Project Profit
    - Direct Project Fee (not already included in direct costs)
    - Direct Project Bank Charges / Interest
    - Project-specific Final Tax (when explicitly applicable)
  ```

- **Special Financial Invariants for Projects**:
  - **Loan Principal (Pokok Pinjaman)**: NEVER an expense. Shows strictly in Project Cash / Financing information; affects Project Cash Position, NEVER Project Profit.
  - **PPh Withheld (Prepaid/Creditable Tax)**: Shows separately as tax withheld. Does NOT automatically reduce Gross Project Profit.
  - **PPh Final Proyek**: Shows separately. Only reduces Project Net Contribution when transaction tax treatment explicitly declares the PPh as final and project-specific. Never globally assume all projects are subject to PPh Final.
  - **Project Cash Position**:
    ```text
    Posisi Kas Proyek = Cash Received - Cash Spent
    ```

---

## 3. Fixed Asset Book Policy & Straight-Line Depreciation

### Book Policy Principles
- **Depreciation Method**: Default is **STRAIGHT LINE** (Garis Lurus).
- **Depreciation Start**: When the asset is **AVAILABLE FOR USE** (`available_for_use_date`). Never depreciate before this date.
- **Residual Value**: Default is `0.00`.
- **Depreciable Amount**: `Acquisition Cost - Residual Value`.
- **Monthly Depreciation**: `Depreciable Amount / Useful Life (Months)`.
- **Ceiling Guard**: Accumulated depreciation must NEVER exceed the depreciable amount.
- **Immutability Guard**: Posted depreciation journals cannot be edited destructively; historical posted depreciation is never rewritten.
- **Accounting Posting**: Straight-line monthly depreciation posts:
  - `Debit 6105 / Beban Penyusutan Aset Tetap`
  - `Credit 1502 / Akumulasi Penyusutan Aset Tetap`

### Default Useful Life by Category
- **Computer / Laptop**: 4 years (48 months)
- **Office Equipment (Peralatan Kantor)**: 4 years (48 months)
- **Light Project Tools (Peralatan Proyek Ringan)**: 4 years (48 months)
- **Major Project Equipment (Alat Berat Proyek)**: 8 years (96 months)
- **Vehicle (Kendaraan Operasional/Proyek)**: 8 years (96 months)
- **Permanent Building (Bangunan Permanen)**: 20 years (240 months)

*Override Policy*: Category defaults may be overridden during asset registration or adjustment with:
- Reason / Justification
- User ID
- Timestamp
- Complete audit trail

### Book vs. Fiscal Depreciation
- Book depreciation (komersial) and fiscal depreciation (pajak) are separate concepts.
- The system must NEVER force the book depreciation schedule to equal the fiscal schedule.
- Future/current schema supports:
  - Book: useful life, depreciation method.
  - Fiscal: fiscal asset group (Golongan I, II, III, IV, Bangunan), fiscal useful life, fiscal method.
- Tax assumptions are not globally hard-coded.

---

## 4. Capitalization Policy

- **Capitalization Threshold**: **IDR 5,000,000** and expected useful life / benefit **> 12 months**.
- **Nature**: This is **COMPANY BOOK POLICY**, not a universal DJP safe-harbor rule.
- **Classification Rules**:
  - Purchase >= IDR 5,000,000 AND benefit > 12 months: `FIXED_ASSET_CANDIDATE`
  - Purchase < IDR 5,000,000: `EXPENSE_DEFAULT` (Direct Project Cost or OPEX)
  - Bulk purchases (e.g. 10 units @ 1M = 10M total), major improvements, or ambiguous items: `REVIEW_REQUIRED`.
  - Manual override is permitted with recorded reason and user audit trail.
  - Historical expenses are NOT automatically converted into assets retroactively.

---

## 5. Project Material & Inventory Policy

- **Immediate consumption**: Material purchased and directly delivered/installed at job site -> `PROJECT COGS` (`COA 5101`).
- **Stored for future use**: Material delivered to central warehouse/staging -> `MATERIAL INVENTORY` (`COA 1401`).
- **Partially used**: Split allocation across COGS and Inventory.
- **Uncertain / Ambiguous**: Routes to `REVIEW_REQUIRED`.
- **Subsequent consumption**: When previously inventoried material is later consumed on a project:
  - `Debit 5101 (Harga Pokok Proyek)`
  - `Credit 1401 (Persediaan Material Proyek)`
  - **NON-CASH Event**: Does NOT create a `MoneyMovement` or bank payment event.
  - Does NOT implement a heavy warehouse ERP; lightweight inventory tracking is sufficient.

---

## 6. Formal Tax & Fiscal Policy

- Commercial Profit & Loss remains authoritative double-entry accounting.
- Never automatically assume `EBT = Taxable Income`.
- Fiscal reconciliation layer supports:
  - Positive fiscal corrections (koreksi fiskal positif: non-deductible expenses, entertainment without nominal list, etc.)
  - Negative fiscal corrections (koreksi fiskal negatif)
  - Final income separation (penghasilan dikenakan PPh Final)
  - Creditable withholding / prepaid tax (PPh 23, PPh 22)
  - Book vs. fiscal depreciation differences
  - Corporate tax payable calculation
- Tax rates and tax regimes must remain configurable per fiscal year.

---

## 7. Report Integrity & Hard Tie-Out Invariants

All formal financial reports must strictly tie out:
1. **Total Debit = Total Credit** across all posted journals and Trial Balance.
2. **Assets = Liabilities + Equity** on the Balance Sheet.
3. **Current-Year Profit on Balance Sheet = Formal Profit After Tax (Net Profit) from Profit & Loss**.
4. **Zero Synthetic Balancing**: Plug entries are strictly prohibited.
5. **Integrity Error Guard**: If any report tie-out fails, return `integrity_status="REPORT_INTEGRITY_ERROR"` and do not allow the report to be marked or exported as `FINAL`.

---

## 8. Owner-Friendly Language Policy & Help Text

The entire owner-facing web application must use simple, accessible Indonesian that a non-accountant can understand.
**Rule**: Simplify LANGUAGE. Do NOT simplify accounting logic. Internal models, APIs, and database columns remain technical.

### Owner UI Terminology Mapping
| Technical / Accounting Term | Owner-Facing Indonesian Label | Context / Help Text |
|---|---|---|
| Accounts Receivable (AR) | **Piutang Pelanggan** | Tagihan pelanggan yang belum dibayar. |
| Accounts Payable (AP) | **Utang Vendor** | Tagihan vendor yang belum dibayar. |
| MoneyMovement | **Mutasi Kas & Bank** | Aliran dana nyata masuk atau keluar dari rekening. |
| Settlement | **Pencocokan Pembayaran** | Menghubungkan pembayaran dengan invoice/tagihan terkait. |
| Bank Reconciliation | **Cocokkan Mutasi Bank** | Mencocokkan catatan sistem dengan mutasi rekening bank. |
| Chart of Accounts (COA) | **Daftar Akun Akuntansi** | Daftar kode dan nama akun pembukuan perusahaan. |
| General Ledger | **Buku Besar** | Catatan lengkap mutasi per akun akuntansi. |
| Trial Balance | **Neraca Saldo** | Ringkasan saldo seluruh akun sebelum dibuat laporan keuangan. |
| Retained Earnings | **Saldo Laba** | Akumulasi laba bersih tahun-tahun sebelumnya yang ditahan. |
| Current Year Earnings | **Laba Tahun Berjalan** | Laba bersih usaha selama tahun berjalan. |
| COGS | **Harga Pokok Proyek** | Biaya langsung yang dikeluarkan untuk menyelesaikan proyek. |
| Operating Expense | **Biaya Operasional** | Biaya umum, administrasi, dan operasional kantor. |
| Fixed Asset | **Aset Tetap** | Barang modal bernilai signifikan dengan masa manfaat > 1 tahun. |
| Depreciation | **Penyusutan** | Pembagian biaya aset selama masa manfaatnya. |
| Inventory | **Persediaan Material** | Stok bahan bangunan/material yang belum terpasang di proyek. |
| Review Required | **Perlu Diperiksa** | Transaksi memerlukan konfirmasi atau verifikasi manual. |
| Unallocated Cash | **Uang Masuk/Keluar Belum Dicocokkan** | Kas masuk atau keluar yang belum dihubungkan ke tagihan. |
| Interbank Transfer | **Transfer Antar Rekening** | Pemindahan dana antar rekening kas/bank internal perusahaan. |
| Counterparty | **Pelanggan / Vendor** | Rekanan bisnis (klien pembeli atau vendor pemasok). |
| Gross Project Profit | **Laba Kotor Proyek** | Invoice proyek dikurangi biaya langsung proyek. |
| Project Gross Margin | **Margin Proyek** | Persentase laba kotor dibanding nilai yang sudah diinvoice. |
| Project Cash Position | **Posisi Kas Proyek** | Cash yang sudah diterima dikurangi cash yang keluar untuk proyek. |
| PPh Withheld | **PPh Dipotong** | Pajak yang dipotong saat pelanggan membayar. Bukan biaya langsung. |
| Loan Principal | **Pokok Pinjaman** | Pengembalian pokok utang. Mengurangi kas dan utang, bukan laba. |

### Formal Report Titles
Formal accounting statements retain standardized statutory names:
- **Laporan Posisi Keuangan (Neraca)**
- **Laporan Laba Rugi**
- **Laporan Perubahan Ekuitas**
- **Laporan Arus Kas**
- **Buku Besar**
- **Neraca Saldo**
- **Catatan Atas Laporan Keuangan (CALK)**

---

## 9. Locked Standard Chart of Accounts Mapping

Preserve stable account codes. Owner UI displays friendly Indonesian descriptions without altering account numbers:
- `1101`: Kas & Bank (Kas Operasional & Rekening Bank)
- `1201`: Piutang Pelanggan (Piutang Usaha Proyek)
- `1202`: Piutang Retensi (Jaminan Pemeliharaan Proyek)
- `1301`: Uang Muka Vendor (Uang Muka Pembelian)
- `1401`: Persediaan Material Proyek
- `1501`: Aset Tetap Operasional & Proyek
- `1502`: Akumulasi Penyusutan Aset Tetap
- `2101`: Utang Vendor (Utang Usaha Pembelian)
- `2201`: Uang Muka Pelanggan (Pendapatan Diterima di Muka)
- `2301`: Utang Pajak (PPN, PPh)
- `2401`: Biaya yang Masih Harus Dibayar (Akrual)
- `2501`: Pinjaman / Utang Bank Jangka Panjang
- `3101`: Modal Disetor
- `3201`: Saldo Laba Ditahan
- `3301`: Prive / Penarikan Pemilik
- `4101`: Pendapatan Proyek & Jasa
- `4201`: Pendapatan Lain-lain
- `5101`: Harga Pokok Proyek (Material, Upah, Subkon, Alat)
- `6101` - `6109`: Biaya Operasional Kantor & Administrasi
- `7101`: Biaya di Luar Usaha & Administrasi Bank
- `8101`: Beban Pajak Penghasilan (PPh Badan / Final)
