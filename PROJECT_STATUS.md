# Project Status

- **Last reconciled**: 2026-09-12
- **Current local `main` / `origin/main` baseline**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c` (Git verified)
- **AUTHZ-001 starting source head**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
- **Active branch**: `hermes/authz-001-role-and-actor-hardening`
- **Active feature**: AUTHZ-001 — role enforcement and actor hardening.
- **Checkpoint**: CP3 is verified and committed as `1481a5f6ebcb2eaefe2bafa0c99552a50e1461a6`; CP4 has not started.
- **CP3 route inventory**: 38 human state mutations: 17 formerly vulnerable routes are now declaratively protected, 4 remain protected in-body by approved scope, and 17 were already declaratively protected. Current AUTHZ-001 covered vulnerable count: 0. Four POST reporting/query routes are non-mutating; machine, webhook, and public routes remain outside human RBAC scope.
- **CP2 decisions**: `get_current_user_id` and its sentinel UUID are removed; human document actor identity now comes from the verified JWT-backed `current_user.id`; `require_roles` cannot reconstruct users from headers and fails closed with 401 without a principal. `X-User-ID` is optional compatibility metadata: if supplied it must match the JWT principal or returns 403; it never establishes identity. `X-Organization-ID` remains mandatory and principal-matched.
- **Role-policy boundary**: The 17 Category A routes use `require_roles`: 13 routine operational routes allow ADMIN/MANAGER/OPERATOR; project status/budget allow ADMIN/MANAGER; COA/payment-account creation allow ADMIN only. Document correction/rejection retain in-body `require_reviewer` (ADMIN/MANAGER); accounting-period authorization remains unchanged.
- **CP3 verification**: AUTHZ route suite 103 passed (17 former RED cases, 68 four-role boundary combinations, 401/403, CP2 identity, and in-body characterizations); affected document/auth/period/tenant selection 124 passed; Feature 011/machine-auth subset 21 passed. Python compile, `pip check`, locked production dependency audit, repository-safety, and `git diff --check` passed. Ruff and mypy are not configured in the declared backend environment.
- **CP3 independent review**: bounded read-only review passed with Critical 0, High 0, Medium 0, Low 0; it confirmed exact 17-route coverage, approved policies, side-effect ordering, CP2 identity preservation, tenant preservation, unchanged machine/webhook and protected in-body routes, and no accounting/migration/frontend changes.
- **Scope**: No migration, accounting logic, tenant ownership rule, frontend product code, machine/webhook authentication, protected storage, credentials, or historical data changed.
- **Next action**: Commit only CP3 as `fix(authz-001): enforce roles on application mutations (CP3)`, then stop. Do not push, open a PR, or begin CP4.
