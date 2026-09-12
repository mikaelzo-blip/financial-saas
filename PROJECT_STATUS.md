# Project Status

- **Last reconciled**: 2026-09-12
- **Current local `main` / `origin/main` baseline**: `3d516096cc0085eb3e5e7273f6be57ec5c7d876c` (Git verified)
- **AUTHZ-001 starting source head**: `c33112c1744e25d12ea1e30b9a133b6931c788b8`
- **Active branch**: `hermes/authz-001-role-and-actor-hardening`
- **Active feature**: AUTHZ-001 — role enforcement and actor hardening.
- **Checkpoint**: CP2 is verified and committed in this checkpoint; independent review passed. CP3 has not started.
- **CP1 route inventory (unchanged)**: 38 human state mutations: 17 genuinely vulnerable VIEWER-reachable routes, 4 protected in-body, and 17 declaratively protected. Four POST reporting/query routes are non-mutating; machine, webhook, and public routes remain outside human RBAC scope.
- **CP2 decisions**: `get_current_user_id` and its sentinel UUID are removed; human document actor identity now comes from the verified JWT-backed `current_user.id`; `require_roles` cannot reconstruct users from headers and fails closed with 401 without a principal. `X-User-ID` is optional compatibility metadata: if supplied it must match the JWT principal or returns 403; it never establishes identity. `X-Organization-ID` remains mandatory and principal-matched.
- **Role-policy boundary**: Document correction/rejection retain in-body `require_reviewer` (ADMIN/MANAGER allowed; OPERATOR/VIEWER denied). CP2 added no declarative role guards to the 17 vulnerable routes; their 17 CP1 RED cases remain expected failures for CP3.
- **CP2 verification**: identity/protected subset 18 passed; CP1 vulnerable matrix 17 failed as expected; document/auth/period/tenant/machine/accounting regression selection 34 passed; Python compile and `git diff --check` passed. Ruff is unavailable in the declared backend environment.
- **CP2 independent review**: bounded read-only review passed with Critical 0, High 0, Medium 0, Low 0; it confirmed no machine/webhook, accounting, migration, frontend product, or CP3 role-policy change.
- **Scope**: No migration, accounting logic, tenant ownership rule, frontend product code, machine/webhook authentication, protected storage, or credentials changed.
- **Next action**: Run the final CP2 repository gates, commit only CP2 as `fix(authz-001): bind application actors to verified principals (CP2)`, and stop. Do not begin CP3, push, or open a PR.
