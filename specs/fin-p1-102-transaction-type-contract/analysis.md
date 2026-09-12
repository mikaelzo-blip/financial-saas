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
| `Document API Routes` | `backend/src/api/v1/documents.py` | **Direct (Low)** | Add capability check in `correct_document` when proposed type is modified; add defense-in-depth in `approve_document_candidate`. |
| `ProcessingPolicyService` | `backend/src/services/processing_policy_service.py` | **Direct (Low)** | Remove `PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`; assert subset invariant. |
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
