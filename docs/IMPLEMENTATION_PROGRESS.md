# Implementation Progress — PRD v2.0 Remediation

## Current Phase
P7 — Reliability & Operations

## Completed
- [x] **P0 — Accounting & Data Integrity First**
  - [x] P0.1 Unified posting entry point (ProcessingPolicyService enforced across direct posting routes)
  - [x] P0.2 Enums and contract synchronized (TransactionType, CostCategory, ReviewFlag alignment)
  - [x] P0.3 Tenant and referential integrity (Document-Transaction CASCADE FK, multi-tenant scoping validation)
  - [x] P0.4 Consultant P&L and Balance Sheet mapping (Other Income/Expense sections, Long-term liabilities separation)
  - [x] P0.5 PostgreSQL / Alembic migration check (migrations 014, 015 verified on Postgres)
- [x] **P1 — Cash & Multi-Bank Foundation**
  - [x] P1.1 payment_account_id accounting dimension added to JournalLine and Transaction
  - [x] P1.2 Real-time ledger balance calculation per PaymentAccount
  - [x] P1.3 MoneyMovement, Settlement, and SettlementAllocation models & migration (016)
  - [x] P1.4 Multi-invoice and multi-project settlement allocation logic with over-allocation prevention
  - [x] P1.5 Interbank transfers debit/credit balance verified without duplicate cash movements
- [x] **P2 — Bank Statement & Reconciliation**
  - [x] P2.1 BankStatementImport and BankStatementLine models & migration (017)
  - [x] P2.2 SHA256 file content deduplication for statement files
  - [x] P2.3 CSV and line item parsing with debit/credit extraction
  - [x] P2.4 Automated reconciliation matching rules (MATCHED, PARTIAL_MATCH, UNMATCHED_BANK, UNMATCHED_BOOK, REVIEW_REQUIRED)
  - [x] P2.5 Unallocated cash and bank summary calculations
- [x] **P3 — Durable Offline WhatsApp Inbox**
  - [x] P3.1 InboxMessage, InboxAttachment, DocumentSession, MatchEvidence models & migration (018)
  - [x] P3.2 RemoteInboxService: offline capture ingestion with idempotent deduplication via external_message_id
  - [x] P3.3 LocalSyncWorker backlog sync: turns received messages into documents and creates pending document sessions
  - [x] P3.4 Provider-agnostic capture endpoints (/api/v1/inbox/capture, /api/v1/inbox/sync, /api/v1/inbox/messages)
  - [x] P3.5 Preserved capture-only contract: no WhatsApp financial approvals
- [x] **P4 — Hermes Deferred Analysis & Exception Review**
  - [x] P4.1 DeferredAnalysisService with DocumentSession candidate evaluation
  - [x] P4.2 MatchEvidence generation across Document, OCR Quality, Counterparty, and Project checks
  - [x] P4.3 Strict ProcessingPolicyDecision states: AUTO_SAFE, REVIEW_REQUIRED, BLOCKED, FAILED
  - [x] P4.4 Safety gate: eliminated confidence > 95% auto-approval bypass; unknown entities route to REVIEW_REQUIRED
- [x] **P5 — Project Cost & Owner Dashboard**
  - [x] P5.1 Dashboard API (cash in/out period, net cash flow, unallocated cash, project spending, exceptions)
  - [x] P5.2 Project Detail API (project cash, project accrual, cost categories, vendor spend, documents, unallocated items)
  - [x] P5.3 Deprioritize Budget vs Actual in favor of real cash & project spending visibility
- [x] **P6 — Accounting Period, Opening Balance & Fixed Assets**
  - [x] P6.1 AccountingPeriod model & migration 019 (OPEN, SOFT_CLOSED, CLOSED)
  - [x] P6.2 Block posting to closed period via ProcessingPolicyService
  - [x] P6.3 Opening Balance migration/import workflow (OpeningBalanceService) for consultant starting balances
  - [x] P6.4 FixedAsset Register model & migration 019

## In Progress
- [ ] P7 — Reliability & Operations
  - [ ] P7.1 Background Job Queue in PostgreSQL (background_jobs table)
  - [ ] P7.2 Sequence safety for document code generation
  - [ ] P7.3 Health endpoint & operational verification

## Verification
- Backend tests: PASS (162 unit + 151 integration passing)
- PostgreSQL migration: PASS (019_p6_periods_and_assets head applied on PostgreSQL)
- Frontend typecheck: PASS
- Frontend build: PASS

## Decisions Made
- Multi-evidence scoring strictly gates candidate promotion: high confidence without counterparty or project match is blocked from auto-posting.

## Remaining Risks
- Large document queue analysis should be batched via background worker (P7).

## Hard Blockers
- none
