# Quickstart Verification Guide: Financial Reporting & Management Dashboard

**Feature Branch**: `004-financial-reporting-dashboard`  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)

---

## 1. Prerequisites
- Backend running on `http://127.0.0.1:8000` with PostgreSQL database populated.
- Frontend running on `http://localhost:5173`.
- User authenticated with `MANAGER` role.

---

## 2. End-to-End Verification Scenarios

### Scenario A: Profit & Loss Statement Generation & Drill-Down
1. Navigate to `/reports/profit-loss` in web app.
2. Select period **Bulan Ini** (*Agustus 2026*).
3. Verify sections: **Pendapatan**, **Harga Pokok Proyek (HPP)**, **Laba Kotor**, **Beban Operasional**, and **Laba Bersih**.
4. Click on row **Biaya Material (5101)**.
5. Verify automatic navigation to `/reports/general-ledger?account_code=5101` displaying individual journal lines with running balances.

### Scenario B: Balance Sheet Accounting Equation Integrity
1. Navigate to `/reports/balance-sheet`.
2. Inspect bottom summary.
3. Confirm green indicator: `Total Aset = Total Kewajiban + Ekuitas` (balanced).
4. Verify `is_balanced: true` and `balancing_difference: 0.00`.

### Scenario C: Cash Flow Statement (Direct Method)
1. Navigate to `/reports/cash-flow`.
2. Verify cash movements categorized into *Operasi*, *Investasi*, and *Pendanaan*.
3. Confirm closing cash balance reconciles to `1101.xx` Cash & Bank accounts on Balance Sheet.

### Scenario D: AR & AP Aging Analysis
1. Navigate to `/reports/receivables` and `/reports/payables`.
2. Verify aging breakdown into buckets: *Belum Jatuh Tempo*, *1–30 Hari*, *31–60 Hari*, *61–90 Hari*, *> 90 Hari*.
3. Confirm individual invoice/bill details match sub-ledger records.

### Scenario E: Project Profitability vs Cash Position
1. Navigate to `/reports/project-profitability`.
2. Select active project.
3. Confirm $\text{Project Gross Profit} = \text{Revenue Recognized} - \text{Actual Project Costs}$.
4. Confirm **Project Cash Position** displayed on separate panel ($\text{Cash In} - \text{Cash Out}$).

### Scenario F: Excel (.xlsx) & PDF Export Validation
1. Click **Ekspor Excel (.xlsx)** on Profit & Loss report.
2. Open generated file `Laporan_Laba_Rugi_Agustus_2026.xlsx`.
3. Verify that all row totals and formula sums match on-screen figures down to Rp 0,01.

### Scenario G: Multi-Tenant Data Isolation
1. Query `/api/v1/reports/profit-loss` with Org Header `X-Organization-ID: org-A`.
2. Repeat with `X-Organization-ID: org-B`.
3. Confirm zero cross-tenant journal leakage or shared report numbers.
