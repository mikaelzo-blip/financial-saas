# Implementation Progress — PRD v2.0 Remediation

## Current Phase
P2 — Bank Statement & Reconciliation

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

## In Progress
- [ ] **P2 — Bank Statement & Reconciliation**

## Pending
- [ ] P3 — Durable Offline WhatsApp Inbox
- [ ] P4 — Hermes Deferred Analysis & Exception Review
- [ ] P5 — Project Cost & Owner Dashboard
- [ ] P6 — Accounting Period, Opening Balance & Fixed Assets
- [ ] P7 — Reliability & Operations

## Verification
- Backend tests: PASS (155 unit tests passing)
- PostgreSQL migration: PASS (`016_p1_settlements` at head)
- Frontend typecheck: PASS
- Frontend build: PASS

## Decisions Made
- `payment_account_id` is tracked on every `journal_lines` cash entry, allowing direct calculation of per-account bank balance without relying on mutable caches.
- `MoneyMovement` supports 1-to-N settlements and allocations across projects while maintaining tenant boundaries.

## Remaining Risks
- Bank statement reconciliation parsing formats (BCA, Mandiri, BRI) require robust regex matching.

## Hard Blockers
- none
