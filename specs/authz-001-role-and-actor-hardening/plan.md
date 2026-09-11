# Implementation Plan: Role Enforcement & Actor Attribution Hardening

**Feature**: AUTHZ-001 & AUTH-002  
**Branch**: `hermes/authz-001-role-enforcement`  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  
**Specification**: [spec.md](spec.md)  
**Contract**: [contracts/authorization-matrix.md](contracts/authorization-matrix.md)  

---

## 1. Summary

Enforce strict backend role-based access control (RBAC) across all 42 human application mutation routes, eliminate caller-controlled actor identity (`X-User-ID`), purge the unauthenticated header fallback in `require_roles`, and guarantee that actor attribution derives solely from the verified JWT principal. No database schema migrations, accounting logic modifications, or frontend changes are in scope.

---

## 2. Technical Context

- **Language / Framework**: Python 3.11+, FastAPI, Starlette, Pydantic v2
- **ORM / Database**: SQLAlchemy 2 async, SQLite for fast unit/integration testing, PostgreSQL 16 authoritative
- **Security / Token**: python-jose (JWT), passlib (bcrypt), FastAPI dependency injection
- **Test Suite**: pytest, pytest-asyncio, httpx AsyncClient
- **Scope**: Backend security layer (`src/api/auth.py`, `src/api/deps.py`, `src/api/v1/`), test fixtures (`tests/conftest.py`), and dedicated authorization regression test suite.

---

## 3. Constitution Check

| Principle / Invariant | Evaluation | Alignment & Justification |
|---|:---:|---|
| **I. Single Input** | **PASS** | Business transactions entered once; authorization checks do not duplicate records. |
| **III. Simple UX** | **PASS** | Operational users (`OPERATOR`) retain simple intake/drafting capability; strict backend rules govern sensitive actions. |
| **IV. Double-Entry Invariant** | **PASS** | Total debit = total credit is untouched; posted journals remain balanced. |
| **V. Deterministic Engine** | **PASS** | Role enforcement prevents unauthorized mutation of COA accounts, transaction types, or journals. |
| **VI. Cash Movement is Not Expense** | **PASS** | Role guards on `/money-movements` ensure proper attribution without altering accounting treatment. |
| **VII. Source Traceability** | **PASS** | Document upload and corrections bind verified `current_user.id` as creator/editor. |
| **X. Immutable Posted Records** | **PASS** | Reversals and adjustments remain immutable; only authorized managers/admins can trigger them. |
| **XI. Audit Trail** | **PASS** | Verified actor principal is recorded in `AuditLog.actor_id`; eliminates spoofed actor attribution. |
| **XVII. Review Before Automation** | **PASS** | Review queue flag resolution and candidate approval remain restricted to `ADMIN` and `MANAGER`. |
| **XVIII. API Boundary** | **PASS** | Backend API remains authoritative system of record; no client-header trust. |
| **XIX. Hermes Runtime Role** | **PASS** | Machine M2M intake routes retain their dedicated token model, separate from human browser JWTs. |
| **XXIII. Tenant Isolation & RBAC** | **PASS** | Strict tenant scoping (`organization_id`) and role restrictions (`VIEWER` cannot mutate). |

---

## 4. Architectural Design

```
                  [Incoming HTTP Request]
                            │
           Header: Authorization: Bearer <JWT>
                            │
                            ▼
             ┌──────────────────────────────┐
             │   require_application_user   │
             └──────────────────────────────┘
                            │
           1. Decode JWT (signature, expiration)
           2. Extract claims: sub (user_id), organization_id
           3. DB Query: User.id == sub, org == organization_id, is_active == True
                            │
                            ▼
                [Authoritative User Principal]
                ┌────────────────────────────┐
                │ current_user.id            │ ──► Verified Actor ID
                │ current_user.organization_id│ ──► Verified Tenant ID
                │ current_user.role          │ ──► Verified Role
                └────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
 ┌──────────────────────┐        ┌──────────────────────┐
 │ require_roles(...)   │        │ Route Handlers       │
 │ - Fail-closed:       │        │ - Read principal     │
 │   no current_user    │        │ - No get_current_user│
 │   -> 401             │        │ - No header fallback │
 │ - role not in allowed│        │ - Pass user.id to    │
 │   -> 403             │        │   services / audit   │
 └──────────────────────┘        └──────────────────────┘
```

### Key Architectural Refactorings:
1. **Delete `deps.py:get_current_user_id`**:
   - Completely remove the function and its default sentinel `00000000-0000-0000-0000-000000000001`.
   - Any endpoint needing user identity must consume `current_user: User = Depends(require_application_user)` or `require_roles(...)`.
2. **Purge Header Fallbacks in `auth.py:require_roles`**:
   - Remove lines 112–128. If `current_user is None`, raise `HTTPException(401, "Authenticated user required")` immediately.
3. **Decouple Redundant Header Checks in `auth.py:authenticated_user`**:
   - Validate the cryptographic JWT token. If client passes `X-Organization-ID` or `X-User-ID`, verify match; if omitted, trust the verified JWT claims as authoritative.
4. **Declarative Role Enforcement Across All 19 Vulnerable Routes**:
   - Add `current_user: User = Depends(require_roles(...))` to each handler per the approved role matrix.
5. **Harmonize Test Fixtures (`tests/conftest.py`)**:
   - Update `authenticated_client` to inject a verified `User` principal (defaulting to `ADMIN` or configurable) so tests validate true authentication paths without security backdoors.

---

## 5. Checkpoint Breakdown

### Checkpoint 1 (CP1): Characterization & RED Regression Matrix
- **Scope**:
  - Implement comprehensive, parameterized RED regression tests in `backend/tests/security/test_authz001_role_enforcement.py`.
  - Prove that `VIEWER` can currently mutate all 19 unprotected routes (RED test: assert `403` which fails with `200`/`201`/`202`).
  - Prove AUTH-002 spoofing vulnerability on `POST /documents/{id}/corrections` and `POST /documents/{id}/reject` with spoofed `X-User-ID`.
  - Prove header fallback in `require_roles` accepts unauthenticated `X-User-ID`.
- **Exit Gate**:
  - RED test suite committed; characterization clearly proves the defects; zero production code modified.

### Checkpoint 2 (CP2): Actor Attribution Hardening & Header Fallback Elimination
- **Scope**:
  - Delete `get_current_user_id` in `src/api/deps.py`.
  - Purge lines 112–128 header fallback in `src/api/auth.py:require_roles`.
  - Refactor `src/api/v1/documents.py`:
    - In `upload_document`: require `ADMIN, MANAGER, OPERATOR`; bind `created_by=current_user.id`.
    - In `correct_document`: require `ADMIN, MANAGER`; bind `corrected_by=current_user.id` and audit log `actor_id=current_user.id`.
    - In `reject_document_candidate`: require `ADMIN, MANAGER`; bind audit log `actor_id=current_user.id`.
    - Remove redundant `require_reviewer` helper.
  - Harmonize `tests/conftest.py` so test clients pass real authenticated user principals.
- **Exit Gate**:
  - AUTH-002 tests turn GREEN; spoofing rejected; header fallback eliminated; existing test suite passes.

### Checkpoint 3 (CP3): Declarative Role Enforcement Across All 19 Routes
- **Scope**:
  - Apply `require_roles(...)` to the remaining unprotected human mutation routes:
    - `transactions.py`: `create_transaction` -> `ADMIN, MANAGER, OPERATOR`
    - `projects.py`: `create_project` -> `ADMIN, MANAGER, OPERATOR`
    - `projects.py`: `update_project_status` -> `ADMIN, MANAGER`
    - `projects.py`: `add_or_update_project_budget` -> `ADMIN, MANAGER`
    - `counterparties.py`: `create_counterparty` -> `ADMIN, MANAGER, OPERATOR`
    - `reference_data.py`: `create_coa` -> `ADMIN`
    - `reference_data.py`: `create_payment_account` -> `ADMIN`
    - `money_movements.py`: `create_money_movement` -> `ADMIN, MANAGER, OPERATOR`
    - `bank_reconciliation.py`: `upload_bank_statement` -> `ADMIN, MANAGER, OPERATOR`
    - `bank_reconciliation.py`: `auto_match_statement` -> `ADMIN, MANAGER, OPERATOR`
    - `bank_reconciliation.py`: `manual_reconcile` -> `ADMIN, MANAGER, OPERATOR`
    - `documents.py`: `retry_document` -> `ADMIN, MANAGER, OPERATOR`
    - `review.py`: `add_review_flag` -> `ADMIN, MANAGER, OPERATOR`
    - `inbox.py`: `capture_remote_message`, `sync_backlog`, `analyze_document_session` -> `ADMIN, MANAGER, OPERATOR`
    - Convert in-body checks in `accounting_periods.py` (`create_period`, `update_period_status`) to declarative `require_roles(ADMIN, MANAGER)`.
- **Exit Gate**:
  - Parameterized VIEWER denial matrix turns GREEN (100% 403 on all 42 human mutation routes).
  - Positive compatibility matrix passes green for authorized roles.

### Checkpoint 4 (CP4): Full Verification, Security Review, CI, and PR Delivery
- **Scope**:
  - Run full backend regression suite (all 555+ tests).
  - Run frontend test suite (66/66), oxlint, and TypeScript build.
  - Verify machine endpoints (`whatsapp.py`, `hermes.py`) remain functional.
  - Finalize Spec Kit artifacts and requirements traceability.
  - Open PR, monitor GitHub Actions CI, and squash-merge upon green completion.
- **Exit Gate**:
  - 100% test pass, CI green, zero security findings.
