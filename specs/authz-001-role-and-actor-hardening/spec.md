# Feature Specification: Complete Role Enforcement & Actor Attribution Hardening

**Feature**: AUTHZ-001 (incorporating AUTH-002)  
**Feature Branch**: `hermes/authz-001-role-enforcement`  
**Status**: SPECIFIED & VALIDATED (Ready for CP1 Implementation)  
**Priority**: P1 (Security & Authorization Remediation)  
**Authority**: Constitution v2.0.0, Financial Concept v1, AGENTS.md, Security Audit 2026-09-12  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  

---

## 1. Purpose & Scope

This specification establishes complete, non-bypassable backend role-based access control (RBAC) and verifies authoritative actor identity across all human application mutation endpoints in `mikaelzo-blip/financial-saas`. It resolves all verified security audit findings regarding role enforcement gaps (**AUTHZ-001**) and eliminates caller-controlled actor identity / header impersonation (**AUTH-002**).

### Core Remediation Objectives
1. **Enforce VIEWER Read-Only Invariant**: Ensure that the `VIEWER` role is strictly denied (`403 Forbidden`) from mutating any application resource across all 42 human application endpoints.
2. **Close Unprotected Mutation Routes**: Enforce explicit, declarative role checks (`require_roles(...)`) on all 19 application mutation routes previously lacking role authorization.
3. **Eliminate Caller-Controlled Actor Identity (AUTH-002)**: Remove `deps.py:get_current_user_id` and the dummy fallback UUID `00000000-0000-0000-0000-000000000001`. Guarantee that actor attribution (`actor_id`, `created_by`, `user_id`) originates exclusively from the cryptographically verified JWT principal.
4. **Purge Unsafe Header Fallbacks in RBAC Gate**: Delete lines 112–128 of `backend/src/api/auth.py:require_roles` that allow unauthenticated requests with `X-User-ID` and `X-Organization-ID` to impersonate privileged users when `current_user is None`.
5. **Protect Document Review Integrity**: Remediate privilege escalation and identity spoofing on `POST /documents/{id}/corrections` and `POST /documents/{id}/reject`.
6. **Preserve Machine & Webhook Boundaries**: Maintain dedicated authentication protocols for Meta WhatsApp webhooks (HMAC-SHA256) and Hermes machine integration (Bearer tokens).

---

## 2. Verified Audit Findings & Classification

| Finding ID | Classification | Exact Evidence & Defect Summary |
|---|---|---|
| **AUTH-002 / FIN-SEC-001** | **CONFIRMED** | `backend/src/api/deps.py:31-43` defines `get_current_user_id`, which extracts caller identity from `X-User-ID` header, defaulting to `00000000-0000-0000-0000-000000000001`. Consumed in `documents.py:68, 121, 271`. Callers can spoof any user UUID for document uploads, corrections, rejections, and audit log entries. |
| **AUTHZ-001 / FIN-SEC-002** | **CONFIRMED** | `backend/src/api/auth.py:112-128` contains an unauthenticated fallback block in `require_roles`: if `current_user is None`, it queries the database for `uid` and `oid` supplied directly via `X-User-ID` and `X-Organization-ID` headers, granting full `ADMIN` or `MANAGER` authorization without token or password verification. |
| **AUTHZ-001 / FIN-SEC-003** | **CONFIRMED** | 19 human application mutation endpoints under `application_router` lack explicit role checks (`require_roles`), relying only on `require_application_user`. As a result, authenticated users with the `VIEWER` role can create counterparties, projects, money movements, draft transactions, bank reconciliation imports/matches, COA accounts, payment accounts, and review flags. |
| **AUTH-002 / FIN-SEC-004** | **CONFIRMED** | In `documents.py:118-125` and `268-274`, `correct_document` and `reject_document_candidate` use in-body `require_reviewer(db, org_id, user_id)` where `user_id` is supplied by `get_current_user_id`. An attacker supplying a Manager's UUID in `X-User-ID` bypasses authorization checks and attributes changes to the spoofed user. |

---

## 3. Security Invariants

The implementation must uphold the following hard security invariants:

- **AUTHZ-R01 (VIEWER Mutation Prohibition)**: The `VIEWER` role MUST receive `403 Forbidden` on every human application mutation endpoint (POST, PUT, PATCH, DELETE).
- **AUTHZ-R02 (Explicit Backend Role Enforcement)**: Every human application mutation endpoint MUST have explicit, declarative backend role enforcement via `Depends(require_roles(...))`.
- **AUTHZ-R03 (Backend Authority)**: Authorization is enforced authoritatively at the backend HTTP boundary. Frontend route hiding, menu suppression, or button disabling MUST NOT be treated as security enforcement.
- **AUTHZ-R04 (Authoritative Actor Principal)**: Actor identity (`actor_id`, `created_by`, `matched_by`) MUST derive strictly from the cryptographically verified JWT principal (`current_user.id`).
- **AUTHZ-R05 (Anti-Spoofing Invariant)**: Caller-supplied headers such as `X-User-ID` MUST NOT override, impersonate, or substitute for the verified JWT principal.
- **AUTHZ-R06 (Anti-Elevation Invariant)**: Caller-supplied headers such as `X-Role` or `X-User-ID` MUST NOT elevate application privileges or satisfy role requirements.
- **AUTHZ-R07 (Tenant Boundary Enforcement)**: An authenticated principal MUST NOT operate on resources outside their assigned `current_user.organization_id`. Cross-tenant requests MUST fail closed with `403 Forbidden` or `404 Not Found`.
- **AUTHZ-R08 (Machine/Webhook Boundary Preservation)**: Webhooks (Meta WhatsApp HMAC) and machine M2M endpoints (Hermes Bearer tokens) MUST retain their dedicated, isolated authentication models and MUST NOT be coupled to browser-user JWT dependencies.
- **AUTHZ-R09 (403 Forbidden Semantics)**: An authenticated caller who lacks the required role for an endpoint MUST receive `403 Forbidden`.
- **AUTHZ-R10 (401 Unauthorized Semantics)**: A request lacking valid authentication credentials (missing, expired, or tampered token) MUST receive `401 Unauthorized`.
- **AUTHZ-R11 (Authorized Workflow Compatibility)**: Legitimate operational workflows for `ADMIN`, `MANAGER`, and `OPERATOR` roles MUST remain functional according to the approved role matrix.
- **AUTHZ-R12 (Audit Attribution Fidelity)**: All audit events emitted by mutations MUST record the verified `current_user.id` as `actor_id`.
- **AUTHZ-R13 (Zero Financial Logic Alteration)**: No accounting rules, debit/credit logic, journal posting invariants, tax classifications, or financial balances may be altered.
- **AUTHZ-R14 (Automated Regression Coverage)**: All authorization rules MUST have route-level automated test coverage asserting both negative denial (`403`) and positive execution for authorized roles.

---

## 4. Privilege Escalation Characterization (AUTH-002)

### Defect Scenario
1. An attacker obtains valid credentials for a low-privilege account (e.g. `VIEWER` or `OPERATOR`).
2. The attacker calls `POST /api/v1/documents/{document_id}/corrections` or `POST /api/v1/documents/{document_id}/reject`.
3. The request includes header `X-User-ID: <admin-or-manager-uuid>`.
4. The endpoint executes:
   ```python
   user_id: uuid.UUID = Depends(get_current_user_id) # returns <admin-or-manager-uuid>
   await require_reviewer(db, org_id, user_id)       # queries DB for <admin-or-manager-uuid>, sees ADMIN, PASSES!
   ```
5. The attacker successfully mutates the candidate transaction or rejects the document, and the audit log records `<admin-or-manager-uuid>` as the actor.

### Hardened Architecture Design
1. Replace `get_current_user_id` with `current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))`.
2. Extract `user_id = current_user.id` directly from the authenticated principal.
3. Remove redundant `require_reviewer` helper.
4. Pass `current_user.id` to `DocumentCorrection` and `AuditService.log_event`.
5. Remove `deps.py:get_current_user_id` entirely from the codebase.

---

## 5. Approved Role Permission Matrix

Derived from Constitution v2.0.0 and Feature 011 precedents (see full details in [contracts/authorization-matrix.md](contracts/authorization-matrix.md)):

### Summary of Policy Mapping for the 19 Vulnerable Endpoints

| Endpoint Path | VIEWER | OPERATOR | MANAGER | ADMIN | Authoritative Policy Basis |
|---|:---:|:---:|:---:|:---:|---|
| `POST /transactions` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. III; operational transaction drafting. |
| `POST /projects` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. II & III; operational project drafting. |
| `PATCH /projects/{id}/status` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Project lifecycle transition enforces financial closure guards. |
| `POST /projects/{id}/budgets` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Baseline budget allocations establish cost control limits. |
| `POST /counterparties` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational creation of customers/vendors. |
| `POST /coa` | **DENY** | **DENY** | **DENY** | **ALLOW** | Const. Prin. V; COA structure is administrative governance. |
| `POST /payment-accounts` | **DENY** | **DENY** | **DENY** | **ALLOW** | Corporate treasury / bank accounts are administrative governance. |
| `POST /money-movements` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. VI; daily operational cash transfers and settlements. |
| `POST /bank-reconciliation/imports` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational intake of bank statement files. |
| `POST /bank-reconciliation/imports/{id}/auto-match` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Algorithmic matching against ledger transactions. |
| `POST /bank-reconciliation/reconcile` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational reconciliation matching. |
| `POST /documents/upload` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. VII; operational document intake. |
| `POST /documents/{id}/retry` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational OCR retry. |
| `POST /documents/{id}/corrections` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Existing code precedent (`require_reviewer`); review queue action. |
| `POST /documents/{id}/reject` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Existing code precedent (`require_reviewer`); formal rejection. |
| `POST /transactions/{id}/review-flags` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. IX; operational users route uncertainty to review queue. |
| `POST /inbox/capture` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Staged ingestion of remote messaging payloads. |
| `POST /inbox/sync` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational worker backlog pull. |
| `POST /inbox/sessions/{id}/analyze` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational trigger of deferred OCR analysis. |

---

## 6. Scope Decisions

1. **Frontend Scope Decision**:
   - **Backend Security**: MANDATORY NOW. Backend enforcement is authoritative.
   - **Frontend Role Hiding**: OPTIONAL FOLLOW-UP. UI changes must not delay backend remediation.
2. **Database / Migration Decision**:
   - **DATABASE MIGRATION REQUIRED**: **NO**.
   - The existing schema contains `User.role` (`ADMIN`, `MANAGER`, `OPERATOR`, `VIEWER`), `Transaction.created_by`, `AuditLog.actor_id`, and `Document.created_by`. No new tables or columns are required.
3. **Accounting Logic Decision**:
   - **ACCOUNTING LOGIC CHANGE**: **NO**.
   - Zero changes to debit/credit posting rules, journal entry balancing, sequence numbering, or financial reports.

---

## 7. Checkpoints & Implementation Gates

- **Checkpoint 1 (CP1)**: Characterization + RED regression test suite + finalized 100% role matrix.
  - Reproduce AUTH-002 spoofing and VIEWER mutation access in failing tests.
  - Establish complete parameterized regression baseline across all roles.
- **Checkpoint 2 (CP2)**: Verified principal & actor identity hardening.
  - Purge header fallback in `auth.py:require_roles`.
  - Delete `deps.py:get_current_user_id`.
  - Refactor `documents.py` (upload, retry, corrections, reject) to ingest verified `current_user`.
  - Harmonize test fixtures in `tests/conftest.py`.
- **Checkpoint 3 (CP3)**: Complete role enforcement across all 19 application mutation routes.
  - Apply `require_roles(...)` declarative dependencies to all vulnerable endpoints.
  - Verify `VIEWER` receives `403 Forbidden` across all 42 human application mutation routes.
  - Verify `ADMIN`, `MANAGER`, and `OPERATOR` retain authorized access.
- **Checkpoint 4 (CP4)**: Full regression, security review, CI, PR, and delivery.
  - Run full backend suite (555+ tests).
  - Run frontend lint, typecheck, tests, and build.
  - Verify zero Constitution violations and 100% requirement traceability.

---

## 8. Requirements Traceability

| Requirement ID | Summary | Checkpoint | Test Case | Gate |
|---|---|:---:|---|---|
| **AUTHZ-R01** | VIEWER cannot mutate any human application resource | CP1, CP3 | `test_viewer_denied_on_all_mutations` | 403 Forbidden on 42 routes |
| **AUTHZ-R02** | Explicit backend role enforcement on every mutation | CP3 | `test_route_dependency_inspection` | Zero un-annotated mutation routes |
| **AUTHZ-R03** | Backend security authoritative; no client trust | CP3 | `test_direct_api_role_rejection` | Direct HTTP requests rejected |
| **AUTHZ-R04** | Actor identity strictly derived from JWT principal | CP2 | `test_actor_attribution_fidelity` | `current_user.id` recorded in entity/audit |
| **AUTHZ-R05** | `X-User-ID` cannot impersonate another user | CP1, CP2 | `test_spoofed_x_user_id_rejected` | Header ignored or rejected |
| **AUTHZ-R06** | `X-Role` or header fallback cannot elevate role | CP1, CP2 | `test_header_role_fallback_eliminated` | Unauthenticated header rejected with 401 |
| **AUTHZ-R07** | Cross-tenant authenticated principal cannot operate | CP2, CP3 | `test_cross_tenant_mutation_rejected` | 403/404 on cross-tenant UUIDs |
| **AUTHZ-R08** | Machine/webhook endpoints retain dedicated auth | CP3, CP4 | `test_whatsapp_webhook_hmac_preserved`, `test_hermes_m2m_preserved` | Webhooks and M2M pass green |
| **AUTHZ-R09** | 403 returned for authenticated but unauthorized role | CP1, CP3 | `test_unauthorized_role_returns_403` | Status code == 403 |
| **AUTHZ-R10** | 401 returned for unauthenticated request | CP1, CP2 | `test_unauthenticated_returns_401` | Status code == 401 |
| **AUTHZ-R11** | Authorized ADMIN/MANAGER/OPERATOR workflows preserved | CP3 | `test_authorized_role_workflows_compatible` | Status code 200/201/202 |
| **AUTHZ-R12** | Audit attribution receives verified actor | CP2 | `test_audit_log_actor_attribution` | Audit log has real user UUID |
| **AUTHZ-R13** | Zero accounting, tax, or financial data changes | CP4 | Full backend test suite | 555+ existing tests pass |
| **AUTHZ-R14** | Route-level automated regression coverage | CP1, CP4 | `test_authz001_role_enforcement.py` | 100% route test coverage |
