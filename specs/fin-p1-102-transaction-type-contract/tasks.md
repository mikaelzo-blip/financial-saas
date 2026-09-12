# Task Breakdown: FIN-P1-102 Transaction Processing Capability Contract

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Branch**: `hermes/fin-p1-102-transaction-type-contract`
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## Task Matrix Overview

| Task ID | CP | Target File(s) | Description | Verification Gate | Status |
|---|:---:|---|---|---|:---:|
| **T-102-01** | CP1 | `backend/tests/security/test_fin_p1_102_transaction_type_contract.py` | Write executable characterization suite: STAGED dead-end baseline evidence & dedicated reversal preservation (passing tests). | Suite runs; 9 baseline tests PASS | COMPLETED |
| **T-102-02** | CP1 | `backend/tests/security/test_fin_p1_102_transaction_type_contract.py` | Write executable RED tests (with strict XFAIL) for generic intake rejection of 16 unsupported types + REVERSAL, sequence preservation, PETTY_CASH_EXPENSE contradiction, and document correction/approval gates. | Suite runs; 37 strict XFAIL on future contracts | COMPLETED |
| **T-102-03** | CP1 | Git & Spec Kit | Commit CP1 characterization suite with conventional commit message. | Clean worktree, test output verified | COMPLETED |
| **T-102-04** | CP2 | `backend/src/services/posting_rules.py` | Implement canonical dispatch-backed capabilities on `PostingRuleRegistry` (`POSTING_RULE_SUPPORTED_TYPES`, `SPECIAL_WORKFLOW_TYPES`, `is_generic_ingestible`, `validate_generic_ingestion`). | Registry classification and accounting regressions pass | COMPLETED |
| **T-102-05** | CP2 | `backend/src/services/transaction_service.py` | Enforce generic ingestion gate at the entrypoint of `create_transaction` before sequence allocation and model creation. | 17 generic rejection cases and sequence preservation pass | COMPLETED |
| **T-102-06** | CP2 | `backend/tests/security/test_authz001_role_enforcement.py` | Test fixture alignment: change `create_transaction` payload type in `mutation_request` from `OTHER_EXPENSE` to `DIRECT_PURCHASE`. | AUTHZ-001 suite passes 100% (103/103) | COMPLETED |
| **T-102-07** | CP2 | Git & Spec Kit | Commit CP2 implementation and fixture alignment with conventional commit message. | CP2 focused suite GREEN; independent review PASS | COMPLETED |
| **T-102-08** | CP3 | `backend/src/api/v1/documents.py` | Add generic ingestion validation to `correct_document` and defense-in-depth guard to `approve_document_candidate`. | Document correction & approval tests GREEN | PENDING |
| **T-102-09** | CP3 | `backend/src/services/processing_policy_service.py` | Remove `PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`; add subset invariant validation. | Policy evaluation test GREEN | PENDING |
| **T-102-10** | CP3 | `backend/tests/unit/test_fin_p1_102_transaction_capabilities.py` | Remove remaining XFAIL markers; add 37/37 classification completeness assertion. | 100% focused suite passes GREEN | PENDING |
| **T-102-11** | CP3 | Git & Spec Kit | Commit CP3 implementation with conventional commit message. | Clean worktree, CP3 suite GREEN | PENDING |
| **T-102-12** | CP4 | Full repository | Run complete backend test suite, Alembic drift check, and frontend build/test gates. | 690+ tests PASS, 0 drift, build passes | PENDING |
| **T-102-13** | CP4 | Spec Kit & Codebase | Conduct independent review against 16 review criteria; resolve any findings. | 0 Critical, 0 High, 0 Medium findings | PENDING |
| **T-102-14** | CP4 | `PROJECT_STATUS.md` & Git | Reconcile operational status and prepare PR for CI verification. | PR ready, CI gate monitored | PENDING |

---

## Detailed Task Descriptions

### Checkpoint 1: Characterization & Executable RED Tests

#### T-102-01: Baseline Characterization Tests
- **Objective**: Create `backend/tests/security/test_fin_p1_102_transaction_type_contract.py`.
- **Tests Implemented**:
  - `test_staged_dead_end_characterization`: Proves that current code allows `OTHER_EXPENSE` creation as `STAGED`, but posting subsequently raises `InvariantViolationException` with zero journal entries.
  - `test_dedicated_reversal_workflow_unaffected`: Proves that `ReversalService.reverse_transaction` works on a valid posted transaction, creating a `POSTED` reversal with inverted journal lines.
  - `test_all_20_posting_rule_supported_types_accepted`: Uses schema-valid, type-appropriate fixtures to preserve generic-ingestion coverage for every normal posting-rule-supported type; it becomes GREEN in CP2.

#### T-102-02: Executable RED Tests (Future Contracts)
- **Objective**: Add tests asserting future fail-closed behaviors using `@pytest.mark.xfail(strict=True, raises=AssertionError)`:
  - `test_generic_intake_rejects_unsupported_types`: Parameterized test across 16 unsupported types expecting HTTP 422 `INVARIANT_VIOLATION`.
  - `test_generic_intake_rejects_reversal`: Verifies `POST /transactions` with `REVERSAL` is rejected.
  - `test_generic_intake_preserves_tenant_sequence_on_rejection`: Verifies sequence counter does not increment on rejection.
  - `test_petty_cash_expense_not_auto_safe`: Verifies `evaluate_processing_policy` returns `HUMAN_REVIEW` for `PETTY_CASH_EXPENSE`.
  - `test_document_correction_rejects_unsupported_and_reversal`: Verifies `correct_document` rejects setting `proposed_transaction_type` to unsupported or reversal types.
  - `test_document_approval_defense_in_depth`: Verifies `approve_document_candidate` fails cleanly when candidate contains an unsupported type.

#### T-102-03: CP1 Commit
- **Commit Message**: `test(fin-p1-102): add characterization and RED regression suite for transaction capabilities (CP1)`

---

### Checkpoint 2: Canonical Processing Capabilities & TransactionService Ingestion Gate

#### T-102-04: Capabilities on PostingRuleRegistry
- **Objective**: Add canonical capability APIs to `PostingRuleRegistry` in `backend/src/services/posting_rules.py`:
  - `_RULE_TYPE_BY_TRANSACTION_TYPE`: single dispatch map for the 20 executable normal types.
  - `POSTING_RULE_SUPPORTED_TYPES`: immutable view derived from the dispatch-map keys.
  - `SPECIAL_WORKFLOW_TYPES`: frozenset with `TransactionType.REVERSAL`.
  - `is_generic_ingestible(cls, transaction_type)`: returns boolean.
  - `validate_generic_ingestion(cls, transaction_type)`: raises `InvariantViolationException` with `NO_POSTING_RULE` or `SPECIAL_WORKFLOW_ONLY` if not ingestible.

#### T-102-05: Ingestion Gate in TransactionService
- **Objective**: In `backend/src/services/transaction_service.py` within `create_transaction`:
  - Invoke `PostingRuleRegistry.validate_generic_ingestion(data.transaction_type)` as the first operation.
  - Verify sequence generation and transaction creation do not execute when exception is raised.

#### T-102-06: Align AUTHZ-001 Test Fixture
- **Objective**: In `backend/tests/security/test_authz001_role_enforcement.py` line 490:
  - Change `"transaction_type": "OTHER_EXPENSE"` to `"transaction_type": "DIRECT_PURCHASE"`.
  - Verify that the authz test passes without relying on an unsupported transaction type.

#### T-102-07: CP2 Commit
- **Commit Message**: `fix(fin-p1-102): enforce generic transaction capability contract on ingestion (CP2)`

---

### Checkpoint 3: Document API Enforcement & AUTO_SAFE Contradiction Removal

#### T-102-08: Document Review & Approval Gates
- **Objective**: In `backend/src/api/v1/documents.py`:
  - In `correct_document`, validate `validated.proposed_transaction_type` via `PostingRuleRegistry.validate_generic_ingestion`.
  - In `approve_document_candidate`, validate candidate type upfront before transaction conversion.

#### T-102-09: AUTO_SAFE Contradiction Removal
- **Objective**: In `backend/src/services/processing_policy_service.py`:
  - Remove `PETTY_CASH_EXPENSE` from `AUTO_SAFE_TYPES`.
  - Enforce `AUTO_SAFE_TYPES.issubset(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)`.

#### T-102-10: Test Suite Finalization
- **Objective**: In `backend/tests/security/test_fin_p1_102_transaction_type_contract.py`:
  - Remove all XFAIL markers; assert 100% GREEN.
  - Add parameterized test covering all 37 transaction types.

#### T-102-11: CP3 Commit
- **Commit Message**: `fix(fin-p1-102): protect document pipeline and remove auto-safe contradiction (CP3)`

---

### Checkpoint 4: Regression, Safety, Review & Delivery

#### T-102-12: Full System Regression
- **Commands**:
  - `pytest backend/tests/` (all suites)
  - `alembic check` / `alembic heads` (confirm 0 new migrations and 0 drift)
  - `npm test` & `npm run build` in `frontend/`

#### T-102-13: Independent Review
- **Objective**: Conduct formal design and code review against 16 evaluation criteria.

#### T-102-14: CP4 Delivery Readiness
- **Objective**: Reconcile `PROJECT_STATUS.md`, create pull request, monitor GitHub CI.
- **Commit Message**: `chore(fin-p1-102): complete transaction processing capability contract (CP4)`
