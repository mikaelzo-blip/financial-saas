# Technical Implementation Plan: Financial Reporting & Management Dashboard

**Feature Branch**: `004-financial-reporting-dashboard`  
**Status**: PLANNED  
**Date**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [specs/004-financial-reporting-dashboard/spec.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/spec.md)
- [specs/004-financial-reporting-dashboard/research.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/research.md)
- [specs/004-financial-reporting-dashboard/data-model.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/data-model.md)
- [specs/004-financial-reporting-dashboard/contracts/reporting-api-spec.yaml](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/contracts/reporting-api-spec.yaml)
- [specs/004-financial-reporting-dashboard/quickstart.md](file:///c:/Projects/financial-saas/specs/004-financial-reporting-dashboard/quickstart.md)

---

## 1. Architecture & Technical Strategy

### Core Principles
1. **Backend Aggregation Authority**: The FastAPI backend performs all authoritative aggregations, running balance calculations, and SAK financial statement groupings. The React frontend is purely a rendering and interaction layer.
2. **Dynamic SQL over Authoritative Ledger**: Reports are computed on-demand directly over posted `journal_lines`, `journal_entries`, `customer_invoices`, and `vendor_bills` without creating redundant derived database snapshot tables.
3. **Monomorphic Decimal Arithmetic**: All financial calculations use Python `decimal.Decimal` and PostgreSQL `NUMERIC(18, 2)` to eliminate floating-point drift.
4. **Server-Side Export Engine**: Excel (`openpyxl`) and PDF exports share the exact same reporting service pipeline as JSON API endpoints.

---

## 2. Backend Module Structure

```text
backend/src/
├── api/v1/
│   └── reports.py                      # REST Endpoints for all financial reports and exports
├── schemas/
│   └── reporting.py                    # Pydantic DTOs for request queries and statement view models
└── services/
    └── reporting/
        ├── __init__.py
        ├── pl_service.py               # Laporan Laba Rugi (Profit & Loss) engine
        ├── balance_sheet_service.py    # Laporan Neraca & Accounting Equation validator
        ├── cash_flow_service.py        # Laporan Arus Kas (Direct Method)
        ├── trial_balance_service.py    # Neraca Saldo generator
        ├── gl_service.py               # Buku Besar & running balance calculator
        ├── aging_service.py            # AR/AP Aging bucket calculator
        ├── project_reporting_service.py # Project Profitability, Cost Breakdown, & Cash Position
        ├── integrity_service.py        # Financial Integrity & Reconciliation Diagnostic engine
        └── export_service.py           # Server-side XLSX and PDF export generator
```

---

## 3. Frontend Module Structure

```text
frontend/src/
├── api/
│   └── reports.ts                      # Typed client for all reporting endpoints and file downloads
├── pages/
│   └── reports/
│       ├── ProfitLossPage.tsx          # Laporan Laba Rugi view with period filter & drill-down
│       ├── BalanceSheetPage.tsx        # Laporan Neraca view with integrity indicator
│       ├── CashFlowPage.tsx            # Laporan Arus Kas view (Direct Method)
│       ├── TrialBalancePage.tsx        # Neraca Saldo view
│       ├── GeneralLedgerPage.tsx       # Buku Besar view with account selector & running balance
│       ├── ARAgingPage.tsx             # Laporan Umur Piutang (AR) view
│       ├── APAgingPage.tsx             # Laporan Umur Utang (AP) view
│       ├── ProjectProfitabilityPage.tsx # Project Profitability & 9-category cost breakdown
│       ├── ProjectCashPositionPage.tsx # Project Cash Position (Inflow vs Outflow)
│       └── BudgetVsActualPage.tsx      # Anggaran vs Realisasi per project view
└── components/
    └── reports/
        ├── ReportHeader.tsx            # Standardized report header with period picker & export buttons
        ├── IntegrityAlertBanner.tsx    # Prominent blocking integrity alert component
        └── ReportSectionTable.tsx      # Dense hierarchical statement table
```

---

## 4. Financial Integrity Diagnostic Architecture

The backend `IntegrityService` executes 5 mandatory invariant validations:
1. **Balance Sheet Invariant**:
   $$\Delta = \text{Total Assets} - (\text{Total Liabilities} + \text{Total Equity}) = 0.00$$
2. **Trial Balance Equality**:
   $$\sum \text{Debit} - \sum \text{Credit} = 0.00$$
3. **AR Sub-Ledger Reconciliation**:
   $$\text{GL Account 1102 Balance} - \sum \text{Outstanding Customer Invoices} = 0.00$$
4. **AP Sub-Ledger Reconciliation**:
   $$\text{GL Account 2101 Balance} - \sum \text{Outstanding Vendor Bills} = 0.00$$
5. **Project Cost Reconciliation**:
   $$\sum \text{GL 5101–5109 Lines with } \text{project\_id} - \text{Total Actual Project Costs} = 0.00$$

If any diagnostic fails, the API responds with `integrity_status: "INTEGRITY_ERROR"`, rendering a blocking red alert on the UI.

---

## 5. Verification & Test Plan

- **Unit Tests**:
  - `tests/unit/test_reporting_pl.py`: P&L math, gross margin, operating profit, EBT, net profit.
  - `tests/unit/test_reporting_balance_sheet.py`: Balance sheet invariant and integrity diagnostics.
  - `tests/unit/test_reporting_cash_flow.py`: Direct method cash classifications.
  - `tests/unit/test_reporting_aging.py`: Effective due-date bucketing for AR and AP.
  - `tests/unit/test_reporting_gl.py`: Running balance computation across backdated journals.
- **Integration Tests**:
  - `tests/integration/test_reporting_api.py`: FastAPI endpoint tests across periods and export streams.
  - `tests/integration/test_export_reconciliation.py`: Validating `.xlsx` binary outputs against JSON payloads.
- **Frontend Component Tests**:
  - Vitest tests for report views, drill-down interactions, and export triggers.
