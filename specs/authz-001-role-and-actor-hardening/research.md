# Research & Architecture Review: Role Enforcement & Actor Attribution Hardening

**Remediation**: AUTHZ-001 (Reconciled Baseline)
**Baseline Commit**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
**Date**: 2026-09-12

---

## 1. Background & Reconciled Context

Following the merge of `FIN-001` (AR/AP Concurrent Allocation Integrity), security audit review investigated role enforcement gaps and caller-controlled actor identity mechanisms.

### Crucial Baseline Reconciliation
An empirical re-audit of the live codebase on `origin/main` (`c33112c1744e25d12ea1e30b9a133b6931c788b8`) demonstrated that the previously asserted **AUTH-002 privilege escalation exploit** ("low-privilege JWT + privileged `X-User-ID` can escalate document reviewer permissions") is **NOT REPRODUCIBLE** and is formally **REJECTED**.

The actual security posture of the live application is:
1. **AUTHZ-001 (CRITICAL P1)**: Exactly **17 human application mutation endpoints** completely lack role checks (`require_roles` or in-body checks). An authenticated user with the `VIEWER` role can mutate transactions, counterparties, projects, money movements, bank reconciliation imports/matches, COA accounts, payment accounts, and review flags.
2. **AUTH-ID-001 (DEFENSE-IN-DEPTH CLEANUP)**: `backend/src/api/deps.py:31-43` contains `get_current_user_id`, which extracts caller identity from `X-User-ID` with a dummy fallback UUID. In production, `application_router` enforces `require_application_user`, which validates `X-User-ID == token.sub`, preventing cross-user spoofing. However, this helper remains an anti-pattern that must be removed.
3. **AUTH-ID-002 (LATENT UNSAFE FALLBACK / DEFENSE-IN-DEPTH)**: `backend/src/api/auth.py:112-128` in `require_roles` contains a header-based user lookup that activates only when `current_user is None`. In real mounted application traffic without dependency overrides, `require_application_user` is always executed first and never yields `None`. The fallback is only reachable under test fixture dependency overrides (`conftest.py:50`). It must be eliminated to prevent latent bypass vulnerabilities.
4. **DOCUMENT REVIEW ROUTES (PROTECTED IN-BODY)**: `POST /documents/{id}/corrections` and `POST /documents/{id}/reject` in `documents.py` call `await require_reviewer(db, org_id, user_id)` which enforces `User.role.in_([UserRole.ADMIN, UserRole.MANAGER])`. An authenticated `VIEWER` is denied with `403 Forbidden` (`Manager or administrator review permission required`). These routes are NOT in the vulnerable RED set.

---

## 2. Empirical Verification from Live Source

### 2.1 Upstream JWT and Header Validation (`backend/src/api/auth.py`)
Lines 40–64 of `backend/src/api/auth.py`:
```python
async def authenticated_user(request: Request, db: AsyncSession) -> User:
    authorization = request.headers.get("Authorization", "")
    payload = decode_access_token(authorization[7:]) if authorization.startswith("Bearer ") else None
    if not payload:
        raise HTTPException(401, "Authenticated user required")
    try:
        from uuid import UUID
        user_id = UUID(payload["sub"])
        organization_id = UUID(payload["organization_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(401, "Authenticated user required") from None
    user = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    )
    if not user:
        raise HTTPException(401, "Authenticated user required")
    if request.headers.get("X-Organization-ID") != str(user.organization_id):
        raise HTTPException(403, "Organization mismatch")
    if request.headers.get("X-User-ID") != str(user.id):
        raise HTTPException(403, "User mismatch")
    return user
```

#### Observations:
- In `backend/src/api/v1/__init__.py:35`, `application_router = APIRouter(dependencies=[Depends(require_application_user)])`.
- Every route mounted under `application_router` requires `require_application_user -> authenticated_user`.
- If a request supplies a valid low-privilege JWT (`VIEWER`) but attempts to spoof an Admin's ID in `X-User-ID`, line 62 immediately triggers `raise HTTPException(403, "User mismatch")`.
- If a request supplies a mismatched `X-Organization-ID`, line 60 triggers `raise HTTPException(403, "Organization mismatch")`.
- Therefore, caller-controlled header spoofing cannot elevate permissions in the live application stack.

### 2.2 Re-Audit of Document Review Endpoints (`backend/src/api/v1/documents.py`)
Lines 46–51, 125, 274 of `backend/src/api/v1/documents.py`:
```python
async def require_reviewer(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(and_(User.id == user_id, User.organization_id == org_id,
        User.role.in_([UserRole.ADMIN, UserRole.MANAGER]))))
    if not user:
        raise HTTPException(status_code=403, detail="Manager or administrator review permission required")
    return user
```

When an authenticated `VIEWER` issues `POST /documents/{id}/corrections` or `POST /documents/{id}/reject`:
1. `require_application_user` validates the JWT and asserts `X-User-ID == viewer.id`.
2. `get_current_user_id` extracts `X-User-ID` (which must equal `viewer.id`).
3. `require_reviewer` queries `User.id == viewer.id` with `User.role.in_([ADMIN, MANAGER])`.
4. The query returns `None` and raises `HTTPException(403, "Manager or administrator review permission required")`.
5. Conclusion: `VIEWER` is **ALREADY DENIED BEFORE MUTATION**. The routes are **CURRENTLY PROTECTED VIA IN-BODY AUTHORIZATION**.

### 2.3 Reachability of `require_roles` Fallback
In `backend/src/api/auth.py:112-128`:
```python
if current_user is None:
    # looks up user via X-User-ID and X-Organization-ID
```
Because `current_user: User | None = Depends(require_application_user)`, and `require_application_user` raises 401/403 or returns a valid `User`, `current_user` is **never None** in mounted application routes.
The fallback block is only entered if an external fixture explicitly overrides `require_application_user` to return `None` (as in `tests/conftest.py:50`).
Thus, this is a **latent defense-in-depth cleanup**, not a production privilege escalation vulnerability.

---

## 3. Route Inventory & Classification

Across all 116 routes in the FastAPI application:
- **Total Mutating Routes (POST, PUT, PATCH, DELETE)**: 59 routes
- **Public Auth Endpoints**: 1 (`POST /auth/login`)
- **Verified Webhook Endpoints**: 2 (`/whatsapp/webhook`, `/integrations/whatsapp/webhook`)
- **Machine Service Endpoints**: 14 (Hermes intake & WhatsApp state routes)
- **Human Application Endpoints**: 42 routes

### Classification of the 42 Human Application Endpoints

| Category | Count | Status & Invariant | Endpoints |
|---|:---:|---|---|
| **A. ACTUALLY VULNERABLE** | **17** | `VIEWER` passes auth and reaches mutation; no role check exists. | 1. `POST /transactions`<br>2. `POST /projects`<br>3. `PATCH /projects/{id}/status`<br>4. `POST /projects/{id}/budgets`<br>5. `POST /counterparties`<br>6. `POST /coa`<br>7. `POST /payment-accounts`<br>8. `POST /money-movements`<br>9. `POST /bank-reconciliation/imports`<br>10. `POST /bank-reconciliation/imports/{id}/auto-match`<br>11. `POST /bank-reconciliation/reconcile`<br>12. `POST /documents/upload`<br>13. `POST /documents/{id}/retry`<br>14. `POST /transactions/{id}/review-flags`<br>15. `POST /inbox/capture`<br>16. `POST /inbox/sync`<br>17. `POST /inbox/sessions/{id}/analyze` |
| **B. PROTECTED IN-BODY** | **4** | `VIEWER` denied with `403` via manual checks inside handler body. | 1. `POST /documents/{id}/corrections` (`require_reviewer`)<br>2. `POST /documents/{id}/reject` (`require_reviewer`)<br>3. `POST /periods` (`current_user.role not in (ADMIN, MANAGER)`)<br>4. `PATCH /periods/{id}/status` (`current_user.role not in (ADMIN, MANAGER)`) |
| **C. DECLARATIVELY PROTECTED** | **17** | `VIEWER` denied with `403` via `require_roles` or `require_whatsapp_admin`. | 1. `POST /transactions/{id}/post`<br>2. `POST /transactions/{id}/approve`<br>3. `POST /transactions/opening-balances`<br>4. `POST /transactions/{id}/reverse`<br>5. `POST /transactions/{id}/review-flags/{flag_id}/resolve`<br>6. `POST /vendor-payments`<br>7. `POST /customer-invoices/retention-releases`<br>8. `POST /customer-payments`<br>9. `POST /fixed-assets`<br>10. `PATCH /fixed-assets/{id}`<br>11. `PUT /fixed-assets/{id}`<br>12. `POST /fixed-assets/{id}/depreciate`<br>13. `POST /fixed-assets/depreciate-batch`<br>14. `POST /fixed-assets/{id}/dispose`<br>15. `POST /documents/{id}/approve`<br>16. `POST /integrations/whatsapp/senders`<br>17. `DELETE /integrations/whatsapp/senders/{id}` |
| **D. REPORTING / QUERY (NON-MUTATING)** | **4** | Read-only calculation or user-scoped Q&A chat. | 1. `POST /reports/consultant-reconciliation/compare`<br>2. `POST /reports/consultant-reconciliation/reconcile-verified/{year}`<br>3. `POST /reports/consultant-reconciliation/upload`<br>4. `POST /insights/query` |

---

## 4. Priority Assessment vs FIN-P1-105

- **FIN-P1-105**: Tenant foreign-reference validation prevents cross-tenant foreign key references during creation/update of certain entities.
- **AUTHZ-001**: 17 distinct mutation surfaces across core financial (transactions, counterparties, chart of accounts, payment accounts, money movements, bank reconciliation) and operational entities (projects, budgets, documents, inbox sync) allow an authenticated `VIEWER` to create and mutate company state.
- **Verdict**: AUTHZ-001 decisively **REMAINS RANK #1**. It addresses an urgent core authorization perimeter failure across 17 live business mutation endpoints.
