# Task Breakdown: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References  
**Status**: PLANNING  
**Checkpoints**: 4 (CP1 -> CP2 -> CP3 -> CP4)  

---

## Checkpoint 1: RED Reproduction & Characterization Suite (COMPLETED)

- [x] **Task 1.1 (CP1-T1)**: Scaffold dedicated security test suite `backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py` with multi-tenant fixtures (Tenant A and Tenant B, with `ADMIN`, `MANAGER`, `OPERATOR`, `VIEWER` users).
- [x] **Task 1.2 (CP1-T2)**: Implement RED negative cross-tenant tests for Project PIC:
  - `test_project_create_cross_tenant_pic_user_rejected` (`TEST-REF-01A`)
  - `test_project_update_cross_tenant_pic_user_rejected` (`TEST-REF-01B`)
- [x] **Task 1.3 (CP1-T3)**: Implement RED negative cross-tenant tests for Fixed Asset:
  - `test_fixed_asset_create_cross_tenant_vendor_rejected` (`TEST-REF-02`)
  - `test_fixed_asset_create_cross_tenant_document_rejected` (`TEST-REF-03`)
- [x] **Task 1.4 (CP1-T4)**: Implement RED negative cross-tenant test for Settlement:
  - `test_money_movement_create_cross_tenant_settlement_transaction_rejected` (`TEST-REF-04`)
- [x] **Task 1.5 (CP1-T5)**: Implement RED negative cross-tenant tests for Bank Reconciliation:
  - `test_bank_reconciliation_match_cross_tenant_journal_line_rejected` (`TEST-REF-05`)
  - `test_bank_reconciliation_match_cross_tenant_money_movement_rejected` (`TEST-REF-06`)
  - `test_bank_reconciliation_match_cross_tenant_transaction_rejected` (`TEST-REF-07`)
- [x] **Task 1.6 (CP1-T6)**: Implement Project Budget defense-in-depth characterization tests (`TEST-DID-01`).
- [x] **Task 1.7 (CP1-T7)**: Implement companion positive same-tenant control tests and nonexistent random UUID tests across all fields.
- [x] **Task 1.8 (CP1-T8)**: Run the suite to verify exact RED failure modes against the authoritative baseline without production changes; record and commit CP1 evidence.

---

## Checkpoint 2: Core Entity Hardening

- [ ] **Task 2.1 (CP2-T1)**: Harden `ProjectService.create_project` to validate `pic_user_id` against `User.organization_id == organization_id` before code generation.
- [ ] **Task 2.2 (CP2-T2)**: Harden `ProjectService.update_project` to validate `pic_user_id` against `User.organization_id == organization_id` before mutation.
- [ ] **Task 2.3 (CP2-T3)**: Harden `FixedAssetService.create_asset` to validate `vendor_id` (`Counterparty.organization_id == organization_id`) and `document_id` (`Document.organization_id == organization_id`) before persistence.
- [ ] **Task 2.4 (CP2-T4)**: Harden `ProjectService.get_project_budgets` and `add_or_update_project_budget` to accept `organization_id` and enforce `await self.get_project(organization_id, project_id)`.
- [ ] **Task 2.5 (CP2-T5)**: Update caller sites in `backend/src/api/v1/projects.py` and `backend/tests/integration/test_project_service.py`.
- [ ] **Task 2.6 (CP2-T6)**: Verify CP2 test subset transitions from RED to GREEN; run unit and integration suites; commit CP2.

---

## Checkpoint 3: Financial Linkage Hardening

- [ ] **Task 3.1 (CP3-T1)**: Harden `MoneyMovementService.create_money_movement` to validate `s.transaction_id` against `Transaction.organization_id == organization_id` within the pre-validation loop before model instantiation or code generation.
- [ ] **Task 3.2 (CP3-T2)**: Harden `BankReconciliationService.match_manual` to validate:
  - `req.journal_line_id` via JOIN `JournalEntry` on `organization_id == organization_id`;
  - `req.money_movement_id` via `MoneyMovement.organization_id == organization_id`;
  - `req.transaction_id` via `Transaction.organization_id == organization_id`.
- [ ] **Task 3.3 (CP3-T3)**: Fix legacy single-argument `EntityNotFoundException` calls in `bank_reconciliation_service.py` to use canonical `(entity_name, identifier)` format.
- [ ] **Task 3.4 (CP3-T4)**: Verify CP3 test subset transitions from RED to GREEN; verify full `test_fin_p1_105_tenant_reference_hardening.py` passes 100%; commit CP3.

---

## Checkpoint 4: Full Regression, Schema Safety & Remote Delivery Readiness

- [ ] **Task 4.1 (CP4-T1)**: Run full backend unit and integration test regression suites (`520+ tests`).
- [ ] **Task 4.2 (CP4-T2)**: Run AUTHZ-001 role matrix regression suite (`test_authz001_role_enforcement.py`) to confirm zero permission regressions.
- [ ] **Task 4.3 (CP4-T3)**: Verify Alembic database migrations (`alembic current`, `alembic check`) to confirm zero new migrations and zero schema drift.
- [ ] **Task 4.4 (CP4-T4)**: Verify frontend build and test suites (`npm test`, `npm run build`).
- [ ] **Task 4.5 (CP4-T5)**: Push feature branch `hermes/fin-p1-105-tenant-reference-hardening`, open Pull Request with comprehensive PR body, and monitor GitHub CI checks.
- [ ] **Task 4.6 (CP4-T6)**: Verify all GitHub CI checks succeed; prepare final delivery readiness summary.
