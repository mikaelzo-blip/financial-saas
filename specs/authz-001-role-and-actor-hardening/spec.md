# Feature Specification: Complete Role Enforcement & Actor Attribution Hardening

**Feature**: AUTHZ-001 (Reconciled Baseline)
**Feature Branch**: `hermes/authz-001-role-and-actor-hardening`
**Status**: CP1 verified and committed
**Priority**: P1 (Security & Authorization Remediation — Outranks FIN-P1-105)
**Authority**: Constitution v2.0.0, Financial Concept v1, AGENTS.md, Security Audit 2026-09-12  
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`

---

## 1. Purpose & Scope

This specification establishes complete, non-bypassable backend role-based access control (RBAC) and authoritative actor identity across all human application mutation endpoints in `mikaelzo-blip/financial-saas`. It resolves all verified security audit findings regarding role enforcement gaps (**AUTHZ-001**) and cleans up legacy caller-controlled actor identity and header fallback helpers (**AUTH-ID-001**, **AUTH-ID-002**).

### Core Remediation Objectives
1. **Enforce VIEWER Read-Only Invariant**: Ensure that the `VIEWER` role is strictly denied (`403 Forbidden`) from mutating any application resource across all human application mutation endpoints.
2. **Close Unprotected Mutation Routes (17 Routes)**: Enforce explicit, declarative role checks (`require_roles(...)`) on all 17 application mutation routes that currently lack role authorization.
3. **Eliminate Legacy Actor Helper (AUTH-ID-001 Defense-in-Depth)**: Remove `deps.py:get_current_user_id` and the dummy fallback UUID `00000000-0000-0000-0000-000000000001`. Guarantee that actor attribution (`actor_id`, `created_by`, `user_id`) originates exclusively from the cryptographically verified JWT principal (`current_user.id`).
4. **Purge Unreachable Header Fallback in RBAC Gate (AUTH-ID-002 Defense-in-Depth)**: Delete lines 112–128 of `backend/src/api/auth.py:require_roles` that allow unauthenticated requests with `X-User-ID` and `X-Organization-ID` to look up users when `current_user is None` (only reachable under test dependency overrides).
5. **Harmonize Protected Routes to Declarative RBAC**: Migrate in-body authorization in `POST /documents/{id}/corrections`, `POST /documents/{id}/reject`, `POST /periods`, and `PATCH /periods/{id}/status` to declarative `require_roles(...)` without altering policy.
6. **Preserve Machine & Webhook Boundaries**: Maintain dedicated authentication protocols for Meta WhatsApp webhooks (HMAC-SHA256) and Hermes machine integration (Bearer tokens).

---

## 2. Verified Audit Findings & Live Source Reconciliation

| Finding ID | Historical Claim | Live Source Audit Status | Exact Evidence & Current Classification |
|---|---|---|---|
| **AUTH-002 (Header Spoof Elevation)** | Low-privilege JWT + privileged `X-User-ID` escalates document reviewer permissions to mutate candidate or bypass review. | **REJECTED / NOT REPRODUCIBLE** | `src/api/auth.py:60-63` verifies `request.headers.get("X-User-ID") == str(user.id)` and `X-Organization-ID == str(user.organization_id)` against the verified JWT principal. Mismatched headers immediately return `403 Forbidden` (`User mismatch` / `Organization mismatch`) before route handler or actor helper execution. |
| **AUTH-ID-001 (Legacy Actor Helper)** | `backend/src/api/deps.py:31-43` defines `get_current_user_id` reading `X-User-ID` with dummy fallback UUID. | **CONFIRMED (DEFENSE-IN-DEPTH)** | Consumed in `documents.py:68, 121, 271`. Not exploitable for cross-user impersonation in normal traffic due to JWT header binding, but represents an architectural anti-pattern and unsafe fallback that must be replaced with direct `current_user.id` binding. |
| **AUTH-ID-002 (RBAC Fallback Code)** | `backend/src/api/auth.py:112-128` contains an unauthenticated fallback block in `require_roles` querying DB on headers if `current_user is None`. | **CONFIRMED (LATENT UNSAFE FALLBACK)** | Unreachable in real mounted human application traffic because `application_router` requires `require_application_user` (which never yields `None`). Only reachable when `require_application_user` is mocked to `None` in test fixtures (`conftest.py:50`). Must be deleted to eliminate latent bypass risk. |
| **AUTHZ-001 (Perimeter Role Gaps)** | Human application mutation endpoints under `application_router` lack explicit role checks, allowing `VIEWER` mutation. | **CONFIRMED (CRITICAL P1)** | Exactly **17 human application mutation endpoints** completely lack role checks (`require_roles` or in-body checks). Authenticated `VIEWER` can create transactions, counterparties, projects, money movements, bank reconciliation imports/matches, COA accounts, payment accounts, and review flags. |
| **DOC-REV-001 (Document Review Security)** | `correct_document` and `reject_document_candidate` allow `VIEWER` mutation via header spoofing. | **REJECTED (ALREADY PROTECTED IN-BODY)** | `documents.py:125, 274` calls `await require_reviewer(db, org_id, user_id)` which queries `User.role.in_([UserRole.ADMIN, UserRole.MANAGER])`. An authenticated `VIEWER` receives `403 Forbidden` (`Manager or administrator review permission required`). Spoofed headers are blocked by JWT verification. Currently protected; CP3 will standardize to declarative `require_roles`. |

---

## 3. Security Invariants

The implementation must uphold the following hard security invariants:

- **AUTHZ-R01 (VIEWER Mutation Prohibition)**: The `VIEWER` role MUST receive `403 Forbidden` on every human application mutation endpoint (POST, PUT, PATCH, DELETE).
- **AUTHZ-R02 (Explicit Backend Role Enforcement)**: Every human application mutation endpoint MUST have explicit, declarative backend role enforcement via `Depends(require_roles(...))`.
- **AUTHZ-R03 (Backend Authority)**: Authorization is enforced authoritatively at the backend HTTP boundary. Frontend route hiding, menu suppression, or button disabling MUST NOT be treated as security enforcement.
- **AUTHZ-R04 (Authoritative Actor Principal)**: Actor identity (`actor_id`, `created_by`, `matched_by`) MUST derive strictly from the cryptographically verified JWT principal (`current_user.id`).
- **AUTHZ-R05 (Anti-Spoofing Invariant)**: Caller-supplied headers such as `X-User-ID` MUST NOT override, impersonate, or substitute for the verified JWT principal. Mismatches MUST return `403 Forbidden`.
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

## 4. Reconciled Defect Scenario & Honest Characterization

### The Actual Security Gap (AUTHZ-001)
1. An attacker obtains valid credentials for an active user with the `VIEWER` role.
2. The user obtains a valid signed JWT bearer token and supplies matching `X-User-ID` and `X-Organization-ID` headers.
3. The user sends mutating requests to any of the 17 unprotected endpoints (e.g. `POST /api/v1/counterparties`, `POST /api/v1/projects`, `POST /api/v1/transactions`, `POST /api/v1/money-movements`, `POST /api/v1/coa`, `POST /api/v1/payment-accounts`, `POST /api/v1/inbox/sync`).
4. `application_router` executes `require_application_user`:
   - Validates JWT signature;
   - Verifies user is active;
   - Verifies headers match JWT claims (`X-User-ID == user.id`, `X-Organization-ID == user.organization_id`);
   - PASSES!
5. Because none of these 17 endpoints declare `require_roles(...)` or check `user.role`, the handler executes and the mutation succeeds.
6. This violates the core invariant that `VIEWER` is strictly read-only.

### Why the Old AUTH-002 Exploit Claim is Rejected
- The previous claim assumed that a `VIEWER` could send their own token but put an `ADMIN`'s UUID in `X-User-ID` to satisfy `require_reviewer`.
- On current `origin/main` (`3d51609`), `src/api/auth.py:62` asserts `if request.headers.get("X-User-ID") != str(user.id): raise HTTPException(403, "User mismatch")`.
- The request is terminated with HTTP 403 before `require_reviewer` or `get_current_user_id` ever runs.
- Thus, header-based privilege escalation is NOT an active exploit on live code.
- Removing `get_current_user_id` and the `current_user is None` fallback in `require_roles` is defense-in-depth code hygiene, not an active exploit patch.

---

## 5. Approved Role Permission Matrix

Derived from Constitution v2.0.0 and Feature 011 precedents (see full details in [contracts/authorization-matrix.md](contracts/authorization-matrix.md)):

### The 17 Actually Vulnerable Endpoints (Category A — CP1 RED Targets)

| # | Endpoint Path | Handler | VIEWER | OPERATOR | MANAGER | ADMIN | Authoritative Policy Basis |
|---|---|---|:---:|:---:|:---:|:---:|---|
| 1 | `POST /transactions` | `transactions:create_transaction` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. III; operational transaction drafting. |
| 2 | `POST /projects` | `projects:create_project` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. II & III; operational project drafting. |
| 3 | `PATCH /projects/{id}/status` | `projects:update_project_status` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Project lifecycle transition enforces financial closure guards. |
| 4 | `POST /projects/{id}/budgets` | `projects:add_or_update_project_budget` | **DENY** | **DENY** | **ALLOW** | **ALLOW** | Baseline budget allocations establish cost control limits. |
| 5 | `POST /counterparties` | `counterparties:create_counterparty` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational creation of customers/vendors. |
| 6 | `POST /coa` | `reference_data:create_coa` | **DENY** | **DENY** | **DENY** | **ALLOW** | Const. Prin. V; COA structure is administrative governance. |
| 7 | `POST /payment-accounts` | `reference_data:create_payment_account` | **DENY** | **DENY** | **DENY** | **ALLOW** | Corporate treasury / bank accounts are administrative governance. |
| 8 | `POST /money-movements` | `money_movements:create_money_movement` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. VI; daily operational cash transfers and settlements. |
| 9 | `POST /bank-reconciliation/imports` | `bank_reconciliation:upload_bank_statement` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational intake of bank statement files. |
| 10 | `POST /bank-reconciliation/imports/{id}/auto-match` | `bank_reconciliation:auto_match_statement` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Algorithmic matching against ledger transactions. |
| 11 | `POST /bank-reconciliation/reconcile` | `bank_reconciliation:manual_reconcile` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational reconciliation matching. |
| 12 | `POST /documents/upload` | `documents:upload_document` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. VII; operational document intake. |
| 13 | `POST /documents/{id}/retry` | `documents:retry_document` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational OCR retry. |
| 14 | `POST /transactions/{id}/review-flags` | `review:add_review_flag` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Const. Prin. IX; operational users route uncertainty to review queue. |
| 15 | `POST /inbox/capture` | `inbox:capture_remote_message` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Staged ingestion of remote messaging payloads. |
| 16 | `POST /inbox/sync` | `inbox:sync_backlog` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational worker backlog pull. |
| 17 | `POST /inbox/sessions/{id}/analyze` | `inbox:analyze_document_session` | **DENY** | **ALLOW** | **ALLOW** | **ALLOW** | Operational trigger of deferred OCR analysis. |

### Protected-but-Non-Declarative Endpoints (Category B — PASS Characterization)
- `POST /documents/{id}/corrections`: In-body `require_reviewer(ADMIN, MANAGER)`. VIEWER denied with 403.
- `POST /documents/{id}/reject`: In-body `require_reviewer(ADMIN, MANAGER)`. VIEWER denied with 403.
- `POST /periods`: In-body `current_user.role not in (ADMIN, MANAGER)`. VIEWER denied with 403.
- `PATCH /periods/{id}/status`: In-body `current_user.role not in (ADMIN, MANAGER)`. VIEWER denied with 403.

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

- **Checkpoint 1 (CP1)**: Characterization + Honest RED Regression Suite + Reconciled Spec Kit.
  - Assert `VIEWER` is denied (`403`) across the 17 actually vulnerable routes (failing currently -> honest RED).
  - Add PASS characterization proving header spoofing returns `403` (`User mismatch` / `Organization mismatch`).
  - Add PASS characterization proving document review routes deny `VIEWER` with `403`.
  - Add PASS characterization proving accounting periods routes deny `VIEWER` with `403`.
  - Document latent fallback behavior in `require_roles`.
  - Zero production code edits.
- **Checkpoint 2 (CP2)**: Verified Principal & Defense-in-Depth Actor Attribution Hardening.
  - Purge unreachable header fallback lines 112–128 in `auth.py:require_roles`.
  - Delete `deps.py:get_current_user_id` and dummy fallback UUID.
  - Refactor `documents.py` to ingest verified `current_user: User`.
  - Harmonize test fixtures in `tests/conftest.py`.
- **Checkpoint 3 (CP3)**: Declarative Role Enforcement Across All Vulnerable and In-Body Routes.
  - Apply `require_roles(...)` declarative dependencies to the 17 vulnerable endpoints.
  - Migrate in-body checks on document review and accounting period endpoints to `require_roles(...)`.
  - Verify `VIEWER` receives `403 Forbidden` across all 38 human application mutation routes.
  - Verify `ADMIN`, `MANAGER`, and `OPERATOR` retain authorized access.
- **Checkpoint 4 (CP4)**: Full Regression, Security Review, CI, PR, and Delivery.
  - Run full backend suite (555+ tests).
  - Run frontend lint, typecheck, tests, and build.
  - Verify zero Constitution violations and 100% requirement traceability.

---

## 8. Requirements Traceability

| Requirement ID | Summary | Checkpoint | Test Case | Gate |
|---|---|:---:|---|---|
| **AUTHZ-R01** | VIEWER cannot mutate any human application resource | CP1, CP3 | `test_viewer_denied_before_reaching_vulnerable_mutation_boundary` | 403 Forbidden on all mutation routes |
| **AUTHZ-R02** | Explicit backend role enforcement on every mutation | CP3 | `test_route_dependency_inspection` | Zero un-annotated mutation routes |
| **AUTHZ-R03** | Backend security authoritative; no client trust | CP3 | `test_direct_api_role_rejection` | Direct HTTP requests rejected |
| **AUTHZ-R04** | Actor identity strictly derived from JWT principal | CP2 | `test_actor_attribution_fidelity` | `current_user.id` recorded in entity/audit |
| **AUTHZ-R05** | `X-User-ID` cannot impersonate another user | CP1 (PASS) | `test_characterization_jwt_user_id_mismatch_returns_403` | Status code == 403 "User mismatch" |
| **AUTHZ-R06** | `X-Role` or header fallback cannot elevate role | CP1, CP2 | `test_characterization_require_roles_fallback_unreachable_in_normal_traffic` | Fail-closed 401 |
| **AUTHZ-R07** | Cross-tenant authenticated principal cannot operate | CP1 (PASS) | `test_characterization_jwt_org_id_mismatch_returns_403` | Status code == 403 "Organization mismatch" |
| **AUTHZ-R08** | Machine/webhook endpoints retain dedicated auth | CP1, CP4 | `test_http_handshake_and_auth_before_payload`, `test_hermes_machine_credential_rejects_missing_or_invalid_tokens` | Webhooks and M2M pass green |
| **AUTHZ-R09** | 403 returned for authenticated but unauthorized role | CP1, CP3 | `test_characterization_*_viewer_denied_403` | Status code == 403 |
| **AUTHZ-R10** | 401 returned for unauthenticated request | CP1 (PASS) | `test_characterization_missing_or_invalid_jwt_returns_401` | Status code == 401 |
| **AUTHZ-R11** | Authorized ADMIN/MANAGER/OPERATOR workflows preserved | CP3 | `test_authorized_role_workflows_compatible` | Status code 200/201/202 |
| **AUTHZ-R12** | Audit attribution receives verified actor | CP2 | `test_audit_log_actor_attribution` | Audit log has real user UUID |
| **AUTHZ-R13** | Zero accounting, tax, or financial data changes | CP4 | Full backend test suite | 555+ existing tests pass |
| **AUTHZ-R14** | Route-level automated regression coverage | CP1, CP4 | `test_authz001_role_enforcement.py` | 100% route test coverage |
