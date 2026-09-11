# Requirements Checklist: Role Enforcement & Actor Attribution

**Feature**: AUTHZ-001 & AUTH-002  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  
**Specification**: [specs/authz-001-role-and-actor-hardening/spec.md](../spec.md)  
**Contract**: [specs/authz-001-role-and-actor-hardening/contracts/authorization-matrix.md](../contracts/authorization-matrix.md)  

---

## 1. Security Invariants Checklist

- [ ] **AUTHZ-R01 (VIEWER Mutation Prohibition)**:
  - `VIEWER` role receives `403 Forbidden` on every human application mutation endpoint (42 routes).
  - Validated by parameterized tests iterating over all 42 routes.
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
  - `X-User-ID` header is either ignored or asserted to match the verified token.
  - Supplying another user's UUID in `X-User-ID` cannot change actor attribution or satisfy reviewer checks.
- [ ] **AUTHZ-R06 (Anti-Elevation Invariant)**:
  - Header fallback in `auth.py:require_roles` (lines 112–128) is eliminated.
  - Unauthenticated requests cannot elevate privileges via headers.
- [ ] **AUTHZ-R07 (Tenant Boundary Enforcement)**:
  - Authenticated user's `current_user.organization_id` is authoritative.
  - Cross-tenant requests fail closed with 403 or 404.
- [ ] **AUTHZ-R08 (Machine/Webhook Boundary Preservation)**:
  - Meta WhatsApp webhooks retain HMAC-SHA256 verification.
  - Hermes machine M2M endpoints retain bearer token verification.
- [ ] **AUTHZ-R09 (403 Forbidden Semantics)**:
  - Authenticated users lacking the required role receive `403 Forbidden` with informative detail.
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

## 2. Traceability & Coverage Matrix

- **Total Mutating Routes**: 59
- **Human Application Mutation Routes**: 42
- **Previously Protected Routes**: 21
- **Vulnerable Routes Requiring Role Hardening**: 21 (19 entity mutations + 2 accounting period routes converted from in-body to declarative)
- **Role-Mapped Routes**: 42 / 42 (100%)
- **Test-Mapped Routes**: 42 / 42 (100%)
- **Traceability Gate**: **100% COMPLETE**
