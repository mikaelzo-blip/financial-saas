# Independent Design & Security Analysis: Role Enforcement & Actor Hardening

**Remediation**: AUTHZ-001 (Reconciled Baseline)
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Date**: 2026-09-12
**Status**: RECONCILED & APPROVED (0 Critical, 0 High, 0 Medium, 0 Low in design)

---

## 1. Reconciled Baseline & Audit Findings Evaluation

### Old AUTH-002 Spoof Claim: NOT REPRODUCIBLE

**NO (REJECTED)**.
- Live source at `backend/src/api/auth.py:60-63` (`authenticated_user`) explicitly compares `request.headers.get("X-User-ID")` against `str(user.id)` and `request.headers.get("X-Organization-ID")` against `str(user.organization_id)`.
- Any mismatch raises `HTTPException(403, "User mismatch")` or `HTTPException(403, "Organization mismatch")` immediately.
- Because `application_router` applies `Depends(require_application_user)` to all human application routes, a caller cannot send a valid low-privilege JWT while spoofing a high-privilege user's UUID in `X-User-ID`.
- Therefore, the claim that `X-User-ID` spoofing enables active privilege escalation on `POST /documents/{id}/corrections` or `POST /documents/{id}/reject` is **empirically rejected**.

### 2. How are AUTH-ID-001 and AUTH-ID-002 classified?
- **AUTH-ID-001 (Legacy Actor Helper `get_current_user_id`)**: `backend/src/api/deps.py:31-43` directly reads `X-User-ID` with a dummy fallback UUID. In production, upstream JWT header binding prevents cross-user spoofing. Classification: **DEFENSE-IN-DEPTH / MAINTAINABILITY CLEANUP**.
- **AUTH-ID-002 (Unreachable RBAC Header Fallback)**: `backend/src/api/auth.py:112-128` queries the DB on headers when `current_user is None`. In real mounted traffic, `require_application_user` always runs first and never yields `None`. The fallback is only reachable when test fixtures override `require_application_user = lambda: None`. Classification: **LATENT UNSAFE FALLBACK / DEFENSE-IN-DEPTH CLEANUP**.

### 3. Are document review routes vulnerable to VIEWER mutation?
**NO**.
- `POST /documents/{id}/corrections` and `POST /documents/{id}/reject` call `await require_reviewer(db, org_id, user_id)`.
- `require_reviewer` queries `User.role.in_([UserRole.ADMIN, UserRole.MANAGER])`.
- An authenticated `VIEWER` receives `403 Forbidden` (`Manager or administrator review permission required`).
- Classification: **CURRENTLY PROTECTED VIA IN-BODY AUTHORIZATION**.
- Migrating to declarative `require_roles` is a CP3 consistency enhancement, not a vulnerability fix.

### 4. What is the actual count of vulnerable human application mutation routes?
**17 routes**.
- Total API routes: 116.
- Total mutating routes: 59.
- Machine / Webhook / Public routes: 17.
- Human application routes: 42.
- Out of 42 human application routes:
  - 17 Declaratively protected (`require_roles` or `require_whatsapp_admin`).
  - 4 Protected in-body (`require_reviewer` or `AuthorizationException`).
  - 4 Reporting calculations / user-scoped chat queries (non-mutating).
  - **17 ACTUALLY VULNERABLE** human application mutation routes completely lacking role enforcement.

### 5. Does AUTHZ-001 still outrank FIN-P1-105?
**YES (RANK #1 CONFIRMED)**.
- While the false-positive AUTH-002 exploit and document review claims were eliminated, 17 distinct business mutation surfaces (transactions, counterparties, projects, budgets, money movements, COA, payment accounts, bank reconciliation, inbox sync, etc.) remain open to `VIEWER` mutation.
- This represents an urgent perimeter authorization gap that takes precedence over internal tenant foreign-reference validation (FIN-P1-105).

---

## 2. CP1 Governance & Test Design Alignment

### 6. Are any RED tests manufactured from already-protected behavior?
**NO**.
- `POST /documents/{id}/corrections` and `POST /documents/{id}/reject` are explicitly classified as PASS characterization tests.
- `POST /periods` and `PATCH /periods/{id}/status` are classified as PASS characterization tests.
- Header mismatch (spoofing) behavior is tested as PASS characterization proving that 403 is already returned.
- RED tests are applied **ONLY** to the 17 genuinely vulnerable routes where `VIEWER` currently passes authorization.

### 7. Is the require_roles fallback reachable in production?
**NO**. It is unreachable in normal mounted traffic because `application_router` enforces `require_application_user` which never returns `None`. It is tested separately as a latent defense-in-depth unit test.

### 8. Did production code remain unchanged in CP1?
**YES**. Zero production files are modified in CP1. Only test harness and documentation artifacts are created/updated.

---

## 3. Findings Summary

| Finding ID | Classification | Severity | Current Behavior | Target Checkpoint |
|---|---|:---:|---|:---:|
| **AUTHZ-001** | Missing RBAC on 17 mutation routes | **CRITICAL (P1)** | VIEWER reaches mutation boundary without role denial | CP1 (RED) -> CP3 (GREEN) |
| **AUTH-ID-001** | Legacy actor helper `get_current_user_id` | **DEFENSE-IN-DEPTH** | Blocked upstream by JWT header check; anti-pattern | CP2 |
| **AUTH-ID-002** | Latent unreachable fallback in `require_roles` | **DEFENSE-IN-DEPTH** | Unreachable in production; reached only under test overrides | CP2 |
| **DOC-REV-001** | In-body document reviewer check | **MAINTAINABILITY** | VIEWER already receives 403; non-declarative | CP1 (PASS) -> CP3 |
| **PERIOD-001** | In-body accounting period check | **MAINTAINABILITY** | VIEWER already receives 403; non-declarative | CP1 (PASS) -> CP3 |

---

## 4. CP1 Verification

- **SPECIFICATION STATUS**: 100% reconciled to `c33112c1744e25d12ea1e30b9a133b6931c788b8`.
- **AUTHORIZATION MATRIX**: 17 vulnerable, 4 in-body protected, 17 declaratively protected, and 4 reporting/query routes.
- **TEST EVIDENCE**: The focused suite has 10 passing characterizations. The 17 RED cases each fail only because a controlled service sentinel proves VIEWER reached the mutation boundary before a `403`.
- **INDEPENDENT REVIEW**: One Medium finding (ASGI exception-noise from the original sentinel) was resolved by a controlled `HTTPException(418)` plus an explicit boundary-reached assertion. Review found no Critical or High issue and no production-scope breach.
- **DATABASE MIGRATION REQUIRED**: **NO**.
- **ACCOUNTING LOGIC CHANGED**: **NO**.
- **PRODUCTION CODE CHANGED IN CP1**: **NO**.
- **CP1 STATUS**: Verified and committed.

---

## 5. CP3 Declarative Role Enforcement Verification

- **ROUTE INVENTORY**: The human mutation inventory remains 38 routes: 17 formerly vulnerable, 4 protected in-body, and 17 already declaratively protected. The four reporting/query POST routes remain non-mutating; machine, webhook, and public routes remain outside human RBAC.
- **FORMERLY VULNERABLE ROUTES**: All 17 Category A routes now declare `require_roles(...)` with the approved policy: 13 routine operational routes allow ADMIN/MANAGER/OPERATOR; project status and budget allow ADMIN/MANAGER; COA and payment-account creation allow ADMIN only.
- **SIDE-EFFECT SAFETY**: The CP1 VIEWER boundary suite is now green for all 17 routes. Each request returns 403 and its controlled mutation/service sentinel is not called.
- **POSITIVE MATRIX**: Route-level boundary probes verify ADMIN reaches 17 routes, MANAGER 15, and OPERATOR 13; every excluded role returns 403 before the mutation boundary.
- **CP2 REGRESSION**: JWT principal identity, optional matching `X-User-ID`, principal-matched `X-Organization-ID`, 401 without a verified principal, and 403 mismatch behavior remain green.
- **IN-BODY SCOPE**: Document correction/rejection and accounting-period authorization remain unchanged and continue to be characterized as protected in-body. CP3 intentionally did not migrate them, per the approved CP3 scope boundary.
- **REGRESSION EVIDENCE**: AUTHZ suite 103 passed; affected document/auth/period/tenant regression selection 124 passed; Feature 011 and machine-auth subset 21 passed. Python compile, `git diff --check`, dependency check, repository-safety check, and locked production dependency audit passed. Ruff and mypy are not configured in the declared backend environment.
- **INDEPENDENT REVIEW**: Bounded read-only senior review passed with Critical 0, High 0, Medium 0, Low 0.
- **CP3 STATUS**: Verified and committed as `1481a5f6ebcb2eaefe2bafa0c99552a50e1461a6`. CP4 remains responsible for full backend/frontend verification, delivery, PR, CI, and merge.
