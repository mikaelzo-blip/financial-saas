# Feature Specification: Tenant Foreign-Reference Ownership Hardening

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References
**Feature Branch**: `hermes/fin-p1-105-tenant-reference-hardening`
**Status**: SPECIFICATION & CHECKPOINT PLANNING
**Priority**: P1 (Security & Multi-Tenancy Hardening)
**Authority**: Constitution v2.0.0, Financial Concept v1, AGENTS.md, Security Audit 2026-09-09/2026-09-12
**Baseline Commit**: `c15548abc8e1b0678b5ec14a96e48b2e8b68fc48`

---

## 1. Purpose & Scope

This specification hardens multi-tenant isolation across all service-layer mutation paths where callers supply foreign UUID references. It eliminates cross-tenant persistence vulnerabilities identified in audit item **FIN-P1-105** and fortifies internal service contracts against unauthorized cross-tenant data linkage.

### The 7 Confirmed Vulnerable Fields
1. **`Project.pic_user_id`** (create and update) referencing `User`.
2. **`FixedAsset.vendor_id`** (create) referencing `Counterparty`.
3. **`FixedAsset.document_id`** (create) referencing `Document`.
4. **`Settlement.transaction_id`** (create) referencing `Transaction`.
5. **`BankReconciliation.journal_line_id`** (manual match) referencing `JournalLine` via `JournalEntry`.
6. **`BankReconciliation.money_movement_id`** (manual match) referencing `MoneyMovement`.
7. **`BankReconciliation.transaction_id`** (manual match) referencing `Transaction`.

### Defense-in-Depth Item (Separately Classified)
* **`ProjectBudget` service methods**: `ProjectService.get_project_budgets` and `ProjectService.add_or_update_project_budget` do not accept `organization_id` at the service boundary (although the HTTP router currently protects the API entrypoint). These methods are hardened to enforce tenant isolation internally.

---

## 2. Security Invariants

The implementation must strictly enforce the following security invariants:

- **TENANT-R01 (Project PIC Tenant Containment)**: Tenant A MUST NOT persist a reference to Tenant B `User` via `Project.pic_user_id` during project creation or metadata update.
- **TENANT-R02 (Fixed Asset Vendor Containment)**: Tenant A MUST NOT persist a reference to Tenant B `Counterparty` via `FixedAsset.vendor_id`. The check mandates `Counterparty.organization_id == organization_id`.
- **TENANT-R03 (Fixed Asset Document Containment)**: Tenant A MUST NOT persist a reference to Tenant B `Document` via `FixedAsset.document_id`.
- **TENANT-R04 (Settlement Transaction Containment)**: Tenant A MUST NOT persist a `Settlement` referencing Tenant B `Transaction` via `Settlement.transaction_id`.
- **TENANT-R05 (Bank Recon JournalLine Containment)**: Tenant A MUST NOT reconcile a statement line against Tenant B `JournalLine`. Because `JournalLine` lacks an `organization_id` column, ownership MUST be verified through `JournalLine.journal_entry_id == JournalEntry.id` where `JournalEntry.organization_id == organization_id`.
- **TENANT-R06 (Bank Recon MoneyMovement Containment)**: Tenant A MUST NOT reconcile a statement line against Tenant B `MoneyMovement`.
- **TENANT-R07 (Bank Recon Transaction Containment)**: Tenant A MUST NOT reconcile a statement line against Tenant B `Transaction`.
- **TENANT-R08 (Anti-Oracle / Fail-Closed Uniformity)**: Foreign-tenant UUID references and non-existent UUID references MUST fail closed with HTTP 404 `EntityNotFoundException` with identical error payloads, preventing IDOR enumeration or existence leakage.
- **TENANT-R09 (Positive Same-Tenant Compatibility)**: Valid same-tenant references across all 7 fields MUST continue to be accepted and linked without regression.
- **TENANT-R10 (AUTHZ-001 Invariant Preservation)**: Existing role-based authorization from AUTHZ-001 remains intact. Authorized roles (`ADMIN`, `MANAGER`, `OPERATOR`) attempting cross-tenant references receive 404, while unauthorized roles (`VIEWER`) receive 403 before reaching service logic.
- **TENANT-R11 (Zero Accounting Rule Alteration)**: No double-entry posting rules, journal balances, debit/credit logic, or financial reporting logic may be changed.
- **TENANT-R12 (Zero Schema Migration)**: No database schema migrations or composite foreign key redesigns may be introduced in this remediation.
- **TENANT-R13 (Strict Atomicity & Rollback)**: If any supplied foreign UUID fails tenant validation, the operation MUST halt before partial persistence occurs; zero rows, sequence numbers, or audit events survive.
- **TENANT-R14 (Project Budget Service Hardening)**: Internal service methods for `ProjectBudget` MUST enforce tenant ownership defense-in-depth by requiring `organization_id` and asserting project tenancy.

---

## 3. Detailed User Stories & Behavior Scenarios

### Scenario 1: Project PIC Assignment (Create & Update)
* **Given** an authenticated Tenant A Manager (`org_a`):
  * When creating a project with `pic_user_id = user_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("User", user_b.id)` -> HTTP 404. No project code is allocated and no project record is created.
  * When updating an existing project with `pic_user_id = user_b.id`, the service raises `EntityNotFoundException("User", user_b.id)` -> HTTP 404. Project remains unchanged.
  * When creating or updating a project with `pic_user_id = user_a.id` (belonging to `org_a`), the operation succeeds (201/200).
  * When `pic_user_id` is omitted or `None`, the operation succeeds with `pic_user_id = None`.

### Scenario 2: Fixed Asset Registration (Vendor & Document)
* **Given** an authenticated Tenant A Operator (`org_a`):
  * When creating an asset with `vendor_id = cp_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("Counterparty", cp_b.id)` -> HTTP 404.
  * When creating an asset with `document_id = doc_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("Document", doc_b.id)` -> HTTP 404.
  * When creating an asset with valid `org_a` vendor and document, the asset is persisted (201 Created).
  * When `vendor_id` and `document_id` are omitted or `None`, the asset is persisted with null references.

### Scenario 3: Money Movement Settlement Linking
* **Given** an authenticated Tenant A Operator (`org_a`):
  * When creating a money movement with a settlement referencing `transaction_id = tx_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("Transaction", tx_b.id)` -> HTTP 404.
  * Zero money movements, settlements, or settlement allocations are written to the database.
  * When creating a money movement with a settlement referencing `transaction_id = tx_a.id` (belonging to `org_a`), the movement and settlement persist successfully (201 Created).

### Scenario 4: Manual Bank Statement Reconciliation
* **Given** an authenticated Tenant A Operator (`org_a`):
  * When calling `/reconcile` with `journal_line_id = jl_b.id` (belonging to `org_b` via its journal entry), the service raises `EntityNotFoundException("JournalLine", jl_b.id)` -> HTTP 404.
  * When calling `/reconcile` with `money_movement_id = mm_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("MoneyMovement", mm_b.id)` -> HTTP 404.
  * When calling `/reconcile` with `transaction_id = tx_b.id` (belonging to `org_b`), the service raises `EntityNotFoundException("Transaction", tx_b.id)` -> HTTP 404.
  * In all failure cases, the statement line remains `UNMATCHED_BANK`, and no `BankReconciliation` row is created.
  * When calling `/reconcile` with valid `org_a` references, the reconciliation row is created and the statement line transitions to `MATCHED`.

### Scenario 5: Project Budget Service Defense-in-Depth
* **Given** an internal service or worker caller:
  * When calling `get_project_budgets(org_a.id, proj_b.id)` or `add_or_update_project_budget(org_a.id, proj_b.id, ...)`, the service raises `EntityNotFoundException("Project", proj_b.id)` -> HTTP 404.
  * When calling with valid `org_a` project, budgets are listed or upserted cleanly.

---

## 4. Explicitly Out of Scope

The following items are strictly excluded from FIN-P1-105:
- Composite database foreign key schema migrations (e.g. `(organization_id, id)` composite FKs).
- Changes to double-entry accounting rules, debit/credit generation, or financial reports.
- Modification of AUTHZ-001 role assignments or perimeter permission gates.
- Audit logging schema or event structural expansions.
- Mandatory `Counterparty.is_vendor == True` enforcement for Fixed Assets (not supported by domain models).
- Frontend UI alterations or client-side form validation changes.
- Unrelated service refactoring or cleanup.
