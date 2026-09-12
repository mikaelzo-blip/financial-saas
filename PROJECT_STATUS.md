# Project Status

- **Last reconciled**: 2026-09-12
- **Current origin/main baseline**: `c33112c1744e25d12ea1e30b9a133b6931c788b8` (Git verified)
- **Active branch**: `hermes/authz-001-role-and-actor-hardening`
- **Active feature**: AUTHZ-001 — role enforcement and actor hardening.
- **Checkpoint**: CP1 is verified and committed; CP2 and CP3 are not started.
- **CP1 evidence**: Live route inventory has 59 mutating routes: 38 human state mutations, with 17 genuinely vulnerable VIEWER-reachable routes, 4 protected in-body, and 17 declaratively protected. Four POST reporting/query routes are non-mutating; machine, webhook, and public routes remain outside human RBAC scope.
- **CP1 verification**: 10 PASS characterizations cover JWT/header mismatches, missing/invalid authentication, document review, accounting periods, tenant isolation, and latent fallback reachability. The 17 expected RED cases each prove the VIEWER request reaches a controlled mutation boundary before a 403. Existing security/auth/document-review/accounting-period/tenant/machine-webhook tests: 40 passed.
- **Independent review**: No Critical or High finding and no production-scope breach. The single Medium sentinel-noise finding was resolved and reverified.
- **Scope**: No production API/auth code, migration, accounting logic, protected storage, or credentials changed. `ruff` is not installed in the declared backend environment; Python compilation and `git diff --check` pass.
- **Next action**: Stop after CP1. Start CP2 only with an explicit authorized follow-up.
