# Architecture Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Memperbaiki 5 temuan kritis arsitektur pelaporan keuangan (AR/AP Aging point-in-time leak, Retained Earnings rollover, Cash & Bank account discovery, Unmatched Cash partial settlement, dan COA mapping conflict) agar laporan memiliki integritas tie-out yang sempurna.

**Architecture:** Perbaikan dilakukan pada layer service pelaporan (`backend/src/services/reporting/`) dengan memodifikasi query SQLAlchemy agar mematuhi batasan waktu (`as_of_date`), memisahkan laba tahun berjalan vs tahun sebelumnya, dan menggunakan filter akun yang dinamis.

**Tech Stack:** Python, FastAPI, SQLAlchemy Async, PostgreSQL.

**Spec:** Hasil Audit Arsitektur Mendalam (Chat Context).

## Global Constraints

- Tidak boleh mengubah skema database (tanpa migrasi Alembic baru).
- Tidak boleh mengubah struktur response JSON API yang sudah ada (hanya memperbaiki nilai kalkulasi).
- Semua query SQLAlchemy harus tetap asynchronous (`await session.execute`).
- Perhitungan uang wajib menggunakan `Decimal`.

## Review Focus

- **AR/AP Aging Point-in-Time**: Jika laporan ditarik mundur ke tahun lalu, alokasi pembayaran tahun ini tidak boleh mengurangi saldo *outstanding* tahun lalu.
- **Neraca (Balance Sheet) Retained Earnings**: Laba dari tahun-tahun sebelum `as_of_date` harus masuk ke Saldo Laba Ditahan (`3201`), bukan Laba Periode Berjalan.
- **Cash Flow & Dashboard Kas**: Akun `1102` (Bank Operasional) harus masuk dalam perhitungan saldo kas dan arus kas.
- **Unmatched Cash**: Mutasi kas yang baru di-settle sebagian (partial) harus tetap muncul dengan sisa nominal yang belum di-settle, dan dibedakan antara uang masuk vs keluar.

---

### Task 1: Fix COA Mapping Conflict for Fixed Assets

**Files:**
- Modify: `backend/src/services/reporting/coa_mapping.py`

**Interfaces:**
- Consumes: N/A
- Produces: `REPORT_GROUPS["FIXED_ASSETS"]["prefix_match"]` bernilai `["15"]`.

- [x] **Step 1: Write the failing test**
```python
# tests/unit/test_coa_mapping.py
from src.services.reporting.coa_mapping import REPORT_GROUPS

def test_fixed_assets_prefix_is_15():
    assert REPORT_GROUPS["FIXED_ASSETS"]["prefix_match"] == ["15"]
```

- [x] **Step 2: Run test to verify it fails**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_coa_mapping.py -v`
Expected: FAIL (karena saat ini bernilai `["12"]`)

- [x] **Step 3: Implement fix in `backend/src/services/reporting/coa_mapping.py`**
Ubah `"prefix_match": ["12"]` menjadi `"prefix_match": ["15"]` pada blok `FIXED_ASSETS`.

- [x] **Step 4: Run test to verify it passes**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_coa_mapping.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/src/services/reporting/coa_mapping.py backend/tests/unit/test_coa_mapping.py
git commit -m "fix(reporting): correct FIXED_ASSETS prefix match to 15 in coa_mapping"
```

---

### Task 2: Fix AR & AP Aging Point-in-Time Leakage

**Files:**
- Modify: `backend/src/services/reporting/ar_aging_service.py`
- Modify: `backend/src/services/reporting/ap_aging_service.py`

**Interfaces:**
- Consumes: `CustomerInvoice.allocations`, `VendorBill.allocations`
- Produces: Kalkulasi `paid_amt` yang difilter berdasarkan `allocated_at <= as_of`.

- [x] **Step 1: Write the failing test**
```python
# tests/unit/test_aging_point_in_time.py
# Buat invoice di 2024, bayar di 2025. Tarik AR Aging per 31 Des 2024.
# Pastikan outstanding == total_amount (belum lunas di 2024).
```

- [x] **Step 2: Run test to verify it fails**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_aging_point_in_time.py -v`
Expected: FAIL (karena saat ini outstanding menjadi 0)

- [x] **Step 3: Implement fix in `ar_aging_service.py` dan `ap_aging_service.py`**
Ubah iterasi kalkulasi `paid_amt` agar memfilter alokasi:
```python
# ar_aging_service.py
paid_amt = sum((Decimal(str(a.allocated_amount)) for a in inv.allocations if a.allocated_at.date() <= as_of), Decimal("0.00"))
outstanding = max(Decimal("0.00"), tot_amt - paid_amt)
```
Lakukan hal yang sama di `ap_aging_service.py` untuk `bill.allocations`.

- [x] **Step 4: Run test to verify it passes**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_aging_point_in_time.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/src/services/reporting/ar_aging_service.py backend/src/services/reporting/ap_aging_service.py
git commit -m "fix(reporting): enforce point-in-time boundary on AR and AP aging allocations"
```

---

### Task 3: Fix Multi-Year Rollover Retained Earnings di Neraca

**Files:**
- Modify: `backend/src/services/reporting/balance_sheet_service.py`

**Interfaces:**
- Consumes: `JournalLine`
- Produces: `BalanceSheetReportResponse` dengan `EQ-CY` hanya untuk tahun berjalan, dan laba tahun sebelumnya masuk ke `3201`.

- [x] **Step 1: Write the failing test**
```python
# tests/unit/test_balance_sheet_retained_earnings.py
# Buat profit 100M di 2024, 20M di 2025. Tarik neraca per 31 Des 2025.
# Pastikan EQ-CY == 20M, dan 3201 bertambah 100M.
```

- [x] **Step 2: Run test to verify it fails**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_balance_sheet_retained_earnings.py -v`
Expected: FAIL (karena saat ini EQ-CY == 120M)

- [x] **Step 3: Implement fix in `balance_sheet_service.py`**
Pisahkan query `tot_rev_cum` dan `tot_exp_cum` menjadi dua bagian:
1. `prior_years_profit`: Jurnal dengan `posting_date < date(as_of.year, 1, 1)`. Tambahkan nilai ini ke `tot_eq` dan ke baris `3201` (Saldo Laba Ditahan).
2. `current_year_earnings`: Jurnal dengan `posting_date >= date(as_of.year, 1, 1)` dan `<= as_of`. Masukkan ke `EQ-CY`.

- [x] **Step 4: Run test to verify it passes**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_balance_sheet_retained_earnings.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/src/services/reporting/balance_sheet_service.py
git commit -m "fix(reporting): rollover prior years profit to retained earnings on balance sheet"
```

---

### Task 4: Fix Cash & Bank Account Discovery (Hardcoded 1101%)

**Files:**
- Modify: `backend/src/services/reporting/cash_flow_service.py`
- Modify: `backend/src/services/reporting/dashboard_service.py`
- Modify: `backend/src/services/reporting/project_reporting_service.py`

**Interfaces:**
- Consumes: `ChartOfAccount`
- Produces: Query yang mencakup semua akun kas/bank (misal `1101`, `1102`, `1103`).

- [x] **Step 1: Write the failing test**
```python
# tests/unit/test_cash_discovery.py
# Buat transaksi kas menggunakan akun 1102.
# Pastikan Cash Flow dan Dashboard membaca saldo tersebut.
```

- [x] **Step 2: Run test to verify it fails**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_cash_discovery.py -v`
Expected: FAIL (saldo 1102 diabaikan)

- [x] **Step 3: Implement fix**
Ubah `ChartOfAccount.account_code.like("1101%")` menjadi:
```python
or_(
    ChartOfAccount.account_code.like("1101%"),
    ChartOfAccount.account_code.like("1102%"),
    ChartOfAccount.account_code.like("1103%"),
    ChartOfAccount.report_group.in_(["Kas & Bank", "CASH"])
)
```
Terapkan di `cash_flow_service.py`, `dashboard_service.py`, dan `project_reporting_service.py`.

- [x] **Step 4: Run test to verify it passes**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_cash_discovery.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git commit -am "fix(reporting): broaden cash and bank account discovery beyond 1101 prefix"
```

---

### Task 5: Fix Unmatched Cash Partial Settlement & Direction

**Files:**
- Modify: `backend/src/services/reporting/dashboard_service.py`

**Interfaces:**
- Consumes: `MoneyMovement`, `Settlement`
- Produces: Kalkulasi `unmatched_amt` yang akurat berdasarkan sisa nominal yang belum di-settle.

- [x] **Step 1: Write the failing test**
```python
# tests/unit/test_unmatched_cash.py
# Buat MoneyMovement 100M, settle 40M.
# Pastikan unmatched_amt == 60M.
```

- [x] **Step 2: Run test to verify it fails**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_unmatched_cash.py -v`
Expected: FAIL (karena saat ini dianggap 0M atau 100M)

- [x] **Step 3: Implement fix in `dashboard_service.py`**
Ubah `unmatched_stmt` menggunakan `OUTER JOIN` ke `Settlement` dan hitung `MoneyMovement.amount - coalesce(sum(Settlement.settled_amount), 0)`. Filter `HAVING` sisa > 0.

- [x] **Step 4: Run test to verify it passes**
Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/unit/test_unmatched_cash.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git commit -am "fix(reporting): correctly calculate partially settled unmatched cash movements"
```
