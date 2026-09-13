# Technical Research & Architecture Analysis: FIN-P1-102

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Audit Context & Problem Statement

In the Deep Architectural & Security Audit dated 2026-09-09, finding **FIN-P1-102** identified a structural contract mismatch:
- `TransactionType` defines 37 distinct enum values covering broad construction accounting concepts.
- `PostingRuleRegistry.generate_journal_legs` implements balanced double-entry journal posting rules for only **20** transaction types.
- `ReversalService` implements specialized reversal logic for **1** type (`REVERSAL`).
- The remaining **16** transaction types have no posting rules implemented because business and tax policies (such as asset capitalization thresholds, imprest petty cash handling, and revenue recognition timing) remain open policy questions governed by Constitution Principle XVI.

### Current Codebase Anatomy
1. **Generic Ingestion Boundary (`TransactionService.create_transaction`)**:
   `TransactionCreate` in `backend/src/schemas/transaction.py` allows any valid `TransactionType`. Inside `TransactionService.create_transaction`:
   - It validates allocations, counterparties, projects, payment accounts, and duplicates.
   - It then allocates a sequence code `trx_code = await self.generate_transaction_code(...)`.
   - It constructs `transaction = Transaction(...)` with `workflow_status = STAGED` and executes `session.flush()`.
   - Result: Any unsupported type is successfully persisted as `STAGED` with HTTP 201.
2. **Posting Time Failure (`AccountingEngine.post_transaction`)**:
   When `authorize_and_post` or `post_transaction` is called, `PostingRuleRegistry.generate_journal_legs(transaction)` executes:
   ```python
   else:
       raise InvariantViolationException(
           f"No posting rule defined for transaction type: {t_type.value}.",
           details={"transaction_type": t_type.value}
       )
   ```
   Posting fails with HTTP 422.
3. **Operational Dead-End**:
   Because there is no transaction deletion endpoint and transactions cannot be edited to a different `transaction_type`, the transaction remains stuck in `STAGED` forever. A sequence number was consumed unnecessarily.
4. **The `REVERSAL` Ingestion Defect**:
   `TransactionType.REVERSAL` is accepted by `POST /transactions`. A generic `STAGED` reversal is created without `reversal_of_id` and cannot be posted because `PostingRuleRegistry` has no rule for `REVERSAL`. Meanwhile, the real reversal path lives in `ReversalService.reverse_transaction`.
5. **The `PETTY_CASH_EXPENSE` Invariant Contradiction**:
   `ProcessingPolicyService.AUTO_SAFE_TYPES` contains `{DIRECT_PURCHASE, PETTY_CASH_EXPENSE, BANK_CHARGE}`. Yet `PETTY_CASH_EXPENSE` has no posting rule! If an automated worker attempts to auto-post it, posting crashes with `InvariantViolationException`.
6. **Document Candidate Correction (`backend/src/api/v1/documents.py:120`)**:
   A human reviewer can submit `proposed_transaction_type = "OTHER_EXPENSE"` or `"REVERSAL"`. The route validates counterparty roles but does NOT check if the proposed type has an executable posting rule. When later approved, `create_transaction` is called.

---

## 2. Root Cause & Architectural Alternatives

### Architectural Question
Where should the authoritative generic ingestion capability contract live?

### Evaluated Options

#### Option A: Explicit Capability API on `PostingRuleRegistry` (Recommended)
- `PostingRuleRegistry` in `src/services/posting_rules.py` is already the single source of truth for posting rules.
- It exposes:
  - `POSTING_RULE_SUPPORTED_TYPES: frozenset[TransactionType]`
  - `SPECIAL_WORKFLOW_TYPES: frozenset[TransactionType]`
  - `has_rule(transaction_type: TransactionType) -> bool`
  - `is_generic_ingestible(transaction_type: TransactionType) -> bool`
  - `validate_generic_ingestion(transaction_type: TransactionType) -> None`
- **Pros**:
  - Single location for rule implementation and rule inventory.
  - Zero redundant lists in consuming services.
  - Minimal diff footprint; no new files or speculative abstractions.
  - Directly usable by `TransactionService`, document API routes, and `ProcessingPolicyService`.
  - One public capability manifest lives beside the actual journal-rule implementation; consumers do not maintain duplicate allowlists.
- **Cons**:
  - The manifest must be updated in the same change as a new posting-rule branch. CP2 tests must exercise every manifest type with a valid fixture and assert every non-manifest type fails the registry's no-rule boundary, preventing contract drift.

#### Option B: Standalone `TransactionProcessingCapabilities` Service
- A separate file `src/services/transaction_capabilities.py` declaring capability maps.
- **Pros**: Pure separation of metadata from posting logic.
- **Cons**: Creates duplicate coupling; any update to `PostingRuleRegistry` requires a synchronized edit in a separate file. Violates Constitution Single Source of Truth principle.

**Decision**: Select **Option A**.

---

## 3. Call Graph & Enforcement Points

### Generic Transaction Ingestion (`POST /api/v1/transactions`)
```
HTTP POST /api/v1/transactions
  -> require_roles(ADMIN, MANAGER, OPERATOR)
  -> TransactionService.create_transaction(data)
       |
       +--> PostingRuleRegistry.validate_generic_ingestion(data.transaction_type)
       |      |
       |      +-- [If NOT ingestible] -> RAISE InvariantViolationException(422)
       |                                  (HALT: No sequence allocated, No DB row)
       |
       +--> validate_transaction_allocations(...)
       +--> check_duplicate_candidate(...)
       +--> generate_transaction_code(...)
       +--> db.add(Transaction) -> flush() -> 201 Created (STAGED)
```

### Document Candidate Review Correction (`POST /api/v1/documents/{id}/corrections`)
```
HTTP POST /api/v1/documents/{id}/corrections
  -> require_reviewer(...)
  -> check allowed changes
  -> candidate.update(changes)
  -> TransactionCandidate.model_validate(candidate)
  |
  +--> [If proposed_transaction_type changed]:
         PostingRuleRegistry.validate_generic_ingestion(validated.proposed_transaction_type)
         |
         +-- [If NOT ingestible] -> RAISE InvariantViolationException(422)
                                    (Candidate unchanged on disk)
  |
  +--> persist valid candidate -> 200 OK
```

### Document Candidate Approval (`POST /api/v1/documents/{id}/approve`)
```
HTTP POST /api/v1/documents/{id}/approve
  -> require_roles(ADMIN, MANAGER)
  -> Defense-in-depth:
       if not PostingRuleRegistry.is_generic_ingestible(candidate.proposed_transaction_type):
           RAISE InvariantViolationException(422)
  -> TransactionService.create_transaction(...) [Primary gate also protects]
  -> AccountingEngine.post_transaction(...)
  -> Status -> PROCESSED -> 200 OK
```

---

## 4. Test Fixture Alignment

In `backend/tests/security/test_authz001_role_enforcement.py:490`:
```python
"create_transaction": {
    "json": {
        "transaction_type": "OTHER_EXPENSE",
        "transaction_date": "2026-01-02",
        "amount": "100.00",
        "description": "Authorization boundary probe",
        "document_ids": []
    }
}
```
Because `OTHER_EXPENSE` is one of the 16 unsupported types, `create_transaction` will reject it with 422 before reaching transaction persistence.
To keep the AUTHZ-001 role authorization test focused on security permissions (testing 403 Forbidden vs authorized roles) rather than transaction type capability, the fixture must be aligned to use `DIRECT_PURCHASE` (a supported neutral type).

---

## 5. Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|:---:|:---:|---|
| Breaking existing tests that create unsupported types | High | Medium | Identify all test fixtures creating unsupported types via `create_transaction` and align to supported types (e.g. `DIRECT_PURCHASE`). |
| Ingestion gate breaking valid dedicated flows | Low | High | Ensure `ReversalService` and `CustomerARService` are not blocked. `ReversalService` constructs models directly and does not call `create_transaction`. |
| Unbalanced journals or accounting policy invention | Zero | High | Strictly out of scope: zero posting rules added, zero accounting policies invented. |
| Database migration issues | Zero | Zero | Zero migrations required. Schema and enums remain untouched. |
