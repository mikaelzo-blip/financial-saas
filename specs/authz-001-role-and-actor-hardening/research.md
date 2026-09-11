# Research & Architecture Review: Role Enforcement & Actor Attribution Hardening

**Remediation**: AUTHZ-001 & AUTH-002  
**Baseline Commit**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c`  
**Date**: 2026-09-12  

---

## 1. Background & Context

Following the successful completion and verification of `FIN-001` (AR/AP Concurrent Allocation Integrity), security audit review identified two tightly coupled authorization vulnerabilities:
1. **AUTHZ-001**: Role enforcement gaps across human application mutating routes, where 19 endpoints lack `require_roles(...)`, permitting the `VIEWER` role to create and mutate business entities.
2. **AUTH-002**: Caller-controlled actor identity and header role fallback mechanisms that allow request headers (`X-User-ID`, `X-Organization-ID`) to determine identity or role authorization, bypassing cryptographic JWT authentication.

---

## 2. Codebase Archeology & Root Cause Analysis

### 2.1 The `get_current_user_id` Defect (`backend/src/api/deps.py`)
Lines 31–43 of `backend/src/api/deps.py`:
```python
async def get_current_user_id(
    x_user_id: Optional[str] = Header(None, description="Current User UUID")
) -> uuid.UUID:
    """Extracts user ID from request header, falling back to a default system user UUID if omitted."""
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid UUID format for 'X-User-ID' header."
            )
    return uuid.UUID("00000000-0000-0000-0000-000000000001")
```

#### Historical Context:
- Introduced early during Phase 1 prototyping to allow fast developer testing via Curl and Swagger UI without generating signed JWT tokens.
- The dummy UUID `00000000-0000-0000-0000-000000000001` was a temporary seed user.
- Later features introduced JWT authentication (`src/api/auth.py`), but older endpoints in `documents.py` were never updated to consume `require_application_user`.

#### Security Impact:
- Any caller can pass an arbitrary UUID in `X-User-ID`.
- In `backend/src/api/v1/documents.py`:
  - `upload_document` records `created_by=user_id` directly from `get_current_user_id`.
  - `correct_document` checks `await require_reviewer(db, org_id, user_id)`: it checks whether the spoofed `user_id` is an Admin/Manager in the database!
  - `reject_document_candidate` also passes spoofed `user_id` to `require_reviewer` and logs it in `AuditService`.

### 2.2 The Insecure Header Fallback in `require_roles` (`backend/src/api/auth.py`)
Lines 112–128 of `backend/src/api/auth.py`:
```python
def require_roles(*allowed_roles: UserRole):
    ...
    async def role_checker(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User | None = Depends(require_application_user),
    ) -> User:
        if current_user is None:
            user_id_header = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
            org_id_header = request.headers.get("X-Organization-ID") or request.headers.get("x-organization-id")
            if user_id_header and org_id_header:
                try:
                    from uuid import UUID
                    uid = UUID(user_id_header)
                    oid = UUID(org_id_header)
                    current_user = await db.scalar(
                        select(User).where(
                            User.id == uid,
                            User.organization_id == oid,
                            User.is_active.is_(True),
                        )
                    )
                except (ValueError, TypeError):
                    pass
        if not current_user:
            raise HTTPException(401, "Authenticated user required")
        if current_user.role not in roles:
            raise AuthorizationException(...)
        return current_user
```

#### Historical Context:
- Added in commit `ec08387` when `require_roles` was implemented.
- The global test client in `backend/tests/conftest.py:50` configured:
  ```python
  app.dependency_overrides[require_application_user] = lambda: None
  ```
- To allow integration tests to pass without generating real JWT tokens for every test request, lines 112–128 were added to look up the user by `X-User-ID` when `current_user is None`.

#### Security Impact:
- If `require_application_user` is mocked or bypassed, any unauthenticated request can elevate itself to `ADMIN` simply by supplying the Admin's UUID in headers.
- This creates an unauthenticated back-door path that violates fail-closed security principles.

### 2.3 The 19 Mutation Endpoints Lacking Role Enforcement
All routes under `application_router` in `backend/src/api/v1/__init__.py:35` inherit `dependencies=[Depends(require_application_user)]`.
However, `require_application_user` only verifies that:
1. A valid JWT exists;
2. The user is active in the organization;
3. `X-Organization-ID` and `X-User-ID` headers match the token.

It **does not check `user.role`**.
Therefore, a user with `role = UserRole.VIEWER` can freely execute:
1. `POST /api/v1/transactions`
2. `POST /api/v1/projects`
3. `PATCH /api/v1/projects/{id}/status`
4. `POST /api/v1/projects/{id}/budgets`
5. `POST /api/v1/counterparties`
6. `POST /api/v1/coa`
7. `POST /api/v1/payment-accounts`
8. `POST /api/v1/money-movements`
9. `POST /api/v1/bank-reconciliation/imports`
10. `POST /api/v1/bank-reconciliation/imports/{id}/auto-match`
11. `POST /api/v1/bank-reconciliation/reconcile`
12. `POST /api/v1/documents/upload`
13. `POST /api/v1/documents/{id}/retry`
14. `POST /api/v1/documents/{id}/corrections` (guarded by spoofable in-body check)
15. `POST /api/v1/documents/{id}/reject` (guarded by spoofable in-body check)
16. `POST /api/v1/transactions/{id}/review-flags`
17. `POST /api/v1/inbox/capture`
18. `POST /api/v1/inbox/sync`
19. `POST /api/v1/inbox/sessions/{id}/analyze`

---

## 3. Test Fixture Analysis & Remediation Strategy

In `backend/tests/conftest.py`:
```python
@pytest.fixture
async def authenticated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_application()
    ...
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_application_user] = lambda: None
    ...
```

When `require_roles` is cleaned up to remove lines 112–128:
```python
if not current_user:
    raise HTTPException(401, "Authenticated user required")
```
Existing tests relying on `authenticated_client` would fail with `401 Unauthorized` because `current_user` would be `None`.

### Solution:
Harmonize `authenticated_client` and security test fixtures:
- Provide an authenticated user fixture that creates a real seeded `User` with `role = UserRole.ADMIN` (or configurable role).
- In `authenticated_client`, set `app.dependency_overrides[require_application_user]` to return the seeded user principal, OR generate a valid JWT token using `create_access_token` and attach `Authorization: Bearer <token>` to client requests.
- This ensures test suites validate authentic security behavior rather than relying on unauthenticated bypasses.

---

## 4. Machine vs. Human Boundary Isolation

A critical finding of the audit is that machine and webhook endpoints in the repository have dedicated, working security protocols that MUST NOT be touched:
- **Meta WhatsApp Webhook** (`/whatsapp/webhook`): Uses HMAC-SHA256 signature verification (`X-Hub-Signature-256`) and hub challenge handshake.
- **Hermes Machine Intake** (`/hermes/documents/upload`, `/hermes/whatsapp/*`): Uses machine bearer tokens (`WHATSAPP_TENANT_TOKENS`, `HERMES_AGENT_TOKEN`, `WHATSAPP_ADAPTER_TOKEN`).
- **Public Login** (`/auth/login`): Verifies email/password and returns a signed JWT.

These routes are mounted outside `application_router` on `api_router`. Hardening `application_router` and `require_roles` will leave machine and webhook channels completely unaffected.
