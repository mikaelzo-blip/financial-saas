# Requirements Checklist: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References  
**Status**: CP3 VERIFIED IN WORKTREE — CP4 REMAINS OPEN

---

## 1. Security & Tenancy Invariants Checklist

- [x] **TENANT-R01**: Tenant A cannot persist a reference to Tenant B `User` via `Project.pic_user_id` (create or update).
- [x] **TENANT-R02**: Tenant A cannot persist a reference to Tenant B `Counterparty` via `FixedAsset.vendor_id`.
- [x] **TENANT-R03**: Tenant A cannot persist a reference to Tenant B `Document` via `FixedAsset.document_id`.
- [x] **TENANT-R04**: Tenant A cannot persist a `Settlement` referencing Tenant B `Transaction` via `Settlement.transaction_id`.
- [x] **TENANT-R05**: Tenant A cannot reconcile a bank statement line against Tenant B `JournalLine` via `BankReconciliation.journal_line_id` (ownership resolved via `JournalEntry.organization_id`).
- [x] **TENANT-R06**: Tenant A cannot reconcile a bank statement line against Tenant B `MoneyMovement` via `BankReconciliation.money_movement_id`.
- [x] **TENANT-R07**: Tenant A cannot reconcile a bank statement line against Tenant B `Transaction` via `BankReconciliation.transaction_id`.
- [x] **TENANT-R08**: Foreign-tenant and nonexistent foreign references fail closed uniformly with HTTP 404 `EntityNotFoundException` without existence, owner, or metadata leakage.
- [x] **TENANT-R09**: Valid same-tenant references continue to work seamlessly across all 7 fields (positive controls).
- [x] **TENANT-R10**: Existing RBAC matrices from AUTHZ-001 remain 100% intact (`VIEWER` denied with 403; `ADMIN`, `MANAGER`, `OPERATOR` authorized at route perimeter).
- [x] **TENANT-R11**: Zero changes to double-entry accounting posting rules, debit/credit mechanics, or balance integrity.
- [x] **TENANT-R12**: Zero database schema migrations required (remediation is purely service-layer query scoping).
- [x] **TENANT-R13**: Denied cross-tenant references produce zero partial persistence, zero sequence code burn, and zero surviving database state (strict atomicity).
- [x] **TENANT-R14**: `ProjectBudget` internal service methods enforce tenant isolation defense-in-depth via `organization_id` scoping without broad call-site churn.

---

## 2. Test Coverage & Traceability Checklist

- [x] **CP1 RED Reproduction**: All 7 vulnerable fields have executable RED tests failing at the service validation boundary before any code change.
- [x] **CP1 Positive Controls**: Every vulnerable field has a companion test verifying that valid same-tenant references are accepted.
- [x] **CP1 Nonexistent UUID Controls**: Every vulnerable field has a companion test verifying that nonexistent random UUIDs fail closed with HTTP 404 identical to cross-tenant UUIDs.
- [x] **CP1 Nullable / Omission Controls**: All optional foreign reference fields (`pic_user_id`, `vendor_id`, `document_id`, `journal_line_id`, `money_movement_id`, `transaction_id`) accept `None` / omission.
- [x] **CP2 Core Hardening**: `ProjectService` (`pic_user_id` create/update) and `FixedAssetService` (`vendor_id`, `document_id`), plus defense-in-depth `ProjectBudget` pass GREEN.
- [x] **CP3 Financial Linkage Hardening**: `MoneyMovementService` (`Settlement.transaction_id`) and `BankReconciliationService` (`journal_line_id`, `money_movement_id`, `transaction_id`) pass GREEN. All remaining FIN-P1-105 tenant-reference vulnerabilities: 0.
- [ ] **CP4 Full Regression & Delivery**: All unit, integration, PostgreSQL, and AUTHZ-001 suites pass cleanly with zero failures.
