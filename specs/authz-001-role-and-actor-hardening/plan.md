# Implementation Plan: Role Enforcement & Actor Attribution Hardening

**Feature**: AUTHZ-001 (Reconciled Baseline)
**Branch**: `hermes/authz-001-role-and-actor-hardening`
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Specification**: [spec.md](spec.md)
**Contract**: [contracts/authorization-matrix.md](contracts/authorization-matrix.md)

---

## 1. Summary

Enforce strict backend role-based access control (RBAC) across all human application mutation routes, eliminate legacy actor helper `deps.py:get_current_user_id`, purge unreachable header fallback in `require_roles`, and guarantee that actor attribution derives solely from the verified JWT principal. No database schema migrations, accounting logic modifications, or frontend changes are in scope.

---

## 2. Technical Context

- **Language / Framework**: Python 3.11+, FastAPI, Starlette, Pydantic v2
- **ORM / Database**: SQLAlchemy 2 async, SQLite for fast unit/integration testing, PostgreSQL 16 authoritative
- **Security / Token**: python-jose (JWT), passlib (bcrypt), FastAPI dependency injection
- **Test Suite**: pytest, pytest-asyncio, httpx AsyncClient
- **Scope**: Backend security layer (`src/api/auth.py`, `src/api/deps.py`, `src/api/v1/`), test fixtures (`tests/conftest.py`), and dedicated authorization regression test suite (`tests/security/test_authz001_role_enforcement.py`).

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
              ┌─────────────┴─────────────┐
              ▼                           ▼
      [Public / Webhook / M2M]   [Human Application Route]
      - /api/v1/auth/login        - mounted under application_router
      - /api/v1/whatsapp/webhook   │
      - /api/v1/hermes/*           ▼
                            [require_application_user]
                            - Decode & verify Bearer JWT
                            - If supplied, assert X-User-ID == user.id (403 on mismatch)
                            - Assert X-Organization-ID == user.organization_id (403 on mismatch)
                            - Fail-closed if token missing/invalid (401)
                                   │
                                   ▼
                         [require_roles(...)]
                         - Declarative route dependency
                         - Assert current_user.role in allowed_roles
                         - Fail-closed if unauthorized (403 Forbidden)
                         - Zero unauthenticated / header fallback
                                   │
                                   ▼
                         [Route Handler Execution]
                         - Ingests verified current_user: User
                         - Binds actor_id = current_user.id
                         - Mutates domain entity / logs audit event
```

---

## 5. Checkpoints & Implementation Gates

### Checkpoint 1 (CP1): Honest Characterization & RED Regression Suite
- **Scope**: Test harness creation, honest RED regression suite for the 17 actually vulnerable routes, PASS characterization for existing protected behavior, and documentation of latent fallback behavior. Zero production changes.
- **Verification Gate**:
  - 17 RED tests failing specifically because `VIEWER` is NOT blocked with 403.
  - PASS characterization tests passing for header mismatches (403), missing JWT (401), document review routes denying `VIEWER` (403), and accounting period routes denying `VIEWER` (403).
  - Latent fallback unit test passing.
  - Spec Kit reconciled with live source reality.

### Checkpoint 2 (CP2): Verified Principal & Defense-in-Depth Actor Attribution
- **Scope**: Purge unreachable header fallback in `auth.py:require_roles`; delete `deps.py:get_current_user_id`; refactor `documents.py` (upload, retry, corrections, reject) to ingest verified `current_user`; update `tests/conftest.py` fixture.
- **Verification Gate**:
  - `deps.py:get_current_user_id` deleted and zero references remain.
  - Document upload and review tests pass cleanly using verified principal.
  - Zero regression across existing document tests.

### Checkpoint 3 (CP3): Declarative Role Enforcement Across All Routes
- **Scope**: Apply `require_roles(...)` to the 17 vulnerable endpoints; migrate in-body checks in document review and periods to declarative `require_roles(...)`.
- **Verification Gate**:
  - All 17 CP1 RED tests turn GREEN.
  - Parameterized test across all 38 human mutation routes confirms `VIEWER` receives `403 Forbidden`.
  - Positive compatibility tests confirm `ADMIN`, `MANAGER`, and `OPERATOR` retain authorized access.

### Checkpoint 4 (CP4): Full Verification, Security Review, CI, & PR Delivery
- **Scope**: Full backend test suite (`pytest -v`), frontend checks (`npm test`, `npx oxlint`, `npm run build`), WhatsApp/Hermes machine isolation checks, independent review, PR creation, GitHub CI pass, squash merge, synchronization.
- **Verification Gate**:
  - Zero test failures, zero lint/type errors, 100% Spec Kit requirement coverage.
