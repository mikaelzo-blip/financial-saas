# Implementation Plan: FIN-P1-102 Transaction Processing Capability Contract

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Branch**: `hermes/fin-p1-102-transaction-type-contract`
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`
**Max Checkpoints**: 4 (CP1, CP2, CP3, CP4)

---

## Checkpoint Overview

```
[Baseline: befb74a]
      |
      v
+-------------------------------------------------------------------------+
| CP1: Executable RED / Characterization Test Suite                       |
| - Generic intake rejection (16 unsupported + 1 REVERSAL) [XFAIL]        |
| - STAGED dead-end baseline evidence (fail-closed at post time) [PASS]    |
| - REVERSAL dedicated workflow preservation [PASS]                       |
| - PETTY_CASH_EXPENSE contradiction [XFAIL]                              |
| - Document correction & approval paths [XFAIL]                          |
| - Sequence counter preservation assertion [XFAIL]                       |
+-------------------------------------------------------------------------+
      |
      v
+-------------------------------------------------------------------------+
| CP2: Canonical Processing Capabilities & TransactionService Gate        |
| - PostingRuleRegistry: capability constants & validation methods        |
| - TransactionService.create_transaction: pre-persistence gate           |
| - Test fixture alignment: test_authz001_role_enforcement.py             |
| - Verification: CP2 unit tests GREEN, AUTHZ-001 regression GREEN        |
+-------------------------------------------------------------------------+
      |
      v
+-------------------------------------------------------------------------+
| CP3: Document API Enforcement & AUTO_SAFE Contradiction Removal         |
| - Document correction route gate in api/v1/documents.py (validate changes) |
| - Document approval defense-in-depth gate                               |
| - Remove PETTY_CASH_EXPENSE from ProcessingPolicyService.AUTO_SAFE_TYPES |
| - Cross-service mathematical invariant tests (37/37 matrix covered)     |
| - Verification: CP3 tests GREEN                                         |
+-------------------------------------------------------------------------+
      |
      v
+-------------------------------------------------------------------------+
| CP4: Full Regression, Schema Safety & Delivery Readiness                |
| - Complete backend test suite (690+ tests)                              |
| - Alembic migration check (0 new migrations, 0 drift)                   |
| - Frontend typecheck & build validation                                 |
| - Independent review (zero Critical / High findings)                    |
| - PR & GitHub CI synchronization                                        |
+-------------------------------------------------------------------------+
```

---

## Checkpoint 1: Executable RED / Characterization Test Suite

### Goal
Establish rigorous executable evidence characterizing current defects and future contracts before any production code changes.

### Deliverables
- Dedicated test file: `backend/tests/unit/test_fin_p1_102_transaction_capabilities.py`
- Test cases designed:
  1. `test_generic_intake_rejects_unsupported_types`: Parameterized test across all 16 unsupported types (`EMPLOYEE_ADVANCE`, `OTHER_EXPENSE`, etc.) verifying HTTP 422 `INVARIANT_VIOLATION` is raised before persistence (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  2. `test_generic_intake_rejects_reversal`: Verifies `POST /transactions` with `TransactionType.REVERSAL` is rejected (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  3. `test_generic_intake_preserves_tenant_sequence_on_rejection`: Verifies that an attempted intake of an unsupported type does not increment `TenantSequenceCounter` (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  4. `test_staged_dead_end_characterization`: Proves current baseline behavior—creating an unsupported type (e.g. `OTHER_EXPENSE`) persists a `STAGED` row, but attempting to post it raises `InvariantViolationException` with zero journal entries created (`PASS` in baseline).
  5. `test_dedicated_reversal_workflow_unaffected`: Proves that `ReversalService.reverse_transaction` succeeds for valid posted transactions (`PASS` in baseline).
  6. `test_petty_cash_expense_not_auto_safe`: Verifies `ProcessingPolicyService.evaluate_processing_policy` does not return `AUTO_SAFE` for `PETTY_CASH_EXPENSE` (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  7. `test_document_correction_rejects_unsupported_and_reversal`: Verifies `correct_document` rejects setting `proposed_transaction_type` to unsupported or reversal types (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  8. `test_document_approval_defense_in_depth`: Verifies `approve_document_candidate` fails cleanly when candidate contains an unsupported type (`@pytest.mark.xfail(strict=True, raises=AssertionError)`).
  9. `test_all_20_posting_rule_supported_types_accepted`: Verifies every normal posting-rule-supported type remains accepted by `create_transaction` with a schema-valid, type-appropriate fixture (future regression contract; CP2 GREEN).
  10. `test_capability_manifest_matches_executable_rules`: Exercises each of the 20 manifest types with a valid fixture through `generate_journal_legs` and asserts each of the other 17 enum types raises the current no-rule boundary; this prevents the manifest and executable registry branches from drifting apart.

### CP1 Verification Gate
- Test suite executes without unexpected crashes or syntax errors.
- Expected passes pass; expected future-invariant tests fail with `strict=True` XFAIL.
- Zero production code modified.

---

## Checkpoint 2: Canonical Processing Capabilities & TransactionService Ingestion Gate

### Goal
Establish `PostingRuleRegistry` as the canonical capability authority and enforce fail-closed generic ingestion in `TransactionService`.

### Deliverables
1. **`backend/src/services/posting_rules.py`**:
   - Define `POSTING_RULE_SUPPORTED_TYPES: frozenset[TransactionType]` (20 types).
   - Define `SPECIAL_WORKFLOW_TYPES: frozenset[TransactionType]` (`{TransactionType.REVERSAL}`).
   - Implement `is_generic_ingestible(cls, transaction_type: TransactionType) -> bool`.
   - Implement `has_rule(cls, transaction_type: TransactionType) -> bool`.
   - Implement `validate_generic_ingestion(cls, transaction_type: TransactionType) -> None`.
2. **`backend/src/services/transaction_service.py`**:
   - In `create_transaction`, add upfront validation call:
     `PostingRuleRegistry.validate_generic_ingestion(data.transaction_type)`
   - Placed at the very top of `create_transaction`, before sequence generation, allocation parsing, or database flush.
3. **`backend/tests/security/test_authz001_role_enforcement.py`**:
   - Update line 490: change `mutation_request["create_transaction"]` payload from `OTHER_EXPENSE` to `DIRECT_PURCHASE`.
4. **Remove XFAIL markers** for generic intake and reversal intake tests in `test_fin_p1_102_transaction_capabilities.py`.

### CP2 Verification Gate
- `test_fin_p1_102_transaction_capabilities.py` generic intake tests turn GREEN.
- `backend/tests/security/test_authz001_role_enforcement.py` passes 100% (103 passed).
- Zero changes to accounting rules or migrations.

---

## Checkpoint 3: Document API Enforcement & AUTO_SAFE Contradiction Removal

### Goal
Enforce capability validation on document candidate corrections/approvals and remove `PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`.

### Deliverables
1. **`backend/src/api/v1/documents.py`**:
   - In `correct_document`, if `data.changes` specifies `proposed_transaction_type`:
     validate with `PostingRuleRegistry.validate_generic_ingestion(validated.proposed_transaction_type)`.
   - In `approve_document_candidate`, verify candidate proposed type is generic ingestible prior to calling `create_transaction`.
2. **`backend/src/services/processing_policy_service.py`**:
   - Remove `TransactionType.PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`.
   - Result: `AUTO_SAFE_TYPES = {TransactionType.DIRECT_PURCHASE, TransactionType.BANK_CHARGE}`.
   - Add class-level assertion `assert AUTO_SAFE_TYPES.issubset(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)`.
3. **Remove remaining XFAIL markers** in `test_fin_p1_102_transaction_capabilities.py`.

### CP3 Verification Gate
- All tests in `test_fin_p1_102_transaction_capabilities.py` pass GREEN (0 xfailed, 0 failed).
- Document candidate test suite passes.
- Processing policy unit tests pass.

---

## Checkpoint 4: Full Regression, Schema Safety & Delivery Readiness

### Goal
Execute comprehensive validation across all layers, ensure zero schema drift, perform independent review, and prepare PR.

### Deliverables
1. **Full Backend Suite**: `pytest` across all unit, integration, and security tests (690+ tests).
2. **Alembic Safety Check**:
   - `alembic current` == `023_historical_seq_bootstrap`
   - `alembic check` -> zero autogenerate drift.
   - Zero new migrations created.
3. **Frontend Verification**:
   - `npm run test` -> 66 passing.
   - `npm run build` -> production build clean.
4. **Independent Review**:
   - Scoped review against 16 review criteria from prompt section 27.
   - Zero Critical, zero High findings.
5. **Durable Artifact Updates**:
   - Update `PROJECT_STATUS.md`.
   - Commit final Spec Kit artifacts.

---

## Contingency & Rollback Strategy
Each checkpoint is committed atomically. If any checkpoint introduces regressions in existing suites (e.g. unexpected test failures in downstream services), changes are localized to service-boundary gates and can be refined or reverted without database migration side-effects.
