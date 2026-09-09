# Feature Specification: Security & Accounting Invariant Hardening

**Feature Branch**: `hermes/011-security-accounting-invariant-hardening`  
**Status**: SPECIFIED & CLARIFIED  
**Authority**: Constitution v2.0.0, Financial Concept v1, AGENTS.md, Audit 2026-09-09  

---

## 1. Purpose & Scope

Hardens the security boundary, role-based access control (RBAC), and non-bypassable financial posting invariants across all API and service paths in `mikaelzo-blip/financial-saas`. Resolves all verified P0 audit findings (FIN-P0-001 through FIN-P0-006) and targeted P1 accounting alignment (FIN-P1-101: 6108 depreciation COA).

This feature ensures that:
1. No API path or background flow can post into a `CLOSED` accounting period or bypass `SOFT_CLOSED` role checks.
2. No caller can bypass role authorization on sensitive financial actions (`approve`, `post`, `reverse`, `opening-balances`, `resolve review flag`, `fixed-asset depreciation/disposal`).
3. Real authenticated actor attribution (`actor_id`, `actor_role`) is enforced on all mutation and posting paths.
4. VIEWER role is strictly read-only across all financial mutation and review endpoints.
5. Depreciation expense deterministically posts to account `6108` per authoritative Financial Concept v1.

---

## 2. Verified Audit Findings & Classification

| Finding ID | Classification | Exact Evidence & Defect Summary |
|---|---|---|
| **FIN-P0-001** | **CONFIRMED** | `backend/src/api/v1/transactions.py:80,98` calls `authorize_and_post(..., bypass_role_check=True)`. Neither route checks caller role or passes `actor_id`/`actor_role`. Sensitive transaction types (`OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`) bypass Manager/Admin authorization. |
| **FIN-P0-002** | **CONFIRMED** | `backend/src/api/v1/review.py:85-101` and `backend/src/services/review_service.py:100-150` allow any authenticated user (including VIEWER and OPERATOR) to resolve review flags, resetting `workflow_status` from `REVIEW_REQUIRED` to `STAGED`. |
| **FIN-P0-003** | **CONFIRMED** | `backend/src/api/v1/transactions.py:105-125` allows any authenticated user to post opening balances (`POST /transactions/opening-balances`). `OpeningBalanceService.post_opening_balances` calls `authorize_and_post(..., bypass_role_check=True)` with no role validation or actor attribution. |
| **FIN-P0-004** | **CONFIRMED** | `backend/src/api/v1/reversals.py:38-57` allows any authenticated user to reverse posted transactions. `ReversalService.reverse_transaction` does not enforce accounting period status (bypasses `CLOSED` and `SOFT_CLOSED`), and `actor_id` is passed as `None`. |
| **FIN-P0-005** | **CONFIRMED** | Multiple financial flows call `AccountingEngine.post_transaction()` directly: vendor payments (`payables.py:152`), customer payments (`receivables.py:197`), retention releases (`receivable_service.py:265`), document approvals (`documents.py:220`), and fixed-asset depreciation (`fixed_asset_service.py:411`). `AccountingEngine.post_transaction()` contains no accounting period validation, allowing callers to post into `CLOSED` periods. |
| **FIN-P0-006** | **CONFIRMED** | `backend/src/api/v1/fixed_assets.py:108,124` hardcodes `actor_role=UserRole.ADMIN`. Endpoints for create, update, depreciate, and dispose have no role check, permitting VIEWER and OPERATOR to mutate fixed assets and post depreciation. |
| **FIN-P1-101** | **CONFIRMED** | `backend/src/services/posting_rules.py:469` posts `FIXED_ASSET_DEPRECIATION` to debit `6105` (Beban Legal/Perizinan) instead of authoritative `6108` (Beban Penyusutan Aset Tetap). |

---

## 3. Approved Authoritative Decisions & Clarifications

1. **Transaction Approve & Post Authorization**:
   - **VIEWER**: 403 Forbidden for all post/approve actions.
   - **OPERATOR**: Permitted to stage/create transactions and approve/post routine operational transactions (`AUTO_SAFE_TYPES` like `DIRECT_PURCHASE`, `BANK_CHARGE`). Forbidden (403) for sensitive transaction types (`OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`, `JOURNAL_ADJUSTMENT`) and any transaction with unresolved review flags.
   - **MANAGER & ADMIN**: Permitted to approve/post all valid transactions.
   - `bypass_role_check=True` is removed from public API endpoints.
2. **Review Flag Resolution**:
   - Only **ADMIN** and **MANAGER** may resolve financial review flags.
   - **OPERATOR** and **VIEWER** receive 403 Forbidden.
3. **Opening Balances**:
   - Only **ADMIN** may establish opening balances.
   - Requires non-null `actor_id` and audit attribution.
   - Must validate total debit == total credit.
   - Must enforce accounting period status (blocked if period is CLOSED).
4. **Reversals**:
   - Only **ADMIN** and **MANAGER** may reverse posted transactions.
   - Must enforce accounting period: reversal cannot post into a `CLOSED` period.
   - Must record real `actor_id` on reversal transaction and audit log.
5. **Non-Bypassable Posting Boundary**:
   - `AccountingEngine.post_transaction()` enforces tenant ownership, valid status (`not POSTED`, `not REVIEW_REQUIRED`, `not REVERSED`), double-entry balance, COA presence, AND **CLOSED accounting period protection**.
   - If `transaction_date` falls in a `CLOSED` accounting period, posting is strictly blocked with `InvariantViolationException`.
   - `ReversalService` enforces the same CLOSED-period invariant.
6. **Fixed Asset RBAC & Depreciation**:
   - Fixed asset mutation (create, update): **ADMIN**, **MANAGER**, **OPERATOR** (VIEWER receives 403 Forbidden).
   - Depreciation (single, batch) and Disposal: **ADMIN** and **MANAGER** only (OPERATOR and VIEWER receive 403 Forbidden).
   - Pass real `actor_role` and `actor_id` from authenticated user; remove hardcoded `UserRole.ADMIN`.
   - Correct posting rule: `FIXED_ASSET_DEPRECIATION` posts debit to `6108` (Beban Penyusutan Aset Tetap).

---

## 4. Requirements

- **FR-001 (Actor & Role Ingestion)**: API endpoints requiring authenticated application principals MUST ingest `current_user: User = Depends(require_application_user)` and pass real `actor_id=current_user.id` and `actor_role=current_user.role`.
- **FR-002 (Transaction Approval RBAC)**: `POST /transactions/{id}/post` and `POST /transactions/{id}/approve` MUST enforce:
  - VIEWER → 403 Forbidden.
  - OPERATOR → 403 Forbidden on sensitive transaction types (`OWNER_WITHDRAWAL`, `OWNER_CONTRIBUTION`, `REVERSAL`, `JOURNAL_ADJUSTMENT`) and on any transaction with unresolved review flags.
  - MANAGER / ADMIN → Allowed.
  - No `bypass_role_check` may be invoked from API routes.
- **FR-003 (Review Flag Resolution RBAC)**: `POST /transactions/{id}/review-flags/{flag_id}/resolve` MUST require ADMIN or MANAGER role. VIEWER and OPERATOR MUST receive 403 Forbidden.
- **FR-004 (Opening Balances RBAC & Period Guard)**: `POST /transactions/opening-balances` MUST require ADMIN role, record `actor_id`, and reject posting if the transaction date falls within a CLOSED accounting period.
- **FR-005 (Reversals RBAC & Period Guard)**: `POST /transactions/{id}/reverse` MUST require ADMIN or MANAGER role, record `actor_id`, and reject reversal if the reversal date falls within a CLOSED accounting period.
- **FR-006 (Hard Closed-Period Posting Invariant)**: `AccountingEngine.post_transaction()` and `ReversalService.reverse_transaction()` MUST unconditionally reject posting with `InvariantViolationException` if the effective transaction date falls within a `CLOSED` accounting period.
- **FR-007 (Fixed-Asset RBAC)**: `fixed_assets.py` endpoints MUST enforce:
  - `POST /` (create), `PUT /{id}` (update) → ADMIN, MANAGER, OPERATOR allowed; VIEWER → 403 Forbidden.
  - `POST /{id}/depreciate`, `POST /depreciate-batch`, `POST /{id}/dispose` → ADMIN, MANAGER allowed; OPERATOR and VIEWER → 403 Forbidden.
  - Hardcoded `actor_role=UserRole.ADMIN` MUST be removed; real `current_user.role` MUST be passed to service layer.
- **FR-008 (Fixed-Asset Depreciation COA Alignment)**: `PostingRuleRegistry` MUST post `FIXED_ASSET_DEPRECIATION` to debit account `6108` ("Beban Penyusutan Aset Tetap"), not `6105`.
- **FR-009 (Audit Attribution Consistency)**: All financial actions (approve, post, reverse, opening balances, depreciation, flag resolution) MUST record the authenticated user's ID as `actor_id` in audit logs and entity metadata.
- **FR-010 (Tenant Isolation Preservation)**: All RBAC and posting operations MUST maintain strict tenant isolation (`organization_id`). Cross-tenant access MUST be rejected.
- **FR-011 (Double-Entry Balance Preservation)**: Total debit MUST equal total credit for every posted journal entry. No synthetic balancing entries may be created.
- **FR-012 (Zero Regressions)**: All 393 existing backend tests, 66 frontend tests, and Node bridge tests MUST continue to pass.

---

## 5. Success Criteria

1. Authenticated API tests verify 403 Forbidden for unauthorized roles across all protected endpoints (VIEWER, OPERATOR, MANAGER, ADMIN tested explicitly).
2. Posting into a CLOSED period fails for all transaction paths (ordinary, reversal, opening balances, depreciation, payments).
3. `FIXED_ASSET_DEPRECIATION` posts Dr 6108 / Cr 1502.
4. Real `actor_id` is recorded on approved transactions and audit entries.
5. Zero new database migrations required.
6. 100% Spec Kit requirement coverage, 0 Critical / 0 High consistency issues.
