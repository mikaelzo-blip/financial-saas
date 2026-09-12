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
- [ ] **T2.1 (Deps Cleanup)**: Delete `get_current_user_id` and sentinel UUID `00000000-0000-0000-0000-000000000001` from `backend/src/api/deps.py`.
- [ ] **T2.2 (Fallback Elimination)**: Purge lines 112–128 of `backend/src/api/auth.py:require_roles`. Ensure immediate fail-closed `401 Unauthorized` if `current_user is None`.
- [ ] **T2.3 (Document Routes Refactoring)**:
  - Refactor `POST /api/v1/documents/upload`: Ingest `current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR))`, bind `created_by=current_user.id`.
  - Refactor `POST /api/v1/documents/{id}/retry`: Ingest `current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR))`.
  - Refactor `POST /api/v1/documents/{id}/corrections`: Ingest `current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))`, bind `corrected_by=current_user.id` and audit log `actor_id=current_user.id`. Remove `require_reviewer`.
  - Refactor `POST /api/v1/documents/{id}/reject`: Ingest `current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))`, bind audit log `actor_id=current_user.id`. Remove `require_reviewer`.
- [ ] **T2.4 (Test Fixture Harmonization)**: Update `backend/tests/conftest.py` (`authenticated_client`) to inject an authentic seeded user principal instead of `lambda: None`.
- [ ] **T2.5 (CP2 Verification & Commit)**: Verify existing document upload/review tests pass; commit CP2.

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
