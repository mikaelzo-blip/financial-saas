# Feature Specification: Transaction Processing Capability Contract

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Feature Branch**: `hermes/fin-p1-102-transaction-type-contract`
**Status**: SPECIFICATION & CHECKPOINT PLANNING
**Priority**: P1 (Core Financial Domain & Workflow Integrity)
**Authority**: Constitution v2.0.0 (Principles V, XVI), Financial Concept v1, AGENTS.md, Deep Audit 2026-09-09
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Executive Summary & Defect Characterization

### The Issue
Currently, the `TransactionType` enum defines **37** members. Any of these 37 members can be submitted to `POST /api/v1/transactions` or assigned via document candidate review correction (`POST /api/v1/documents/{id}/corrections`).

However, the deterministic accounting engine (`PostingRuleRegistry`) only implements double-entry posting rules for **20** transaction types. One additional type (`REVERSAL`) is supported exclusively through the dedicated `ReversalService` domain workflow. The remaining **16** transaction types have no debit/credit rules implemented because their accounting and tax policies remain open decisions.

Furthermore, `ProcessingPolicyService.AUTO_SAFE_TYPES` includes `PETTY_CASH_EXPENSE`, claiming it can be safely posted without review, even though no posting rule exists for it.

### Characterization: Workflow Dead-End, Not Ledger Corruption
When an unsupported transaction type is created via generic ingestion:
1. `TransactionService.create_transaction` persists a transaction row with `workflow_status = STAGED` and consumes an authoritative tenant sequence number (`TRX-YYYY-NNNNNN`).
2. When a user attempts to approve or post the transaction, `PostingRuleRegistry.generate_journal_legs` raises `InvariantViolationException("No posting rule defined for transaction type: ...")`.
3. The transaction cannot be posted, cannot be deleted (there is no delete endpoint), and cannot be modified to another type.
4. **Ledger Integrity**: Zero unbalanced or corrupted journal lines are written to the database. The failure is fail-closed at posting time.
5. **Workflow Impact**: The transaction enters a permanent dead-end state, polluting the operational workspace and unnecessarily burning business transaction sequence numbers.

### Remediation Goal
Enforce a fail-closed capability contract at the **ingestion boundary** (`TransactionService.create_transaction` and the `correct_document` API route) so that non-executable transaction types are rejected with HTTP 422 before sequence allocation and before persistence.

---

## 2. Core Invariants

- **TYPE-R01 (Executable Ingestion Gate)**: Generic transaction creation MUST accept only transaction types that have an executable normal posting path in `PostingRuleRegistry`.
- **TYPE-R02 (Pre-Persistence Rejection)**: Any `TransactionType` lacking an executable generic processing path MUST be rejected before `Transaction` model persistence or database flush.
- **TYPE-R03 (Standard 422 Error Contract)**: Ingestion rejection MUST return HTTP 422 with error code `INVARIANT_VIOLATION` via `src.core.exceptions.InvariantViolationException`.
- **TYPE-R04 (Sequence Number Preservation)**: Rejected transaction attempts MUST NOT consume an authoritative tenant sequence number (`TRX-YYYY-NNNNNN`) or increment sequence counters.
- **TYPE-R05 (REVERSAL Generic Ingestion Prohibition)**: `TransactionType.REVERSAL` MUST NOT be accepted via generic transaction creation (`POST /api/v1/transactions`).
- **TYPE-R06 (REVERSAL Dedicated Workflow Preservation)**: Dedicated reversal operations via `ReversalService` / `POST /api/v1/transactions/{id}/reverse` MUST remain fully functional, returning `201 Created` and creating paired reversal transactions with inverted journal entries.
- **TYPE-R07 (Document Candidate Correction Gate)**: Document review correction (`POST /api/v1/documents/{id}/corrections`) MUST NOT assign a `proposed_transaction_type` that lacks an executable generic posting path.
- **TYPE-R08 (Document Approval Defense-in-Depth)**: Document approval (`approve_document_candidate`) MUST NOT persist a transaction from an unsupported candidate type.
- **TYPE-R09 (PETTY_CASH_EXPENSE Contradiction Removal)**: `PETTY_CASH_EXPENSE` MUST NOT remain in `ProcessingPolicyService.AUTO_SAFE_TYPES` while it has no executable posting rule.
- **TYPE-R10 (AUTO_SAFE Subset Invariant)**: Every type in `AUTO_SAFE_TYPES` MUST be a verified member of `GENERIC_INGESTIBLE_TYPES` with an executable posting rule.
- **TYPE-R11 (Full Regression Support for 20 Valid Types)**: All 20 `PostingRuleRegistry`-supported transaction types MUST remain fully ingestible and postable without regression.
- **TYPE-R12 (Zero Speculative Accounting Policy)**: No synthetic posting rules, speculative debit/credit accounts, or tax policies may be added for unsupported types.
- **TYPE-R13 (Historical Data Boundary)**: Existing historical `STAGED` rows with unsupported types are not altered, cleaned up, or migrated by this feature.
- **TYPE-R14 (Zero Database Migrations)**: No database schema migrations or enum definitions in PostgreSQL may be altered.

---

## 3. Detailed User Stories & Behavioral Scenarios

### Scenario 1: Generic Transaction Intake with Unsupported Type
* **Given** an authenticated user with `ADMIN`, `MANAGER`, or `OPERATOR` role:
* **When** calling `POST /api/v1/transactions` with `transaction_type = "OTHER_EXPENSE"` (or any of the 16 unsupported types):
* **Then** the request is rejected with HTTP 422 `INVARIANT_VIOLATION`.
* **And** no `Transaction` record is inserted into the database.
* **And** the tenant's transaction sequence counter is NOT incremented.

### Scenario 2: Generic Transaction Intake with REVERSAL
* **Given** an authenticated user:
* **When** calling `POST /api/v1/transactions` with `transaction_type = "REVERSAL"`:
* **Then** the request is rejected with HTTP 422 `INVARIANT_VIOLATION`.
* **And** the error details indicate `SPECIAL_WORKFLOW_ONLY`.
* **And** no record is persisted.

### Scenario 3: Dedicated Reversal Flow Unaffected
* **Given** a valid `POSTED` transaction `TRX-001`:
* **When** an authorized Manager calls `POST /api/v1/transactions/{id}/reverse`:
* **Then** `ReversalService` executes successfully, marking `TRX-001` as `REVERSED`, creating a new `REVERSAL` transaction in `POSTED` status with inverted journal lines, and returning HTTP 201 Created.

### Scenario 4: Document Review Candidate Correction
* **Given** an unapproved document candidate in `REVIEW_REQUIRED`:
* **When** a reviewer attempts to set `proposed_transaction_type` to `OTHER_EXPENSE` or `REVERSAL`:
* **Then** the correction is rejected with HTTP 422 `INVARIANT_VIOLATION`.
* **And** `document.candidate_transaction` retains its prior valid type or remains unassigned.
* **When** a reviewer sets `proposed_transaction_type` to `DIRECT_PURCHASE` (supported):
* **Then** the correction succeeds with HTTP 200.

### Scenario 5: Document Candidate Approval Defense-in-Depth
* **Given** a historical candidate transaction that hypothetically contains an unsupported `proposed_transaction_type`:
* **When** an Admin or Manager attempts to approve the candidate:
* **Then** the approval fails before creating or flushing a `Transaction` row.
* **And** the clean transaction context rolls back completely.

### Scenario 6: Routine AUTO_SAFE Evaluation
* **Given** a candidate transaction with type `PETTY_CASH_EXPENSE`:
* **When** `ProcessingPolicyService.evaluate_processing_policy` is executed:
* **Then** it returns `HUMAN_REVIEW` (never `AUTO_SAFE`).
* **Given** a candidate transaction with type `DIRECT_PURCHASE` or `BANK_CHARGE`:
* **When** zero review flags exist:
* **Then** it returns `AUTO_SAFE`.

---

## 4. Behavioral API Contract

| Contract Dimension | Change | Description |
|---|---|---|
| **API Schema Change** | **NO** | `TransactionCreate`, `TransactionResponse`, and OpenAPI models are untouched. |
| **Route Signature Change** | **NO** | Path parameters, HTTP methods, headers, and query parameters remain identical. |
| **Response Model Change** | **NO** | Successful response models and standard error envelopes remain identical. |
| **Behavioral API Contract Change** | **YES** | Previously, sending an unsupported enum member or `REVERSAL` to `POST /transactions` returned `201 Created` with `workflow_status: STAGED`. After remediation, it returns `422 Unprocessable Content` with error code `INVARIANT_VIOLATION` prior to persistence. |

---

## 5. Traceability & Invariant Mapping

| Invariant | Target Service / File | Test ID | Checkpoint |
|---|---|---|:---:|
| **TYPE-R01** | `src.services.posting_rules.PostingRuleRegistry`, `src.services.transaction_service.TransactionService` | `TC-GATE-001`, `TC-UNSUP-001..016` | CP2 |
| **TYPE-R02** | `src.services.transaction_service.TransactionService` | `TC-GATE-002` | CP2 |
| **TYPE-R03** | `src.core.exceptions.InvariantViolationException` | `TC-ERR-001` | CP2 |
| **TYPE-R04** | `src.services.transaction_service.TransactionService` | `TC-SEQ-001` | CP2 |
| **TYPE-R05** | `src.services.posting_rules.PostingRuleRegistry`, `src.services.transaction_service.TransactionService` | `TC-REV-GEN-001` | CP2 |
| **TYPE-R06** | `src.services.reversal_service.ReversalService` | `TC-REV-DED-001` | CP2 |
| **TYPE-R07** | `src.api.v1.documents.correct_document` | `TC-DOC-CORR-001` | CP3 |
| **TYPE-R08** | `src.api.v1.documents.approve_document_candidate` | `TC-DOC-APPR-001` | CP3 |
| **TYPE-R09** | `src.services.processing_policy_service.ProcessingPolicyService` | `TC-SAFE-001` | CP3 |
| **TYPE-R10** | `src.services.processing_policy_service.ProcessingPolicyService` | `TC-SAFE-002` | CP3 |
| **TYPE-R11** | `src.services.posting_rules.PostingRuleRegistry`, `src.services.accounting_engine.AccountingEngine` | `TC-GEN-001..020` | CP2, CP4 |
| **TYPE-R12** | Global Scope Boundary (no rules added) | `TC-POL-001` | CP2 |
| **TYPE-R13** | Database Integrity (historical rows intact) | `TC-HIST-001` | CP4 |
| **TYPE-R14** | Alembic migration check (0 new migrations) | `TC-MIG-001` | CP4 |

---

## 6. Explicitly Out of Scope

The following items are strictly excluded from FIN-P1-102:
1. Addition of new debit/credit posting rules for the 16 unsupported types.
2. Removal of any enum members from `TransactionType` or PostgreSQL database enums.
3. Database migrations of any kind.
4. Mutation, cleanup, or deletion of existing historical `STAGED` transaction rows.
5. Introduction of transaction edit or transaction deletion endpoints.
6. Introduction of transaction cancellation workflows.
7. Frontend UX or component redesign.
8. Unrelated security or authorization changes (AUTHZ-001 role policies remain untouched).
9. Reporting engine modifications.
