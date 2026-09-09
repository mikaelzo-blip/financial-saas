# Tasks: Security & Accounting Invariant Hardening

**Feature**: `011-security-accounting-invariant-hardening`  
**Spec**: `specs/011-security-accounting-invariant-hardening/spec.md`  
**Plan**: `specs/011-security-accounting-invariant-hardening/plan.md`  

---

## Task List

- [ ] **T001 (Reproduction & Baseline Tests)**: Create a new comprehensive test file `backend/tests/unit/test_security_accounting_hardening.py` with failing tests reproducing:
  - FIN-P0-001 (Sensitive transaction post/approve by VIEWER/OPERATOR)
  - FIN-P0-002 (Review flag resolution by VIEWER/OPERATOR)
  - FIN-P0-003 (Opening balance posting by VIEWER/OPERATOR/MANAGER)
  - FIN-P0-004 (Reversal by VIEWER/OPERATOR, and reversal in CLOSED period)
  - FIN-P0-005 (Direct caller posting into CLOSED period)
  - FIN-P0-006 (Fixed asset depreciation and mutation by VIEWER/OPERATOR)
  - FIN-P1-101 (Depreciation posting debit account 6108 vs 6105)
- [ ] **T002 (RBAC Principal Helper)**: Implement `require_roles(*allowed_roles: UserRole)` dependency in `backend/src/api/auth.py`.
- [ ] **T003 (Hard Accounting Engine Period Guard)**: Add centralized `assert_period_allows_posting(organization_id, transaction_date, actor_role)` to `backend/src/services/accounting_engine.py` and call it at the start of `post_transaction()`.
- [ ] **T004 (Reversal Service Hardening)**: Update `backend/src/services/reversal_service.py` to check accounting period (CLOSED/SOFT_CLOSED), require MANAGER/ADMIN, and pass `actor_id` to the reversal transaction and audit log.
- [ ] **T005 (Processing Policy Service Cleanup)**: In `backend/src/services/processing_policy_service.py`, require non-null `actor_role` for sensitive transactions when `bypass_role_check=False`, and ensure fail-closed behavior.
- [ ] **T006 (Transaction API RBAC Hardening)**: In `backend/src/api/v1/transactions.py`:
  - Update `post_transaction` and `approve_transaction` to depend on `require_application_user`, pass `actor_id=current_user.id`, `actor_role=current_user.role`, and remove `bypass_role_check=True`.
  - Update `establish_opening_balances` to require `require_roles(UserRole.ADMIN)` and pass `actor_id=current_user.id`, `actor_role=current_user.role`.
- [ ] **T007 (Review Queue API RBAC Hardening)**: In `backend/src/api/v1/review.py`, protect `POST /transactions/{id}/review-flags/{flag_id}/resolve` with `require_roles(UserRole.ADMIN, UserRole.MANAGER)`.
- [ ] **T008 (Reversals API RBAC Hardening)**: In `backend/src/api/v1/reversals.py`, protect `POST /transactions/{id}/reverse` with `require_roles(UserRole.ADMIN, UserRole.MANAGER)` and pass `actor_id=current_user.id`, `actor_role=current_user.role`.
- [ ] **T009 (Fixed Assets API RBAC & Depreciation Role)**: In `backend/src/api/v1/fixed_assets.py`:
  - Protect `POST /`, `PUT /{asset_id}` with `require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)`.
  - Protect `POST /{asset_id}/depreciate`, `POST /depreciate-batch`, `POST /{asset_id}/dispose` with `require_roles(UserRole.ADMIN, UserRole.MANAGER)`.
  - Remove hardcoded `actor_role=UserRole.ADMIN`; pass `actor_role=current_user.role`.
- [ ] **T010 (Depreciation Posting Rule COA Alignment)**: In `backend/src/services/posting_rules.py`, change `FIXED_ASSET_DEPRECIATION` debit account from `6105` to `6108`. Update `test_fixed_asset_service.py` assertions accordingly.
- [ ] **T011 (Comprehensive Regression & Test Verification)**: Run `pytest backend/tests -q` to verify all 393+ tests pass, including the new security and invariant tests. Run frontend vitest and node bridge tests.
- [ ] **T012 (Spec Kit Consistency Analysis & Documentation)**: Create `specs/011-security-accounting-invariant-hardening/final-analysis.md`, update `PROJECT_STATUS.md`, and verify 100% requirement coverage.
