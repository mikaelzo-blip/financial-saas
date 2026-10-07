# Cross-Journey Architecture & Regression Matrix

- **Audit Run ID:** `FINAL-BASELINE-20260920`
- **Git Commit SHA:** `26ab5affee58` (`26ab5af`)
- **Date:** 20 September 2026

---

## 1. Journey Summary Matrix

| Journey | Description | Registry Status | Freshness | Run ID | Regression Mode | Final Baseline Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **J1** | Document → OCR → Review → Post | `PASS_WITH_FRICTION` | `CURRENT` | `E2E-TEST-20260920-1139` | `SMOKE` | **PASS_WITH_FRICTION** |
| **J2** | Duplicate Document Protection | `FULLY_VERIFIED` | `CURRENT` | `E2E-TEST-20260920-1139` | `CURRENT` | **FULLY_VERIFIED** |
| **J3** | AP / Vendor Payment | `PASS_WITH_FRICTION` | `CURRENT` | `E2E-TEST-20260920-1301` | `CURRENT` | **PASS_WITH_FRICTION** |
| **J4** | AR / Customer Receipt | `PASS_WITH_FRICTION` | `CURRENT` | `E2E-TEST-20260920-1345` | `CURRENT` | **PASS_WITH_FRICTION** |
| **J5** | Bank Reconciliation | `PARTIAL` | `CURRENT` | `E2E-TEST-20260920-1350` | `CURRENT` | **PARTIAL** |
| **J6** | Error Recovery | `PASS_WITH_FRICTION` | `CURRENT` | `E2E-TEST-20260920-1406` | `CURRENT` | **PASS_WITH_FRICTION** |
| **J7** | Reporting Traceability | `PASS_WITH_FRICTION` | `CURRENT` | `E2E-TEST-20260920-1425` | `SMOKE` | **PASS_WITH_FRICTION** |
| **J8** | WhatsApp → Web Review | `PARTIAL` | `CURRENT` | `E2E-TEST-20260920-1505` | `CURRENT` | **PARTIAL** |

---

## 2. Shared Service Dependency Mapping

```text
AccountingEngine
├── J1: Document Posting (DocumentPostingService)
├── J3: Vendor Bill Creation & Payment Posting (VendorAPService)
├── J4: Customer Invoice Creation & Payment Posting (CustomerARService)
├── J5: Matches journal lines posted by AccountingEngine
├── J6: Enforces posting idempotency & transactional rollback
├── J7: Source of all ledger balances for P&L, BS, GL, and TB
├── J8: Document Posting from WhatsApp intake
└── Reversals: Executes compensating journals for all reversed transactions (J1, J3, J4, J5, J6, J8)

PostingRuleRegistry / Posting Rules
├── J1: Maps document line items to account codes
├── J3: Enforces PAY_VENDOR_BILL (Dr 2101 / Cr 1101)
├── J4: Enforces CUSTOMER_PAYMENT (Dr 1101 / Cr 1201)
└── J8: Maps WhatsApp document line items

TransactionService
├── J1: Creates candidate transactions
├── J3: Creates PAY_VENDOR_BILL transactions
├── J4: Creates CUSTOMER_PAYMENT transactions
├── J5: Creates test purchase transactions
├── J6: Validates state transitions and rejects duplicates
├── J7: Provides transaction metadata
└── J8: Creates WhatsApp candidate transactions

VendorAPService & CustomerARService (Subledgers)
├── J1: Registers VendorBill on invoice posting
├── J3: Manages VendorBill lifecycle & payment allocations
├── J4: Manages CustomerInvoice lifecycle & receipt allocations
├── J7: Provides aging balances for AP and AR Aging reports
└── J8: Registers VendorBill from WhatsApp intake

ReversalService
├── J1, J3, J4, J5, J6, J8: Single authoritative service for immutable transaction reversal
└── Enforces net-zero compensating journal generation

StorageService & Ingestion
├── J1: Web document upload & SHA-256 calculation
├── J2: Exact byte deduplication guard
└── J8: Machine upload (/hermes/documents/upload) & remote inbox capture (/inbox/capture)

Auth & Multi-Tenant Scoping (Deps & Security)
└── Enforced uniformly across all HTTP endpoints via X-Organization-ID and require_roles
```

---

## 3. Idempotency & Duplicate Guard Matrix

| Workflow Domain | Mechanism | Layer | Behavior | Financial Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Document Intake** | SHA-256 byte hash | DB (`uq_documents_org_hash`) + Service | HTTP 409 Conflict | 0 duplicate documents |
| **AP Payment** | Outstanding balance check | Service (`VendorAPService`) | HTTP 422 InvariantViolation | 0 overpayment, 0 duplicate payment |
| **AR Receipt** | Outstanding balance check | Service (`CustomerARService`) + UI badge | HTTP 422 InvariantViolation | 0 overpayment, 0 duplicate receipt |
| **Bank Import** | SHA-256 statement hash | DB (`uq_statement_imports_hash`) + Service | HTTP 409 Conflict | 0 duplicate statement imports |
| **Bank Match** | Unique constraint per target | DB (`ck_bank_recon_exactly_one_target`) | HTTP 409 Conflict | 0 duplicate reconciliations |
| **Posting Submit** | Post idempotency check | DB + `AccountingEngine` | Existing Journal returned / HTTP 500 guard | 0 duplicate journals created |
| **WhatsApp Intake** | WAMID hash key | DB + Service (`RemoteInboxService`) | Idempotent HTTP 200 return | 0 duplicate messages |
