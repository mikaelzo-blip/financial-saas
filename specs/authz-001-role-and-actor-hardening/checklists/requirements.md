# Requirements Checklist: Role Enforcement & Actor Attribution

**Feature**: AUTHZ-001 (Reconciled Baseline)
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Specification**: [specs/authz-001-role-and-actor-hardening/spec.md](../spec.md)  
**Contract**: [specs/authz-001-role-and-actor-hardening/contracts/authorization-matrix.md](../contracts/authorization-matrix.md)  

---

## 1. Security Invariants Checklist

- [ ] **AUTHZ-R01 (VIEWER Mutation Prohibition)**:
  - `VIEWER` role receives `403 Forbidden` on the 17 CP1 RED targets, four in-body protected routes, and 17 declaratively protected routes across CP1–CP4.
  - CP1 instruments the 17 unprotected routes and characterizes the four in-body guards; CP3/CP4 complete the all-38 mutation matrix.
- [ ] **AUTHZ-R02 (Explicit Backend Role Enforcement)**:
  - Every human application mutation endpoint declares `Depends(require_roles(...))` or equivalent declarative guard.
  - Zero routes rely solely on `require_application_user` without role restriction.
- [ ] **AUTHZ-R03 (Backend Authority)**:
  - Role enforcement is evaluated at the FastAPI backend HTTP router boundary.
  - No assumption of frontend menu hiding as security.
- [ ] **AUTHZ-R04 (Authoritative Actor Principal)**:
  - `current_user.id` from the verified JWT principal is the sole source of actor identity.
  - `created_by`, `approved_by`, `rejected_by`, `corrected_by`, and `actor_id` are bound to `current_user.id`.
- [ ] **AUTHZ-R05 (Anti-Spoofing Invariant)**:
  - `X-User-ID` header mismatching the JWT subject returns `403 User mismatch`.
  - Supplying another user's UUID in `X-User-ID` cannot change actor attribution or satisfy reviewer checks.
- [ ] **AUTHZ-R06 (Anti-Elevation Invariant)**:
  - Header fallback in `auth.py:require_roles` (lines 112–128) is eliminated.
  - Unauthenticated requests cannot look up users or elevate privileges via headers.
- [ ] **AUTHZ-R07 (Tenant Boundary Enforcement)**:
  - Authenticated user's `current_user.organization_id` is authoritative.
  - Header mismatch returns `403 Organization mismatch`; cross-tenant entity lookups fail closed with 404.
- [ ] **AUTHZ-R08 (Machine/Webhook Boundary Preservation)**:
  - Meta WhatsApp webhooks retain HMAC-SHA256 verification.
  - Hermes machine M2M endpoints retain bearer token verification.
- [ ] **AUTHZ-R09 (403 Forbidden Semantics)**:
  - Authenticated users lacking the required role receive `403 Forbidden`.
- [ ] **AUTHZ-R10 (401 Unauthorized Semantics)**:
  - Missing, invalid, or expired tokens receive `401 Unauthorized`.
- [ ] **AUTHZ-R11 (Authorized Workflow Compatibility)**:
  - Legitimate operational flows for `ADMIN`, `MANAGER`, and `OPERATOR` pass green.
- [ ] **AUTHZ-R12 (Audit Attribution Fidelity)**:
  - Audit log entries record the authentic `current_user.id` as `actor_id`.
- [ ] **AUTHZ-R13 (Zero Financial Logic Alteration)**:
  - Debit/credit rules, double-entry equality, account mappings, and tax rules remain unchanged.
- [ ] **AUTHZ-R14 (Automated Regression Coverage)**:
  - Route-level automated test suite covers all negative and positive role permutations.

---

## 2. Checkpoint Deliverables Checklist

### CP1: Honest Characterization & RED Suite
- [x] `backend/tests/security/test_authz001_role_enforcement.py` created.
- [x] Honest RED tests for all 17 vulnerable endpoints fail only when the instrumented mutation boundary is reached before a `403`.
- [x] PASS characterization for header mismatches (X-User-ID, X-Organization-ID -> 403).
- [x] PASS characterization for missing/invalid JWT (401).
- [x] PASS characterization for document review routes denying `VIEWER` (403).
- [x] PASS characterization for accounting period routes denying `VIEWER` (403).
- [x] Latent fallback behavior documented via unit test.
- [x] Zero production code modified.

### CP2: Actor Hardening
- [x] `deps.py:get_current_user_id` deleted.
- [x] `auth.py:require_roles` header fallback deleted.
- [x] `documents.py` refactored to consume verified `current_user: User`.
- [x] `tests/conftest.py` fixture updated to inject an authentic user principal.

### CP3: Declarative Role Enforcement
- [x] `require_roles(...)` applied across all 17 vulnerable endpoints with the approved role matrix.
- [x] Existing in-body checks in document correction/rejection and accounting periods were intentionally preserved under CP3 scope; their protections remain characterized.
- [x] All 17 CP1 RED tests turn GREEN with denied-request side-effect sentinels not called.
- [x] Route-level positive access tests pass for authorized roles; ADMIN reaches 17 boundaries, MANAGER 15, and OPERATOR 13.

### CP4: Delivery & Verification
- [ ] Full backend regression suite passes (555+ tests).
- [ ] Frontend lint, typecheck, build pass.
- [ ] Zero Constitution violations.
- [ ] PR merged to `main`.
