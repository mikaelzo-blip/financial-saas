# Research & Architectural Audit: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References
**Authority**: Constitution v2.0.0, AGENTS.md, Security Audit 2026-09-09/2026-09-12
**Status**: COMPLETE / VERIFIED

---

## 1. Context & Problem Statement

In `mikaelzo-blip/financial-saas`, multi-tenancy is modeled with an `organization_id` on top-level business entities (`organizations`, `projects`, `counterparties`, `documents`, `transactions`, `money_movements`, `journal_entries`, `fixed_assets`).

However, the underlying relational database uses standard single-column UUID foreign keys (e.g. `FOREIGN KEY (vendor_id) REFERENCES counterparties(id)`). Because primary keys are globally unique random UUIDs, PostgreSQL successfully permits foreign key references to link records across distinct organizations unless the application service explicitly restricts the query with `organization_id == caller_organization_id`.

An exhaustive audit of mutation entrypoints identified **7 vulnerable foreign-reference fields** where caller-supplied UUIDs bypass tenant validation, allowing cross-tenant data linkages. Additionally, one service-layer defense-in-depth boundary (`ProjectBudget`) was analyzed.

---

## 2. In-Depth Analysis of the 7 Vulnerable Fields

### 1. `Project.pic_user_id`
* **Entrypoints**:
  * `ProjectService.create_project` (`backend/src/services/project_service.py:67–106`)
  * `ProjectService.update_project` (`backend/src/services/project_service.py:139–163`)
* **Current State**:
  * In `create_project`, `data.customer_id` is queried against `Counterparty.organization_id == organization_id`. But `data.pic_user_id` is assigned directly to the `Project` model without any query against the `users` table.
  * In `update_project`, `data.pic_user_id` is directly assigned to `project.pic_user_id` without query.
  * Clearing `pic_user_id` by passing `None` or leaving it unset is valid.
* **Risk**: Tenant A can assign Tenant B users as project managers (PIC), exposing project assignments across tenants in reports and dashboards.

### 2. `FixedAsset.vendor_id`
* **Entrypoint**: `FixedAssetService.create_asset` (`backend/src/services/fixed_asset_service.py:143–225`)
* **Current State**:
  * `data.vendor_id` is assigned directly to `FixedAsset.vendor_id` (line 196) without checking `counterparties`.
  * `FixedAssetUpdate` does not modify `vendor_id`.
* **Domain Semantics Check (`is_vendor`)**:
  * We audited whether `Counterparty.is_vendor == True` is expected.
  * In `TransactionService`, `is_vendor` is enforced only for `PAY_VENDOR_BILL` transactions; general counterparty links do not enforce `is_vendor`.
  * In `FixedAsset` domain, assets may be acquired from general suppliers or mixed counterparties.
  * **Finding**: `Counterparty.organization_id == organization_id` is strictly required. Mandating `is_vendor == True` is **NOT** supported by existing domain models and would invent new business policy.
* **Risk**: Tenant A can reference Tenant B's counterparties, cross-contaminating vendor registries.

### 3. `FixedAsset.document_id`
* **Entrypoint**: `FixedAssetService.create_asset` (`backend/src/services/fixed_asset_service.py:143–225`)
* **Current State**:
  * `data.document_id` is assigned directly to `FixedAsset.document_id` (line 197) without querying `documents`.
* **Risk**: Tenant A can attach Tenant B's confidential uploaded documents (invoices, receipts, SPKs) to its own assets.

### 4. `Settlement.transaction_id`
* **Entrypoint**: `MoneyMovementService.create_money_movement` (`backend/src/services/money_movement_service.py:239–338`)
* **Current State**:
  * Lines 273–297 validate `alloc.project_id` and `alloc.invoice_id` within allocations.
  * However, lines 313–324 instantiate `Settlement` with `transaction_id=s_data.transaction_id` with zero validation.
* **Risk**: A cash movement in Tenant A can settle a transaction belonging to Tenant B, breaking AR/AP ledger integrity and cross-tenant reconciliation.

### 5. `BankReconciliation.journal_line_id`
* **Entrypoint**: `BankReconciliationService.match_manual` (`backend/src/services/bank_reconciliation_service.py:248–281`)
* **Current State**:
  * `req.journal_line_id` is assigned directly to `BankReconciliation` (line 269) without verification.
  * **Model Traversal Finding**: `JournalLine` has **no direct `organization_id` column** in `backend/src/models/journal.py`. It links to `JournalEntry` via `journal_entry_id`.
  * **Query Strategy**: Must query `JournalLine` joining `JournalEntry` on `journal_entry_id == JournalEntry.id` where `JournalEntry.organization_id == organization_id`.
* **Risk**: Tenant A can reconcile bank transactions against Tenant B's general ledger journal entries.

### 6. `BankReconciliation.money_movement_id`
* **Entrypoint**: `BankReconciliationService.match_manual` (`backend/src/services/bank_reconciliation_service.py:248–281`)
* **Current State**:
  * `req.money_movement_id` is assigned directly to `BankReconciliation` (line 270) without checking `money_movements.organization_id`.
* **Risk**: Tenant A can reconcile against Tenant B's cash movements.

### 7. `BankReconciliation.transaction_id`
* **Entrypoint**: `BankReconciliationService.match_manual` (`backend/src/services/bank_reconciliation_service.py:248–281`)
* **Current State**:
  * `req.transaction_id` is assigned directly to `BankReconciliation` (line 271) without checking `transactions.organization_id`.
* **Risk**: Tenant A can link bank statement lines directly to Tenant B's business transactions.

---

## 3. Defense-in-Depth Service Hardening: Project Budget

* **Methods**:
  * `ProjectService.get_project_budgets(self, project_id: uuid.UUID)`
  * `ProjectService.add_or_update_project_budget(self, project_id: uuid.UUID, data: ProjectBudgetCreate)`
* **Current Security Boundary**:
  * `backend/src/api/v1/projects.py` (lines 107 and 127) calls `await service.get_project(org_id, project_id)` before invoking the service methods.
  * Therefore, the **HTTP API is already protected** against cross-tenant attacks.
* **Service-Layer Hardening**:
  * Direct invocation of `get_project_budgets` or `add_or_update_project_budget` by internal background workers or other services would lack tenant scoping.
  * Call-site audit revealed only **2 production call sites** in `api/v1/projects.py` and **1 integration test call site** in `test_project_service.py`.
  * **Decision**: Add `organization_id: uuid.UUID` to both methods and call `await self.get_project(organization_id, project_id)` inside the service. This is small, safe, has near-zero churn, and closes internal service gaps in CP2.

---

## 4. Error Semantics & Anti-Oracle Defense

### The Threat
If an API distinguishes between a nonexistent ID (`404 Not Found`) and a foreign tenant ID (`403 Forbidden` or `422 Unprocessable Content`), an attacker can brute-force UUIDs to discover which IDs exist on the platform.

### Uniform 404 Standard
All foreign entity queries use:
```python
if not entity:
    raise EntityNotFoundException("<EntityName>", identifier)
```
This produces an identical `404 Not Found` response with identical payload structure whether the UUID does not exist at all or belongs to another tenant. Zero metadata or existence information is disclosed.

---

## 5. Atomicity & Sequence Burn Prevention

In financial systems, sequence numbers (e.g. `PRJ-2026-001`, `AST-001`, `MM-2026-000001`, `SET-000001`) should not be burned or leaked on failed validation.

- In `ProjectService.create_project`, `data.pic_user_id` must be validated **before** calling `self.generate_project_code(...)`.
- In `MoneyMovementService.create_money_movement`, all settlements and allocations must be pre-validated **before** calling `_generate_movement_code` or adding `movement` to the session.
- In `FixedAssetService.create_asset`, `vendor_id` and `document_id` must be validated **before** session flush.
- In `BankReconciliationService.match_manual`, all optional references (`journal_line_id`, `money_movement_id`, `transaction_id`) must be validated **before** updating `statement_line.reconciliation_status` or creating the `BankReconciliation` row.

---

## 6. Test Runner & Database Strategy

- **Local Execution**: The project test suite executes cleanly using SQLite in-memory for unit and service integration tests (`pytest tests/unit tests/integration`).
- **PostgreSQL Integration Verification**: Real PostgreSQL tests (`test_live_postgresql_schema.py`) verify constraint compatibility and schema sanity.
- No new PostgreSQL migrations are needed.
