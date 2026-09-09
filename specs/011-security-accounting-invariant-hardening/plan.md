# Implementation Plan: Security & Accounting Invariant Hardening

**Feature**: `011-security-accounting-invariant-hardening`  
**Spec**: `specs/011-security-accounting-invariant-hardening/spec.md`  

---

## 1. Constitution Check

- **Principle IV (Double-Entry Accounting)**: PASS. All posted entries preserve debit == credit.
- **Principle V (Deterministic Accounting Engine)**: PASS. Fixes `FIXED_ASSET_DEPRECIATION` to debit authoritative COA `6108`.
- **Principle X (Immutable Posted Records)**: PASS. Reversal workflow preserved and protected by period guards.
- **Principle XI (Audit Trail)**: PASS. Real non-null `actor_id` recorded on all operations.
- **Principle XXIII (Security & Confidentiality)**: PASS. Implements strict RBAC across all sensitive financial endpoints.
- **Principle XXIV (Testability & Verification)**: PASS. Authenticated API test suite across all 4 roles.

---

## 2. Architecture & Technical Design

### A. Non-Bypassable Posting Boundary

```text
API / Domain Service
        │ (passes authenticated User: actor_id, actor_role)
        ▼
Financial Posting Policy / Service
        │ (evaluates domain review requirements & role escalation)
        ▼
AccountingEngine.post_transaction()  <-- HARD LEDGER INVARIANT BOUNDARY
        ├── 1. Tenant ownership validation
        ├── 2. Workflow status validation (must not be POSTED, REVIEW_REQUIRED, or REVERSED)
        ├── 3. CLOSED Accounting Period Guard (UNCONDITIONAL: raises InvariantViolationException)
        ├── 4. SOFT_CLOSED Accounting Period Guard (requires ADMIN or MANAGER)
        ├── 5. Deterministic rule evaluation (PostingRuleRegistry)
        ├── 6. COA account presence verification
        ├── 7. Immutable double-entry persistence (sum(Dr) == sum(Cr))
        └── 8. Updates transaction.workflow_status = POSTED, approved_by = actor_id, posted_at = now
```

In addition:
- `ReversalService.reverse_transaction()` integrates the same CLOSED and SOFT_CLOSED period guards before creating reversal transactions and inverted journal entries.

### B. Role-Based Access Control (RBAC) Seam

Create a reusable role dependency helper in `src/api/auth.py` or `src/api/deps.py`:
```python
def require_roles(*allowed_roles: UserRole):
    """FastAPI dependency enforcing that current_user has one of the allowed roles."""
    async def role_checker(current_user: User = Depends(require_application_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AuthorizationException(
                f"Role '{current_user.role.value}' is not authorized. Required: {[r.value for r in allowed_roles]}."
            )
        return current_user
    return role_checker
```

### C. Endpoint Protection Mapping

| Endpoint | Allowed Roles | Service / Policy Call |
|---|---|---|
| `POST /transactions/{id}/post` | ADMIN, MANAGER, OPERATOR* | `policy_svc.authorize_and_post(..., actor_id=user.id, actor_role=user.role, bypass_role_check=False)` (*OPERATOR blocked on sensitive types) |
| `POST /transactions/{id}/approve` | ADMIN, MANAGER, OPERATOR* | `policy_svc.authorize_and_post(..., actor_id=user.id, actor_role=user.role, bypass_role_check=False)` (*OPERATOR blocked on sensitive types) |
| `POST /transactions/opening-balances` | ADMIN only | `OpeningBalanceService.post_opening_balances(..., actor_id=user.id, actor_role=user.role)` |
| `POST /transactions/{id}/review-flags/{flag_id}/resolve` | ADMIN, MANAGER | `ReviewQueueService.resolve_review_flag(..., resolved_by=user.id, actor_role=user.role)` |
| `POST /transactions/{id}/reverse` | ADMIN, MANAGER | `ReversalService.reverse_transaction(..., actor_id=user.id, actor_role=user.role)` |
| `POST /fixed-assets` | ADMIN, MANAGER, OPERATOR | `FixedAssetService.create_asset(..., actor_id=user.id)` |
| `PUT /fixed-assets/{id}` | ADMIN, MANAGER, OPERATOR | `FixedAssetService.update_asset(...)` |
| `POST /fixed-assets/{id}/depreciate` | ADMIN, MANAGER | `FixedAssetService.depreciate_asset(..., actor_id=user.id, actor_role=user.role)` |
| `POST /fixed-assets/depreciate-batch` | ADMIN, MANAGER | `FixedAssetService.depreciate_batch(..., actor_id=user.id, actor_role=user.role)` |
| `POST /fixed-assets/{id}/dispose` | ADMIN, MANAGER | `FixedAssetService.dispose_asset(..., actor_id=user.id)` |

---

## 3. Files to Touch

1. **`backend/src/api/auth.py`**: Add `require_roles` dependency helper.
2. **`backend/src/services/accounting_engine.py`**: Add centralized `assert_period_allows_posting(organization_id, transaction_date, actor_role)` check inside `post_transaction()`.
3. **`backend/src/services/reversal_service.py`**: Add period checks (CLOSED/SOFT_CLOSED) and `actor_role` validation; pass `actor_id`.
4. **`backend/src/services/processing_policy_service.py`**: Clean up `authorize_and_post` so `actor_role` is required when `bypass_role_check=False`; raise `AuthorizationException` if sensitive and role is insufficient or None.
5. **`backend/src/services/opening_balance_service.py`**: Pass `actor_id` and `actor_role` to `authorize_and_post`.
6. **`backend/src/api/v1/transactions.py`**: Use `require_application_user`; pass real `actor_id` and `actor_role`; restrict `/opening-balances` to ADMIN.
7. **`backend/src/api/v1/review.py`**: Use `require_roles(UserRole.ADMIN, UserRole.MANAGER)` on flag resolution.
8. **`backend/src/api/v1/reversals.py`**: Use `require_roles(UserRole.ADMIN, UserRole.MANAGER)`; pass `current_user.id` and `current_user.role`.
9. **`backend/src/api/v1/fixed_assets.py`**: Add `require_roles` to endpoints; pass real `current_user.role` instead of hardcoded `UserRole.ADMIN`.
10. **`backend/src/services/posting_rules.py`**: Change `FIXED_ASSET_DEPRECIATION` debit account from `6105` to `6108`.
11. **`backend/tests/unit/test_fixed_asset_service.py`**: Update assertions expecting `6105` to expect authoritative `6108`.
12. **`backend/tests/unit/test_security_accounting_hardening.py`**: New comprehensive test suite covering all RBAC and posting invariants.

---

## 4. Migration Impact

**Zero migrations required.** All required database fields (`approved_by`, `created_by`, `posted_at`, `resolved_by`, `actor_id`, `AccountingPeriod`, COA `6108`) already exist in the schema.
