# Accounting & Reporting Standardization Specification (v1.0)

**Standard**: SAK EP-Oriented (Baseline architectural orientation, NOT claimed as formally certified SAK EP compliant).  
**Architecture**: Modular Monolith. Financial PostgreSQL is authoritative system of record. Single Input, Double-Entry (`Total Debit == Total Credit`), Derived Balances, Period Guarded.

---

## 1. Reporting Layers & Presentation Architecture

Financial reporting is structured into four non-overlapping functional layers:

### Layer A: Owner View (Operational Management)
Designed for non-accountant executive oversight. Strict default mode is **Ringkas** (Summary), toggleable to **Detail**. Debits/credits are abstracted away.
- **Total Kas & Bank**: Real-time aggregated liquidity across cash and bank accounts (`COA 1001-1199`).
- **Uang Masuk**: Real cash receipts from customer payments, non-project income, and capital contributions.
- **Uang Keluar**: Real cash disbursements for vendor bills, project direct expenses, operational overhead, and tax payments.
- **Net Cash Flow**: Total Uang Masuk minus Total Uang Keluar across the period.
- **Piutang Usaha**: Outstanding uncollected customer receivables (`COA 1201`).
- **Utang Usaha**: Outstanding unpaid vendor obligations (`COA 2101`).
- **Project Spending**: Cumulative cash disbursements and accrual direct costs attributed to projects.
- **Project Profitability**: Accrual performance (`Recognized Revenue - Project Cost / HPP`).
- **Project Cash Position**: Liquidity performance (`Cash Collected - Cash Disbursed`).
- **Review / Exception Items**: Items flagged for low extraction confidence, missing fields, or pending verification.

*Traceability Invariant*: Every number on the Owner View must trace back:  
`Report -> JournalEntry -> Transaction (Business Event) -> Settlement / MoneyMovement -> Source Document`.

### Layer B: Formal Financial Statements
Authoritative accounting statements generated strictly from posted double-entry journal entries:
1. **Laporan Posisi Keuangan (Neraca / Balance Sheet)**: Strictly enforces `Assets = Liabilities + Equity` without synthetic plug rows.
2. **Laporan Laba Rugi (Income Statement)**: Gross profit, operating profit, and net income before/after tax.
3. **Laporan Perubahan Ekuitas (Statement of Changes in Equity)**: Opening equity, capital contributions, current year profit/loss, owner draws (Prive), and closing equity.
4. **Laporan Arus Kas (Statement of Cash Flows)**: Direct/indirect classification into Operating, Investing, and Financing activities.
5. **Catatan Atas Laporan Keuangan (CALK)**: Framework containing deterministic general entity information, declared accounting policies, and breakdown notes.

### Layer C: Supporting Accounting Reports
- Neraca Saldo (Trial Balance)
- Buku Besar (General Ledger)
- AR Aging (Aging Piutang)
- AP Aging (Aging Utang)
- Bank Reconciliation (Rekonsiliasi Bank)
- Fixed Asset Schedule (Daftar Aset Tetap)
- Accounting Integrity Diagnostics (Zero discrepancy verification)

### Layer D: Project Management Reports
- Project Profitability (`Revenue Recognized - Project Direct Cost`)
- Project Cash Position (`Cash Received - Cash Disbursed`)
- Project Spending breakdown (Materials, Subcontractors, Labor, Equipment, Overhead)
- Retention & Invoicing status (`Contract Value, Billed, Retention Withheld, Retention Released, Cash Collected`)

---

## 2. Locked Chart of Accounts (COA) Structure

The standard contractor COA structure is preserved. No broad redesigns:
- `1xxx`: Assets (Kas & Bank, Piutang Usaha, Piutang Retensi, Uang Muka, Persediaan Material & Perlengkapan Proyek, Aset Tetap, Akumulasi Penyusutan)
- `2xxx`: Liabilities (Utang Usaha, Utang Subkontraktor, Utang Gaji, Utang Pajak, Pendapatan Diterima di Muka)
- `3xxx`: Equity (Modal Disetor, Saldo Laba Ditahan, Prive / Penarikan Pemilik)
- `4xxx`: Revenue (Pendapatan Kontrak Konstruksi, Pendapatan Jasa, Pendapatan Lain-lain)
- `5xxx`: Project Cost / HPP (Material Langsung, Upah Tenaga Kerja Langsung, Subkontraktor, Sewa Alat, Biaya Proyek Lainnya)
- `6xxx`: Operating Expense (Beban Gaji Kantor, Beban Sewa, Beban Utilitas, Beban Profesional, Beban Umum & Administrasi)
- `7xxx`: Other / Non-Operating (Pendapatan Bunga, Beban Bunga, Biaya Administrasi Bank)
- `8xxx`: Income Tax (Beban Pajak Penghasilan Final PPh 4(2), Beban PPh Badan)

*Strict Separations*:
- `3301` is reserved strictly for **Prive / Penarikan Pemilik**. Synthetic or calculated current-year earnings MUST use a presentation-only identifier (e.g. `EQ-CY`), never account `3301`.
- Salary/payroll expenses (`COA 6101` / direct project labor `COA 5201`) and fee/commission/professional expenses (`COA 6104`) MUST remain distinct.

---

## 3. Cash & Money Movement Architecture

`MoneyMovement` is the authoritative operational representation of cash and bank events:
- Pipeline: `Bank/Cash Event -> MoneyMovement -> Settlement -> Accounting Event / Journal -> Reconciliation`.
- **Interbank Transfer**:
  - Outflow from Source Payment Account (`1101/1102`), Inflow to Destination Payment Account (`1102/1101`).
  - Neither revenue nor expense. Must NEVER inflate `Uang Masuk` or `Uang Keluar` on the Owner View.
  - Reported separately as **Mutasi Antar Rekening**. Net cash of company remains unchanged.
- **Unclassified Cash**:
  - Movements pending reconciliation/categorization MUST NOT disappear from Cash Flow; they are surfaced as `REVIEW_REQUIRED / UNCLASSIFIED`.

---

## 4. Separation of Economic Concepts & Revenue Recognition Gate

The system enforces strict conceptual independence between:
- **Contract Value**: Total agreed contract price (SPK / Addendum).
- **Revenue Recognized**: Earned revenue under formal accounting policy.
- **Amount Invoiced**: Progress claims and customer invoices issued.
- **Cash Received**: Actual cash collections received against invoices.

*Policy Gate*: The system MUST NOT unilaterally decide the revenue recognition accounting policy (e.g. Percentage of Completion vs Billed Progress). Invoicing = Revenue is treated as an operational staging convention until an accounting consultant formally approves SAK EP revenue recognition rules. Ambiguous policy areas remain marked `BLOCKED_POLICY_DECISION`.

---

## 5. Material & Inventory Policy Gate

- Purchasing material for a project does not automatically force immediate direct HPP recognition if policy dictates inventory staging.
- `Persediaan Material & Perlengkapan Proyek` (`COA 1301/1302`) remains available for unconsumed supplies.
- Default direct cost posting remains intact; changes to auto-inventory capitalization require explicit Owner policy approval.

---

## 6. Comparative Reporting & Export Consistency

- Standard financial statements must support comparative periods: `Current Period`, `Comparative Period`, `Variance Amount`, `Variance %`.
- Single Source of Truth for Exports: PDF, XLSX, and Web views MUST consume the identical backend reporting DTO. No duplicate calculation logic in frontend or template scripts.
- Formal statements must prominently display: Organization Legal Name, Report Title, Reporting Period / As-of Date, Presentation Currency (`IDR`), Generation Timestamp, and Comparative Period.
