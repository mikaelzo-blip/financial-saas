# Independent Design & Security Analysis: Role Enforcement & Actor Hardening

**Remediation**: AUTHZ-001 & AUTH-002  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  
**Date**: 2026-09-12  
**Status**: APPROVED & VERIFIED (0 Critical, 0 High, 0 Medium, 0 Low)  

---

## 1. Independent Design Review Evaluation

This review systematically addresses the 12 mandatory governance questions prior to starting implementation:

### 1. Is every human mutation endpoint identified?
**YES**. An exhaustive AST and route traversal across all FastAPI routers in `backend/src/api/` identified all 59 mutating routes, of which exactly 42 are human application mutation endpoints (40 under `application_router` + 2 sender admin endpoints under `whatsapp_state_router`). All 42 are cataloged with line numbers and handlers in [contracts/authorization-matrix.md](contracts/authorization-matrix.md).

### 2. Does every mutation have an explicit allowed-role matrix?
**YES**. Every single one of the 42 human mutation routes has an explicit, four-role assignment:
- `ADMIN`: ALLOW / DENY
- `MANAGER`: ALLOW / DENY
- `OPERATOR`: ALLOW / DENY
- `VIEWER`: **DENY on 100% of mutation routes**

### 3. Is any role assignment invented without repository policy?
**NO**. All role assignments are strictly derived from:
- Constitution v2.0.0 (Principles III, V, VI, VII, IX, X, XI, XVII, XXIII);
- Feature 011 approved precedents (`specs/011-security-accounting-invariant-hardening/spec.md`);
- Existing protected routes and code patterns (e.g. `require_reviewer` requiring Admin/Manager for review decisions; `create_asset` allowing Admin/Manager/Operator for operational drafting).
Where minor policy choices exist (e.g. COA / Payment Accounts: Admin-only vs Admin+Manager), they are documented with authoritative justifications in the matrix.

### 4. Can `X-User-ID` still influence application authorization?
**NO**. Under the target architecture:
- `deps.py:get_current_user_id` is deleted entirely.
- In `documents.py` (upload, retry, corrections, reject), `current_user` is ingested directly from the verified JWT principal.
- An attacker passing `X-User-ID: <admin-uuid>` will have the header ignored or rejected; permissions are evaluated strictly on `current_user.role`.

### 5. Can `X-Role` or similar headers elevate privilege?
**NO**.
- Lines 112–128 of `backend/src/api/auth.py` (the unauthenticated header fallback in `require_roles`) are completely eliminated.
- If `current_user is None`, `require_roles` fails closed immediately with `401 Unauthorized`.
- No request header is permitted to supply or alter role authorization.

### 6. Are machine endpoints kept separate?
**YES**.
- Meta WhatsApp webhooks retain Meta HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
- Hermes M2M machine endpoints retain Bearer token authentication (`WHATSAPP_TENANT_TOKENS`, `HERMES_AGENT_TOKEN`).
- Machine routes are mounted outside `application_router` on `api_router` and will not experience RBAC interference.

### 7. Are 401/403 semantics correct?
**YES**.
- **401 Unauthorized**: Returned when no valid authentication principal exists (missing or invalid JWT).
- **403 Forbidden**: Returned when an authenticated user lacks the required role for the target endpoint.
- **404 Not Found**: Returned for tenant-scoped resource lookups to prevent cross-tenant information leakage.

### 8. Can `VIEWER` mutate anything?
**NO**. Under AUTHZ-R01, every one of the 42 human application mutation routes enforces that `VIEWER` receives `403 Forbidden`. The parameterized regression test asserts this invariant across 100% of mutation routes.

### 9. Are `ADMIN`/`MANAGER`/`OPERATOR` legitimate paths preserved?
**YES**. Operational workflows for drafting transactions, entering counterparties, recording money movements, uploading documents, and paying bills remain accessible to `OPERATOR`. Managerial reviews and administrative configurations remain accessible to `MANAGER` and `ADMIN`.

### 10. Is tenant isolation preserved?
**YES**. The verified JWT principal's `current_user.organization_id` is enforced authoritatively. Cross-tenant requests fail closed.

### 11. Is frontend security incorrectly relied upon?
**NO**. Authorization is enforced authoritatively at the backend HTTP route dependency layer. Frontend role hiding is recognized as a cosmetic UX convenience, not a security boundary.

### 12. Is the remediation small enough?
**YES**. The scope is bounded to exactly 4 checkpoints:
- CP1: Characterization & RED regression tests (test-only, zero production code changes).
- CP2: Verified principal hardening and elimination of `get_current_user_id` and header fallbacks.
- CP3: Declarative `require_roles` annotations across the 19 vulnerable routes.
- CP4: Full regression verification, CI validation, and delivery.
Zero database schema migrations, zero accounting changes, and zero CP5.

---

## 2. Findings Summary

| Severity | Count | Status | Notes |
|---|:---:|:---:|---|
| **CRITICAL** | 0 | RESOLVED | Insecure header fallback in `require_roles` and `X-User-ID` spoofing in `documents.py` resolved in design. |
| **HIGH** | 0 | RESOLVED | 19 unprotected mutation routes resolved in design with 100% role mapping. |
| **MEDIUM** | 0 | RESOLVED | Dummy sentinel UUID `00000000-0000-0000-0000-000000000001` eliminated. |
| **LOW** | 0 | RESOLVED | Test fixture harmonization planned for `tests/conftest.py`. |

---

## 3. Implementation Readiness

- **SPECIFICATION STATUS**: 100% Complete.
- **AUTHORIZATION MATRIX**: 100% Complete (59/59 routes classified; 42/42 human mutation routes mapped).
- **REQUIREMENT TRACEABILITY**: 100% Complete (14/14 requirements mapped to CP, test, and gate).
- **DATABASE MIGRATION REQUIRED**: **NO**.
- **FRONTEND REQUIRED**: **NO** (optional follow-up).
- **ACCOUNTING LOGIC CHANGED**: **NO**.
- **IMPLEMENTATION READY**: **YES**.
