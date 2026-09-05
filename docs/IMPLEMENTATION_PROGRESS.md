# Implementation Progress — PRD v2.0 Remediation

## Current Phase
P1 — Cash & Multi-Bank Foundation

## Completed
- [x] **P0 — Accounting & Data Integrity First**
  - [x] P0.1 Unified posting entry point (`ProcessingPolicyService`) locking direct posting bypass.
  - [x] P0.2 API contract synchronization: aligned frontend `TransactionType`, `CostCategory`, and `ReviewFlag` enums.
  - [x] P0.3 Database referential/tenant integrity: FK on `transaction_document_links.transaction_id` and strict cross-tenant entity validation.
  - [x] P0.4 PostgreSQL migration gate: `014_doc_fk_and_retention` (ensuring `RETENTION_RELEASE` enum value on PostgreSQL and FK) and `015_coa_report_section`.
  - [x] P0.5 Fix report classification: added `report_section` metadata on `ChartOfAccount`, consultant format mapping in `pl_service.py` and `balance_sheet_service.py` (Long-Term Liabilities support).

## In Progress
- [ ] **P1 — Cash & Multi-Bank Foundation**
  - [ ] P1.1 Journal payment account dimension (`journal_lines.payment_account_id` nullable FK)
  - [ ] P1.2 MoneyMovement entity & service
  - [ ] P1.3 Settlement & SettlementAllocation
  - [ ] P1.4 Interbank transfer rewrite with source and destination payment accounts

## Pending
- [ ] P2 Bank Statement & Reconciliation
- [ ] P3 Durable Offline WhatsApp Inbox
- [ ] P4 Hermes Deferred Analysis & Exception Review
- [ ] P5 Project Cost & Owner Dashboard
- [ ] P6 Accounting Period, Opening Balance & Fixed Assets
- [ ] P7 Reliability & Operations

## Verification
- Backend tests: PASS (153 unit tests pass, new unit tests pass)
- PostgreSQL migration: PASS (Alembic head upgraded successfully to `015_coa_report_section`)
- Frontend typecheck: PASS (`tsc -b` pass)
- Frontend build: PASS (`vite build` pass)
- Frontend tests: PASS (48 tests pass)

## Decisions Made
- All transaction posting must pass through `ProcessingPolicyService.authorize_and_post`.
- Added `report_section` column to `chart_of_accounts` to decouple formal statement categorization from arbitrary account code prefixes.

## Remaining Risks
- Ensuring new `payment_account_id` on journal lines cleanly supports historical and future cash/bank entries without violating Debit=Credit invariants.

## Hard Blockers
- none
