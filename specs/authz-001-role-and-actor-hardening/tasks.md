# Tasks: Role Enforcement & Actor Attribution Hardening

**Feature**: AUTHZ-001 (Reconciled Baseline)
**Branch**: `hermes/authz-001-role-and-actor-hardening`
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Specification**: [spec.md](spec.md)  
**Plan**: [plan.md](plan.md)  

---

## Task List & Checkpoint Gates

### Checkpoint 1 (CP1): Reconciled Spec Kit, PASS Characterization & Honest RED Suite
- [x] **T1.1 (Test Structure)**: Create `backend/tests/security/test_authz001_role_enforcement.py` with test fixtures supporting all 4 roles (`ADMIN`, `MANAGER`, `OPERATOR`, `VIEWER`).
- [x] **T1.2 (VIEWER Honest RED Suite)**: Implement parameterized test asserting `403 Forbidden` for `VIEWER` across the 17 actually vulnerable human application mutation routes (assert fails currently as VIEWER is not blocked -> RED).
- [x] **T1.3 (PASS Characterization: Header Integrity & Missing Auth)**:
  - Implement test proving spoofed `X-User-ID` mismatching JWT subject returns `403 User mismatch` (PASS).
  - Implement test proving spoofed `X-Organization-ID` mismatching JWT org returns `403 Organization mismatch` (PASS).
  - Implement test proving missing/invalid Bearer token returns `401 Authenticated user required` (PASS).
- [x] **T1.4 (PASS Characterization: In-Body Protected Endpoints)**:
  - Implement test proving `POST /documents/{id}/corrections` denies `VIEWER` with `403` via `require_reviewer` (PASS).
  - Implement test proving `POST /documents/{id}/reject` denies `VIEWER` with `403` via `require_reviewer` (PASS).
  - Implement test proving `POST /periods` denies `VIEWER` with `403` via in-body role check (PASS).
  - Implement test proving `PATCH /periods/{id}/status` denies `VIEWER` with `403` via in-body role check (PASS).
- [x] **T1.5 (Latent Header Fallback Characterization)**:
  - Implement unit test documenting that `require_roles` fallback activates only when `current_user is None` (e.g. via test dependency override).
  - Implement integration test proving fallback is unreachable in real mounted application traffic without overrides.
- [x] **T1.6 (CP1 Spec Reconcile & Review)**: Verify all characterization tests pass and all 17 vulnerable route tests fail as honest RED without touching production code; commit CP1.

---

### Checkpoint 2 (CP2): Verified Principal & Defense-in-Depth Actor Hardening
- [x] **T2.1 (Deps Cleanup)**: Deleted `get_current_user_id` and sentinel UUID `00000000-0000-0000-0000-000000000001` from `backend/src/api/deps.py`; zero production callers remain.
- [x] **T2.2 (Fallback Elimination)**: Deleted the `require_roles` header/DB fallback. `current_user is None` now fails closed with `401 Unauthorized`.
- [x] **T2.3 (Document Actor Refactoring)**:
  - `POST /api/v1/documents/upload` binds `created_by=current_user.id` via `require_application_user` without changing the CP3 role matrix.
  - `POST /api/v1/documents/{id}/corrections` and `POST /api/v1/documents/{id}/reject` bind correction and audit actor IDs to `current_user.id`, while preserving `require_reviewer` and its existing ADMIN/MANAGER policy.
  - `POST /api/v1/documents/{id}/retry` had no actor field or `get_current_user_id` dependency; its role gap remains a CP3 item.
- [x] **T2.4 (Test Fixture Harmonization)**: Updated `backend/tests/conftest.py` (`authenticated_client`) to inject a matching seeded user principal rather than `lambda: None`.
- [x] **T2.5 (CP2 Verification)**: CP2 identity tests and protected-route regressions pass; the 17 CP1 vulnerable-route cases remain expected RED pending CP3.
- [x] **T2.6 (CP2 Independent Review & Commit Gate)**: Bounded read-only security review reported Critical 0, High 0, Medium 0; final CP2 gates passed and checkpoint commit is authorized.

---

### Checkpoint 3 (CP3): Declarative Role Enforcement Across All 17 Vulnerable Routes
- [ ] **T3.1 (Transactions & Review RBAC)**:
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /transactions`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /transactions/{id}/review-flags`.
- [ ] **T3.2 (Projects & Budgets RBAC)**:
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /projects`.
  - Add `require_roles(ADMIN, MANAGER)` to `PATCH /projects/{id}/status`.
  - Add `require_roles(ADMIN, MANAGER)` to `POST /projects/{id}/budgets`.
- [ ] **T3.3 (Master Data RBAC)**:
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /counterparties`.
  - Add `require_roles(ADMIN)` to `POST /coa`.
  - Add `require_roles(ADMIN)` to `POST /payment-accounts`.
- [ ] **T3.4 (Treasury & Reconciliation RBAC)**:
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /money-movements`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /bank-reconciliation/imports`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /bank-reconciliation/imports/{id}/auto-match`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /bank-reconciliation/reconcile`.
- [ ] **T3.5 (Inbox & Periods RBAC)**:
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /inbox/capture`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /inbox/sync`.
  - Add `require_roles(ADMIN, MANAGER, OPERATOR)` to `POST /inbox/sessions/{id}/analyze`.
  - Refactor `accounting_periods.py` `create_period` and `update_period_status` to use declarative `Depends(require_roles(ADMIN, MANAGER))`.
- [ ] **T3.6 (CP3 Verification & Commit)**:
  - Verify T1.2 VIEWER denial matrix turns 100% GREEN (all 17 routes return 403).
  - Verify positive compatibility tests pass green for `ADMIN`, `MANAGER`, and `OPERATOR`.
  - Commit CP3.

---

### Checkpoint 4 (CP4): Full Verification, Security Review, CI, & PR Delivery
- [ ] **T4.1 (Backend Regression)**: Run full backend test suite (`pytest -v`); verify all 555+ tests pass green.
- [ ] **T4.2 (Frontend Verification)**: Run `npm test`, `npx oxlint`, `npx tsc -b`, and `npm run build`; verify all pass.
- [ ] **T4.3 (Machine & Webhook Isolation Gate)**: Run WhatsApp webhook and Hermes machine test suites; verify zero regressions.
- [ ] **T4.4 (Traceability & Artifacts)**: Finalize Spec Kit artifacts, ensure 100% requirement coverage, update `PROJECT_STATUS.md`.
- [ ] **T4.5 (PR & CI Delivery)**: Push `hermes/authz-001-role-and-actor-hardening`, open PR, monitor GitHub CI to completion, squash-merge, and synchronize `main`.
