# Implementation Plan: Tenant Foreign-Reference Ownership Hardening (FIN-P1-105)

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References
**Status**: CHECKPOINT PLANNING
**Authority**: Constitution v2.0.0, AGENTS.md, Checkpoint-Driven Development Skill

---

## 1. Technical Architecture & Design Principles

1. **Service-Layer Enforcement**: All foreign-reference validations reside authoritatively within backend domain services (`ProjectService`, `FixedAssetService`, `MoneyMovementService`, `BankReconciliationService`), not solely in API routes.
2. **Fail-Closed 404 Response**: If a referenced UUID does not exist within the caller's `organization_id`, raise `EntityNotFoundException(entity_name, identifier)` immediately.
3. **Strict Atomicity**: Validations run in pre-validation loops before sequence code allocations, entity instantiations, and session flushes.
4. **Zero Migrations**: Use existing single-column foreign key columns and SQLAlchemy models without database schema alterations.

---

## 2. Checkpoint Breakdown

```text
+-----------------------------------------------------------------------------------+
| CP1: RED Reproduction & Characterization Suite                                    |
| - Implement executable RED tests for all 7 vulnerable fields                      |
| - Implement positive same-tenant controls & nonexistent UUID tests               |
| - Implement Project Budget defense-in-depth characterization                      |
| - Confirm all 7 negative tests fail RED against baseline                         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP2: Core Entity Hardening                                                        |
| - Harden ProjectService.create_project & update_project (pic_user_id)             |
| - Harden FixedAssetService.create_asset (vendor_id, document_id)                  |
| - Harden ProjectService.get_project_budgets & add_or_update_project_budget        |
| - Update 2 API route callers in api/v1/projects.py                                |
| - Verify CP2 tests transition from RED to GREEN                                   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP3: Financial Linkage Hardening                                                  |
| - Harden MoneyMovementService.create_money_movement (Settlement.transaction_id)   |
| - Harden BankReconciliationService.match_manual (journal_line, MM, transaction)   |
| - Verify CP3 tests transition from RED to GREEN                                   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| CP4: Full Regression, Schema Safety & Remote Delivery Readiness                  |
| - Run complete unit, integration, PostgreSQL, and AUTHZ-001 suites               |
| - Verify 0 regressions, 0 migrations, clean worktree                             |
| - Push hermes/fin-p1-105-tenant-reference-hardening, open PR, monitor GitHub CI  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Checkpoint Details

### Checkpoint 1: RED Reproduction & Characterization Suite
* **Scope**: Write dedicated test file `backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py`.
* **Test Cases**:
  1. `test_project_create_cross_tenant_pic_user_rejected` (Asserts 404 on Tenant B `pic_user_id`)
  2. `test_project_update_cross_tenant_pic_user_rejected` (Asserts 404 on Tenant B `pic_user_id`)
  3. `test_fixed_asset_create_cross_tenant_vendor_rejected` (Asserts 404 on Tenant B `vendor_id`)
  4. `test_fixed_asset_create_cross_tenant_document_rejected` (Asserts 404 on Tenant B `document_id`)
  5. `test_money_movement_create_cross_tenant_settlement_transaction_rejected` (Asserts 404 on Tenant B `transaction_id`)
  6. `test_bank_reconciliation_match_cross_tenant_journal_line_rejected` (Asserts 404 on Tenant B `journal_line_id`)
  7. `test_bank_reconciliation_match_cross_tenant_money_movement_rejected` (Asserts 404 on Tenant B `money_movement_id`)
  8. `test_bank_reconciliation_match_cross_tenant_transaction_rejected` (Asserts 404 on Tenant B `transaction_id`)
  9. `test_project_budget_defense_in_depth_service_scoping` (Asserts 404 when project does not belong to organization)
  10. Companion positive same-tenant control tests for all 7 fields + budget methods.
  11. Companion nonexistent random UUID tests asserting identical 404 behavior.
* **Verification Gate**:
  - Run `pytest backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py`.
  - Assert all 8 negative cross-tenant tests fail RED (currently accepted by baseline).
  - Assert positive controls pass or characterizations are consistent.

---

### Checkpoint 2: Core Entity Hardening
* **Scope**:
  - `backend/src/services/project_service.py`:
    - In `create_project`: pre-validate `data.pic_user_id` before code generation.
    - In `update_project`: validate `data.pic_user_id` before assignment.
    - In `get_project_budgets` & `add_or_update_project_budget`: add `organization_id: uuid.UUID` parameter and enforce `await self.get_project(organization_id, project_id)`.
  - `backend/src/api/v1/projects.py`:
    - Pass `org_id` into `get_project_budgets` and `add_or_update_project_budget`.
  - `backend/tests/integration/test_project_service.py`:
    - Update `get_project_budgets` call site to include `org_id`.
  - `backend/src/services/fixed_asset_service.py`:
    - In `create_asset`: pre-validate `data.vendor_id` and `data.document_id` before `FixedAsset` creation and flush.
* **Verification Gate**:
  - `pytest backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py -k "project or fixed_asset"` passes GREEN.
  - Existing project and fixed asset unit/integration tests pass.

---

### Checkpoint 3: Financial Linkage Hardening
* **Scope**:
  - `backend/src/services/money_movement_service.py`:
    - In `create_money_movement`: inside the settlement validation loop (lines 265–297), validate `s.transaction_id` against `Transaction.organization_id == organization_id` before `_generate_movement_code` and model addition.
  - `backend/src/services/bank_reconciliation_service.py`:
    - In `match_manual`: validate `req.journal_line_id` via join to `JournalEntry`, validate `req.money_movement_id`, and validate `req.transaction_id` before updating `statement_line` status or creating `BankReconciliation`.
    - Fix single-argument calls to `EntityNotFoundException` to supply canonical `(entity_name, identifier)`.
* **Verification Gate**:
  - Full `pytest backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py` passes 100% GREEN.
  - Money movement and bank reconciliation regression suites pass cleanly.

---

### Checkpoint 4: Full Regression, Schema Safety & Remote Delivery Readiness
* **Scope**:
  - Run full test suite: unit, integration, security, PostgreSQL tests.
  - Verify zero AUTHZ-001 role regressions (`pytest backend/tests/security/test_authz001_role_enforcement.py`).
  - Verify Alembic migrations: `alembic current`, `alembic check` (0 new migrations, 0 drift).
  - Verify frontend build & tests: `npm run build && npm test`.
  - Push branch `hermes/fin-p1-105-tenant-reference-hardening` to remote.
  - Create Pull Request with structured body.
  - Monitor GitHub CI runs to terminal success.
* **Verification Gate**:
  - All CI status checks green.
  - 0 Critical / High security findings.
  - 100% Spec Kit requirement coverage.
