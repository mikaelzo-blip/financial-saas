# Technical Research & Architectural Decisions: Financial Reporting & Management Dashboard

**Feature Branch**: `004-financial-reporting-dashboard`  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)

---

## 1. Aggregation Strategy: On-Demand Dynamic SQL vs Materialized Ledger Snapshots

### Evaluation
- **Option A: Real-Time Dynamic SQL Aggregation over `JournalLine` and Sub-ledgers**
  - *Pros*: 100% guarantee of zero stale data; strict compliance with Constitution Principle XII (Derived Financial Balances); zero auxiliary database tables to synchronize.
  - *Cons*: For organizations with $> 500,000$ lines, complex multi-join queries might exceed 500ms without proper indexing.
- **Option B: Materialized Snapshot / Reporting Summary Tables**
  - *Pros*: Ultra-fast static reads ($< 20$ ms).
  - *Cons*: Invalidation complexity, risk of data desynchronization upon reversals or backdated transactions; violates the single source of truth principle unless strictly implemented as a disposable cache.
- **Option C: Optimized Real-Time SQL Aggregation with Multi-Column Composite Indexes (Recommended)**
  - *Decision*: **Option C**. Implement direct SQL aggregations (using `SUM`, `CASE WHEN`, `FILTER (WHERE ...)`, window functions) directly over `journal_lines`, `journal_entries`, `customer_invoices`, and `vendor_bills`, backed by composite indexes on `(organization_id, account_code, posted_at)` and `(organization_id, project_id)`.
  - *Rationale*: A modern PostgreSQL instance easily aggregates 100,000 indexed rows in $< 15$ ms. This avoids cache invalidation bugs and satisfies all financial invariants.

---

## 2. Server-Side Financial Export Engine: Excel (`.xlsx`) & PDF (`.pdf`)

### Evaluation
- **Option A: Client-Side Export via JavaScript libraries (e.g., `xlsx`, `jspdf`)**
  - *Pros*: No backend rendering load.
  - *Cons*: Exports only what is rendered in the browser DOM (subject to table slicing or client formatting bugs); cannot guarantee 100% audit reconciliation with backend records.
- **Option B: Backend Authoritative Export Engine (Recommended)**
  - *Decision*: **Option B**. Backend service (`backend/src/services/reporting/export_service.py`) reuses the exact same Python reporting DTOs that power the JSON API.
  - *Libraries*:
    - **Excel (`.xlsx`)**: `openpyxl` / `xlsxwriter` for streaming formatted workbooks with accounting number formats (`_($* #,##0.00_)`), bold headers, company metadata, and formula sums.
    - **PDF (`.pdf`)**: `ReportLab` or HTML-to-PDF template rendering for formal corporate financial statements with organization branding and approval signature blocks.
  - *Rationale*: Ensures exported files are mathematically identical down to Rp 0,01 to on-screen figures.

---

## 3. Financial Precision & Monomorphic Decimal Typing

### Decision
- All monetary arithmetic, cumulative running balances, and aggregations inside Python services MUST use `decimal.Decimal` with fixed-point rounding (`ROUND_HALF_UP`).
- PostgreSQL columns remain `NUMERIC(18, 2)`.
- Pydantic models serialize currency values as standard numeric strings or exact Decimal objects to avoid floating-point inaccuracies in JSON serialization.

---

## 4. Cash Flow Classification Architecture (Direct Method)

### Decision
- MVP uses the **Direct Method** by analyzing journal lines linked to cash/bank accounts (`1101.xx`):
  - Inflows from `CUSTOMER_PAYMENT` $\to$ *Penerimaan dari Pelanggan (Operasi)*.
  - Outflows for `DIRECT_PURCHASE` / `PAY_VENDOR_BILL` $\to$ *Pembayaran ke Pemasok/Subkon (Operasi)*.
  - Outflows for `VENDOR_ADVANCE` $\to$ *Pengeluaran Kasbon Proyek (Operasi)*.
  - Inflows from `OWNER_CONTRIBUTION` $\to$ *Setoran Modal (Pendanaan)*.
  - Outflows for `OWNER_WITHDRAWAL` $\to$ *Penarikan Prive (Pendanaan)*.
  - Outflows for Capitalized Assets $\to$ *Pembelian Aset Tetap (Investasi)*.
- Any uncategorized cash movement is grouped under *"Transaksi Kas Perlu Klasifikasi"* rather than silently guessed.

---

## 5. Performance Indexing Strategy for PostgreSQL

```sql
-- High-performance composite indexes for reporting aggregations
CREATE INDEX IF NOT EXISTS idx_journal_lines_org_posted_account 
  ON journal_lines(organization_id, account_code);

CREATE INDEX IF NOT EXISTS idx_journal_lines_org_project_cost 
  ON journal_lines(organization_id, project_id, cost_category) 
  WHERE project_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_journal_entries_org_posted_date 
  ON journal_entries(organization_id, entry_date, status);

CREATE INDEX IF NOT EXISTS idx_customer_invoices_org_status_due 
  ON customer_invoices(organization_id, collection_status, due_date);

CREATE INDEX IF NOT EXISTS idx_vendor_bills_org_status_due 
  ON vendor_bills(organization_id, status, due_date);
```
