# Quickstart & Verification Guide: Core Financial Domain

**Feature**: `002-core-financial-domain-model`  
**Purpose**: Validation scenarios proving the domain model and accounting engine invariants end-to-end.

---

## 1. Prerequisites

- Python 3.12+
- PostgreSQL 16 running locally or via Docker:
  ```bash
  docker run --name fin-saas-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fin_saas -p 5432:5432 -d postgres:16-alpine
  ```

---

## 2. Validation Scenarios

### Scenario A: Master Data Setup & Single-Input Vendor Bill Posting
1. **Setup COA & Project**:
   - Seed standard accounts: `1101` (Kas dan Bank), `2101` (Utang Usaha), `5101` (Harga Pokok Proyek).
   - Create customer counterparty "PT Nusantara" and Project `PRJ-2026-001` (Original Contract: Rp 1.000.000.000).
   - Create vendor counterparty "PT Baja Perkasa".
2. **Execute Ingestion**:
   - Ingest a `VENDOR_BILL` transaction for Rp 25.000.000, linked to `PRJ-2026-001` with `cost_category = 'MAT'`.
3. **Approve & Post**:
   - Call `/transactions/{id}/approve`.
4. **Expected Outcome**:
   - `workflow_status` transitions to `POSTED`.
   - `journal_entries` record created with `total_debit = 25000000` and `total_credit = 25000000`.
   - Journal lines created:
     - `Dr 5101 Harga Pokok Proyek`: Rp 25.000.000 (`project_id = PRJ-2026-001`, `cost_category = MAT`).
     - `Cr 2101 Utang Usaha`: Rp 25.000.000.
   - `vendor_bills` record created with `amount = 25000000` and `outstanding = 25000000`.
   - Querying Project `PRJ-2026-001` summary shows `total_project_cost = 25000000` under Material (`MAT`) without any manual project cost entry.

---

### Scenario B: Partial Payment of Vendor Bill (AP Settlement & Cash Neutrality)
1. **Execute Payment**:
   - Ingest a `PAY_VENDOR_BILL` transaction for Rp 15.000.000 from `payment_account_id = Mandiri`, matched to the bill created in Scenario A.
2. **Approve & Post**:
   - Call `/transactions/{id}/approve`.
3. **Expected Outcome**:
   - Journal lines created:
     - `Dr 2101 Utang Usaha`: Rp 15.000.000.
     - `Cr 1101 Kas dan Bank`: Rp 15.000.000.
   - `payment_allocations` links payment to the vendor bill for Rp 15.000.000.
   - Querying AP shows bill outstanding reduced to Rp 10.000.000.
   - Project `PRJ-2026-001` cost remains Rp 25.000.000 (no double-counted expense on payment).

---

### Scenario C: Customer Invoicing & Payment Overpayment (Review Queue Handling)
1. **Customer Invoice**:
   - Ingest a `CUSTOMER_INVOICE` transaction for Rp 100.000.000 on `PRJ-2026-001`.
   - Post transaction -> `customer_invoices` created with `amount = 100000000` and `due_date = invoice_date + 30 days`.
   - Project `billing_status` derives as `PARTIALLY_INVOICED`.
2. **Overpayment Intake**:
   - Ingest a `CUSTOMER_PAYMENT` transaction for Rp 110.000.000 matched to the invoice above.
3. **Expected Outcome**:
   - System flags `AMOUNT_MISMATCH` review flag.
   - `workflow_status` is set to `REVIEW_REQUIRED`.
   - Invariant: System does NOT auto-post or auto-create Customer Advance without human classification.
   - Reviewer reviews the item, allocates Rp 100.000.000 to settle the invoice and classifies the remaining Rp 10.000.000 as `CUSTOMER_ADVANCE`.

---

### Scenario D: Multi-Project Split Allocation Transaction
1. **Split Bill**:
   - Ingest a `VENDOR_BILL` transaction for Rp 50.000.000 with 2 allocations:
     - Allocation 1: `PRJ-2026-001`, `cost_category = MAT`, `amount = 30000000`.
     - Allocation 2: `PRJ-2026-002`, `cost_category = MAT`, `amount = 20000000`.
2. **Approve & Post**:
   - Call `/transactions/{id}/approve`.
3. **Expected Outcome**:
   - Journal entry generated with 3 lines:
     - `Dr 5101 Harga Pokok Proyek` (PRJ-2026-001, MAT): Rp 30.000.000.
     - `Dr 5101 Harga Pokok Proyek` (PRJ-2026-002, MAT): Rp 20.000.000.
     - `Cr 2101 Utang Usaha`: Rp 50.000.000.
   - `Total Debit (50.000.000) == Total Credit (50.000.000)`.

---

### Scenario E: Transaction Reversal Workflow
1. **Reversal Initiation**:
   - Call `/transactions/{id}/reverse` on a posted transaction.
2. **Expected Outcome**:
   - Original transaction transitions to `REVERSED`.
   - New `REVERSAL` transaction created in `POSTED` status.
   - Offsetting journal entry generated flipping debits and credits.
   - Historical rows preserved immutably with full `audit_logs` record.

---

## 3. Automated Test Commands (Target Implementation Suite)

```bash
# Run unit domain & accounting engine invariant tests
pytest tests/unit/test_accounting_engine.py

# Run sub-ledger allocation & duplicate detection tests
pytest tests/integration/test_allocations_and_duplicates.py

# Run full financial statement balance invariant tests (Assets == Liabilities + Equity)
pytest tests/integration/test_financial_integrity.py
```
