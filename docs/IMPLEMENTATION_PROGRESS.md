# Implementation Progress — PRD v2.0 Remediation

## Current Phase
P3 — Durable Offline WhatsApp Inbox

## Completed
- [x] **P0 — Accounting & Data Integrity First**
  - [x] P0.1 Unified posting entry point (`ProcessingPolicyService`, single route bypass closed)
  - [x] P0.2 Shared enums sync between frontend and backend
  - [x] P0.3 PostgreSQL and Alembic migration integrity validated
  - [x] P0.4 `TransactionDocumentLink` foreign key constraint to `transactions.id`
  - [x] P0.5 Strict tenant scoping validations for counterparties, projects, payment accounts, and documents
  - [x] P0.6 Chart of Account `report_section` column added and consultant P&L / Balance Sheet classification aligned
- [x] **P1 — Cash & Multi-Bank Foundation**
  - [x] P1.1 `payment_account_id` and `destination_payment_account_id` on transactions and journal lines
  - [x] P1.2 Per-bank authoritative ledger balances derived from `journal_lines` with `payment_account_id`
  - [x] P1.3 Dedicated `MoneyMovement`, `Settlement`, and `SettlementAllocation` models & services
  - [x] P1.4 Interbank transfers update source and destination bank balances deterministically without duplicate cash movements
  - [x] P1.5 Multi-project / multi-target settlement allocation support
- [x] **P2 — Bank Statement & Reconciliation**
  - [x] P2.1 New models: `BankStatementImport`, `BankStatementLine`, `BankReconciliation`
  - [x] P2.2 Alembic migration `017_p2_bank_reconciliation` applied to PostgreSQL
  - [x] P2.3 CSV parsing pipeline with cryptographic file hash deduplication (exact duplicate imports rejected)
  - [x] P2.4 Deterministic auto-match engine (exact reference, amount, bank, date) & manual match endpoint
  - [x] P2.5 Cash Completeness Dashboard API exposing matched, unmatched bank, unmatched book, and unallocated cash totals

## In Progress
- [ ] **P3 — Durable Offline WhatsApp Inbox**

## Pending
- [ ] P4 — Hermes Deferred Analysis & Exception Review
- [ ] P5 — Project Cost & Owner Dashboard
- [ ] P6 — Accounting Period, Opening Balance & Fixed Assets
- [ ] P7 — Reliability & Operations

## Verification
- Backend tests: PASS (157 unit tests passing)
- PostgreSQL migration: PASS (`017_p2_bank_reconciliation` at head)
- Frontend typecheck: PASS
- Frontend build: PASS

## Decisions Made
- Bank statement imports enforce SHA-256 unique constraints per organization.
- Unmatched bank lines remain separate from immutable double-entry books until verified and matched.
- Cash Completeness dashboard computes book vs bank variances dynamically using authoritative journal lines and money movements.

## Remaining Risks
- Bank statement format variations across regional banks (e.g. multi-line narrations) can be augmented with tailored parsers.

## Hard Blockers
- none
