# Project Status

- **Last reconciled**: 2026-09-12
- **Current branch**: `hermes/fin-p1-105-tenant-reference-hardening`
- **Base commit**: `c15548abc8e1b0678b5ec14a96e48b2e8b68fc48`
- **Active feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References
- **Active checkpoint**: CP1 — Executable Cross-Tenant RED Regression Suite Only (COMPLETED)
- **CP1 Deliverables**:
  - Spec Kit tracked under `specs/fin-p1-105-tenant-reference-hardening/`
  - Dedicated security regression test suite: `backend/tests/security/test_fin_p1_105_tenant_reference_hardening.py`
  - Test results: 34 tests collected (24 passed, 10 xfailed, 0 unexpected failures)
  - 7 vulnerable reference fields reproduced with executable RED tests (Project PIC create/update, FixedAsset vendor/document, Settlement transaction, BankReconciliation journal_line/money_movement/transaction + mixed atomicity)
  - ProjectBudget characterized as DEFENSE-IN-DEPTH SERVICE CONTRACT GAP (API protected with 404, direct service lacks organization_id)
  - Same-tenant positive controls, nullability controls, nonexistent fail-closed characterization, and AUTHZ-001 regression verified
  - Authoritative PostgreSQL confirmation verified (`test_postgresql_cross_tenant_foreign_key_acceptance_confirmation`) proving global database FKs accept cross-tenant UUIDs without error
  - Zero production code fixes, zero migrations, zero accounting changes, zero frontend changes
- **Scope adherence**: Zero modifications to `backend/src/*` or production database.
- **Next checkpoint**: CP2 — Core Entity Hardening (`ProjectService.create_project`, `ProjectService.update_project`, `FixedAssetService.create_asset`, `ProjectService` budget methods).
