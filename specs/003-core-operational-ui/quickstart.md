# Quickstart & Verification Guide: Web SaaS Application — Core Operational UI

**Feature**: `003-core-operational-ui`  
**Date**: 2026-08-30  

---

## 1. Prerequisites & Environment Setup

- **Node.js**: v20+ (Verified: v24.19.0)
- **Package Manager**: npm (Verified: 11.17.0)
- **Backend API**: Running at `http://127.0.0.1:8000` (PostgreSQL backed FastAPI service)

```bash
# In frontend directory
cd frontend
npm install
npm run dev
```

---

## 2. Validation Scenarios

### Scenario A: Operator Login & Operational Dashboard
1. Open browser to `http://localhost:5173/login`.
2. Login with credentials (`operator@example.com` / `password123`).
3. Verify redirect to `/dashboard`.
4. Check that 5 operational metric cards (Kas & Bank, Piutang, Utang, Proyek Aktif, Antrean Review) render with accurate formatted Rupiah values without floating-point artifacts.

---

### Scenario B: Project Creation & Variation Order Tracking
1. Navigate to `/projects/new`.
2. Enter Project Name ("Gedung Olahraga"), Customer ("PT Properti Utama"), Original Contract ("Rp 500.000.000,00"), Start Date.
3. Submit and verify project code `PRJ-YYYY-###` generated.
4. Navigate to Project Detail, add Variation Order ("Rp 50.000.000,00").
5. Verify Revised Contract Value updates to "Rp 550.000.000,00".
6. Check "Biaya & Profitabilitas" tab displays breakdown by `MAT`, `SUB`, `LAB`.

---

### Scenario C: Transaction Intake & Document Attachment
1. Navigate to `/transactions/new`.
2. Select "Pembelian Langsung" (Direct Purchase).
3. Select Project, Vendor, Nominal ("Rp 25.000.000,00"), Kategori ("MAT - Material"), Bayar dari ("Bank Mandiri").
4. Attach a PDF receipt via drag-and-drop.
5. Submit transaction. Verify success toast and `TRX-YYYY-######` generated.
6. Check transaction status is `STAGED` in `/transactions`.

---

### Scenario D: Multi-Project Split Transaction Validation
1. Navigate to `/transactions/new`.
2. Enter total nominal "Rp 50.000.000,00".
3. Toggle "Bagi Alokasi Proyek" (Split Allocation).
4. Enter Line 1: Proyek A - Rp 30.000.000,00.
5. Enter Line 2: Proyek B - Rp 15.000.000,00 (Total = 45M $\neq$ 50M).
6. Verify form displays inline error: "Total alokasi (Rp 45.000.000) belum sama dengan nominal transaksi (Rp 50.000.000)" and disables Submit.
7. Correct Line 2 to Rp 20.000.000,00 and verify Submit is enabled.

---

### Scenario E: Review Queue Multi-Flag Resolution
1. Navigate to `/review-queue`.
2. Select a transaction with `PROJECT_UNKNOWN` and `MISSING_DOCUMENT`.
3. Verify document split-view renders evidentiary files.
4. Resolve flag 1 with resolution notes. Verify flag 1 is marked resolved while the transaction remains blocked in review.
5. Resolve flag 2. Verify transaction transitions to `STAGED` and enables approval.

---

### Scenario F: Posted Transaction Immutability & Reversal Workflow
1. Navigate to `/transactions` and open a `POSTED` transaction.
2. Verify all inputs are disabled / read-only and Delete button is absent.
3. Click "Batalkan / Koreksi (Reversal)".
4. Enter mandatory reversal reason "Koreksi salah alokasi".
5. Confirm. Verify status changes to `REVERSED` and a compensating reversal transaction is linked.

---

### Scenario G: Document Duplicate Warning Dialog
1. Navigate to `/documents/upload`.
2. Upload a file that was previously uploaded.
3. Verify modal appears with message: "Dokumen ini sudah pernah diunggah sebelumnya" and a direct link to the original document record.

---

## 3. Automated Test Execution

```bash
# Run unit & component test suite
npm run test

# Run type-checking and linter
npm run typecheck
npm run lint
```
