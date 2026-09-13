# Architecture & Impact Analysis: FIN-P1-102

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Defect Anatomy & Live Trace

### Current Ingestion Trace (Defective)
1. Client issues:
   ```http
   POST /api/v1/transactions
   Content-Type: application/json

   {
     "transaction_type": "OTHER_EXPENSE",
     "transaction_date": "2026-09-12",
     "amount": "5000000.00",
     "description": "Beban tak terduga proyek"
   }
   ```
2. FastAPI validates `TransactionCreate` schema. Since `OTHER_EXPENSE` is a valid enum member of `TransactionType`, validation succeeds.
3. `TransactionService.create_transaction` calls `generate_transaction_code(organization_id, date)`. The tenant sequence counter in `tenant_sequence_counters` is incremented, and code `TRX-2026-000148` is generated.
4. `Transaction` row is created with `workflow_status = STAGED` and flushed to the database.
5. Endpoint responds with `HTTP 201 Created` and `TransactionResponse`.
6. Client later calls:
   ```http
   POST /api/v1/transactions/{id}/post
   ```
7. `authorize_and_post` invokes `AccountingEngine.post_transaction(org_id, trx_id)`.
8. `PostingRuleRegistry.generate_journal_legs(transaction)` executes:
   - Evaluates `if/elif` chain across 20 supported types.
   - Hits `else` branch:
     `raise InvariantViolationException("No posting rule defined for transaction type: OTHER_EXPENSE.")`
9. Post fails with `HTTP 422 Unprocessable Content`.
10. **State Result**: Transaction remains in `STAGED` permanently. Sequence number `TRX-2026-000148` was consumed. No journal lines exist.

### Remediated Ingestion Trace (Target Contract)
1. Client issues same `POST /api/v1/transactions` with `transaction_type = "OTHER_EXPENSE"`.
2. `TransactionService.create_transaction` invokes:
   ```python
   PostingRuleRegistry.validate_generic_ingestion(data.transaction_type)
   ```
3. `PostingRuleRegistry` checks `data.transaction_type in POSTING_RULE_SUPPORTED_TYPES`.
4. Check evaluates to `False`. It raises:
   ```python
   raise InvariantViolationException(
       "Transaction type 'OTHER_EXPENSE' is not supported by the generic posting workflow.",
       details={"transaction_type": "OTHER_EXPENSE", "reason": "NO_POSTING_RULE"}
   )
   ```
5. Exception is caught by global `AppException` handler:
   - Endpoint returns `HTTP 422 Unprocessable Content`.
   - Error code is `INVARIANT_VIOLATION`.
   - Details: `{"transaction_type": "OTHER_EXPENSE", "reason": "NO_POSTING_RULE"}`.
6. Execution halts immediately:
   - `generate_transaction_code` is NEVER called.
   - No row is added to `transactions` or flushed.
   - Tenant sequence counter is NOT incremented.

---

## 2. Component Blast Radius & Interface Analysis

| Component | File Path | Impact Level | Nature of Change |
|---|---|:---:|---|
| `PostingRuleRegistry` | `backend/src/services/posting_rules.py` | **Direct (Low)** | Expose capability sets and validation methods (`POSTING_RULE_SUPPORTED_TYPES`, `SPECIAL_WORKFLOW_TYPES`, `is_generic_ingestible`, `validate_generic_ingestion`). Zero changes to existing 20 posting rules. |
| `TransactionService` | `backend/src/services/transaction_service.py` | **Direct (Low)** | Add fail-closed validation check as first line of `create_transaction`. |
| `Document API Routes` | `backend/src/api/v1/documents.py` | **Direct (Low)** | Validate corrected candidate types with canonical `PostingRuleRegistry`; approval inherits the central `TransactionService.create_transaction` gate. |
| `ProcessingPolicyService` | `backend/src/services/processing_policy_service.py` | **Direct (Low)** | Remove `PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`; verify the subset invariant against canonical capability in the focused contract test. |
| `Test Fixture` | `backend/tests/security/test_authz001_role_enforcement.py` | **Direct (Low)** | Change mutation probe transaction type from `OTHER_EXPENSE` to `DIRECT_PURCHASE` to preserve role testing focus. |
| `AccountingEngine` | `backend/src/services/accounting_engine.py` | **None (Zero)** | No changes. Existing posting logic calls `PostingRuleRegistry.generate_journal_legs` unchanged. |
| `ReversalService` | `backend/src/services/reversal_service.py` | **None (Zero)** | No changes. Dedicated reversal construction remains intact. |
| `CustomerARService` | `backend/src/services/receivable_service.py` | **None (Zero)** | No changes. Uses supported types (`CUSTOMER_INVOICE`, `CUSTOMER_PAYMENT`, `RETENTION_RELEASE`). |
| `VendorAPService` | `backend/src/services/payable_service.py` | **None (Zero)** | No changes. Uses supported types (`VENDOR_BILL`, `PAY_VENDOR_BILL`). |
| `MoneyMovementService`| `backend/src/services/money_movement_service.py` | **None (Zero)** | No changes. Links settlements to valid existing transactions. |
| `Database Schema` | `backend/alembic/versions/` | **None (Zero)** | Zero migrations. Zero table/column/enum modifications. |
| `Frontend UI` | `frontend/src/` | **None (Zero)** | Zero UI modifications. |

---

## 3. Constitution & Invariant Adherence

- **Principle V (Deterministic Accounting Engine)**: Preserved. The accounting engine enforces rules deterministically without heuristic fallbacks or invented accounts.
- **Principle XVI (Open Policy Protection)**: Strictly respected. Unsupported types remain unpostable because their accounting policies have not been resolved. No synthetic debit/credit accounts are invented.
- **Single Source of Truth**: Preserved. `PostingRuleRegistry` is the single source of capability truth; services do not maintain parallel hardcoded lists.
- **Fail-Closed Security**: Preserved. Unsupported operations are blocked at the perimeter before persistence or state corruption.

---

## 4. CP2 Verified Implementation

### Reversal Call Graph

`POST /api/v1/transactions/{id}/reverse` invokes `ReversalService.reverse_transaction`, which allocates the shared transaction sequence and constructs the `REVERSAL` transaction directly. It does **not** invoke `TransactionService.create_transaction`. The generic ingestion gate therefore rejects public `REVERSAL` intake without introducing a bypass flag or changing the dedicated reversal path.

### Canonical Capability and Ingestion Gate

- `PostingRuleRegistry._RULE_TYPE_BY_TRANSACTION_TYPE` is the single dispatch map for all 20 executable normal transaction types.
- `POSTING_RULE_SUPPORTED_TYPES` is derived from that map's keys; no second production 20-type allowlist exists.
- `SPECIAL_WORKFLOW_TYPES` contains only `REVERSAL`.
- `TransactionService.create_transaction` calls `validate_generic_ingestion` before allocation parsing, lookups, duplicate checks, sequence allocation, model construction, or flush.
- The 16 policy-blocked types return reason `NO_POSTING_RULE`; `REVERSAL` returns `SPECIAL_WORKFLOW_ONLY`.
- Rejections use HTTP 422 and `INVARIANT_VIOLATION`, persist zero transactions, and do not consume the tenant transaction sequence.

### CP2 Verification

- FIN-P1-102 focused suite: **27 passed, 19 strict xfailed, 0 failed, 0 errors**. The remaining XFAILs are exactly 17 document-correction cases and 2 AUTO_SAFE/PETTY_CASH cases assigned to CP3.
- Generic-create transition: **17 XFAIL -> 17 PASS**.
- Sequence-preservation transition: **1 XFAIL -> 1 PASS**.
- AUTHZ-001: **103 passed** after fixture-only alignment from `OTHER_EXPENSE` to `DIRECT_PURCHASE`; role and route policy are unchanged.
- Relevant reversal, accounting-engine, transaction-validation, and sequence unit tests: **22 passed**.
- Transaction-intake integration tests: **3 passed**.
- Python compilation, repository safety, and `git diff --check`: **PASS**.
- Independent bounded read-only review: **PASS** with **0 Critical, 0 High, 0 Medium, 0 Low** findings.

### Scope Confirmation

No document production code, processing-policy code, posting-leg definitions, accounting amounts/accounts, migrations, enum values, frontend product code, or historical transaction data were changed. Historical STAGED dead-end evidence remains in CP1 Git history and the specification; CP2 tests now construct historical rows directly instead of requiring the remediated public API to reproduce the old defect.

---

## 5. CP3 Verified Implementation

### Document Correction Boundary

- `correct_document` builds and schema-validates a local candidate copy, then invokes `PostingRuleRegistry.validate_generic_ingestion` before updating `document.candidate_transaction` or creating correction/audit records.
- All 16 policy-blocked types return `HTTP 422 INVARIANT_VIOLATION` with `NO_POSTING_RULE`; `REVERSAL` returns the same public status/code with `SPECIAL_WORKFLOW_ONLY`.
- Failed corrections leave the persisted `proposed_transaction_type` unchanged. The focused test verifies this for all 17 rejected types.
- Valid normal generic corrections, including `DIRECT_PURCHASE`, remain accepted.

### Approval Call Graph and Historical Safety

`approve_document_candidate` calls `TransactionService.create_transaction`. The CP2 service entrypoint invokes the canonical capability gate before allocation, lookup, sequence allocation, model construction, or flush. CP3 therefore adds no duplicate route-level approval check. Historical `READY_FOR_APPROVAL` candidates containing unsupported types still fail atomically through this actual path, with zero durable transactions/journals and unchanged candidate state.

### AUTO_SAFE Consistency

- `AUTO_SAFE_TYPES` is now `{DIRECT_PURCHASE, BANK_CHARGE}`.
- `PETTY_CASH_EXPENSE` uses the existing `HUMAN_REVIEW` fallback and receives no new accounting treatment.
- The focused contract suite verifies `AUTO_SAFE_TYPES` is a subset of `POSTING_RULE_SUPPORTED_TYPES`, the canonical CP2 capability set.

### CP3 Verification

- FIN-P1-102 focused suite: **46 passed, 0 xfailed, 0 failed, 0 errors**.
- Relevant document intelligence suite: **46 passed**.
- CP2/reversal/accounting/transaction-validation/sequence regression slice: **86 passed**.
- AUTHZ-001: **103 passed**.
- Python compilation, `git diff --check`, and repository safety: **PASS**.
- Independent bounded read-only review: **PASS** with **0 Critical, 0 High, 0 Medium, 0 Low** findings.

### CP3 Scope Confirmation

CP3 changed only document correction capability validation, `AUTO_SAFE_TYPES`, FIN-P1-102 contract tests, and governance artifacts. It did not change posting-rule implementations, `TransactionService`, accounting logic, `TransactionType`, database migrations, frontend product code, authorization policies, or historical data.

---

## 6. CP4 Final Local Verification

### Result

- Canonical-source probe verified **37** `TransactionType` members: **20** normal dispatch-backed posting-rule types, **1** special-workflow-only `REVERSAL`, and **16** policy-blocked types. The three sets are pairwise disjoint and their union equals the enum.
- Generic creation and document correction reject the same **17** values with `422 INVARIANT_VIOLATION`; the service gate occurs before lookups, sequence allocation, model construction, flush, and persistence. Dedicated reversal still bypasses generic creation through `ReversalService` only.
- `AUTO_SAFE_TYPES == {DIRECT_PURCHASE, BANK_CHARGE}` and is a strict subset of canonical normal capability; `PETTY_CASH_EXPENSE` is `HUMAN_REVIEW`.
- FIN-P1-102 focused suite: **46 passed, 0 xfailed, 0 failed, 0 errors**. AUTHZ-001: **103 passed**. FIN-P1-105: **35 passed, 1 PostgreSQL-prerequisite skip**. FIN-001 retry classification: **7 passed**. Feature 012 sequence/bootstrap: **28 passed**. Accounting/reversal/document-posting slice: **18 passed**.
- Full backend local invocation failed only at **26** FIN-001 PostgreSQL setup fixtures because `FIN_001_TEST_DATABASE_URL` was intentionally absent. A non-PostgreSQL complete run passed **635** tests with **79** explicit prerequisite skips. No local PostgreSQL service, Docker daemon, or `psql` client was available. The mandatory PostgreSQL 16 migration/drift/concurrency/retry suite remains CI-owned and fail-closed.
- Frontend: **66 passed**; lint passed with eight existing warnings; typecheck and production build passed; production dependency audit found zero vulnerabilities. Backend `compileall`, `pip check`, locked production `pip-audit`, diff security-pattern scan, and `git diff --check` passed. Ruff and mypy are not configured/available.
- Alembic static evidence: one head `023_historical_seq_bootstrap`; complete offline migration SQL chain generated. `alembic current` and `alembic check` require the unavailable local PostgreSQL service and must complete in CI.
- Independent bounded CP4 review: **PASS — 0 Critical, 0 High, 0 Medium, 0 Low**.

### Delivery Boundary

No migrations, enum changes, posting rules, accounting policy, frontend product code, authorization role policy, or historical data changes were introduced. API schemas, routes, and response models are unchanged; behavior intentionally changes from `201 STAGED` to `422 INVARIANT_VIOLATION` for unsupported generic input. Push/PR creation and actual GitHub CI are the remaining CP4 delivery gates.
