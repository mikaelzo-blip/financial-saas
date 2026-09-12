# Data Model & Tenancy Architecture: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References
**Authority**: Constitution v2.0.0, AGENTS.md
**Status**: SPECIFICATION / PLANNING

---

## 1. Relational Topology & Tenancy Resolution

The table below details the relational pathways connecting source entities to referenced target entities, documenting the exact join topology required to establish tenant ownership.

```text
+-------------------+                    +-----------------------+
|   Project         | ---(pic_user_id)-->|   User                |
|   (organization_id|                    |   (organization_id)   |
+-------------------+                    +-----------------------+

+-------------------+                    +-----------------------+
|   FixedAsset      | ---(vendor_id)---->|   Counterparty        |
|   (organization_id|                    |   (organization_id)   |
+-------------------+                    +-----------------------+
        |
        +----------------(document_id)-->+-----------------------+
                                         |   Document            |
                                         |   (organization_id)   |
                                         +-----------------------+

+-------------------+                    +-----------------------+
|   Settlement      | --(transaction_id)->|  Transaction         |
|   (organization_id|                    |   (organization_id)   |
+-------------------+                    +-----------------------+

+-------------------+                    +-----------------------+      +---------------------+
|BankReconciliation | -(journal_line_id)->|  JournalLine          |-(FK)->|  JournalEntry       |
| (organization_id) |                    |  (NO org_id column)   |      |  (organization_id)  |
+-------------------+                    +-----------------------+      +---------------------+
        |
        +------------(money_movement_id)->+-----------------------+
        |                                |  MoneyMovement        |
        |                                |  (organization_id)    |
        |                                +-----------------------+
        |
        +------------(transaction_id)--->+-----------------------+
                                         |  Transaction          |
                                         |  (organization_id)    |
                                         +-----------------------+

+-------------------+                    +-----------------------+
|   ProjectBudget   | ---(project_id)--->|   Project             |
|  (NO org_id col)  |                    |   (organization_id)   |
+-------------------+                    +-----------------------+
```

---

## 2. Model Detail & Traversal Paths

### A. Project & User
* **Source**: `projects.pic_user_id` (UUID, nullable, FK -> `users.id`)
* **Target**: `users.id`
* **Tenant Column**: `users.organization_id`
* **Traversal**: Direct (`users.organization_id == caller_organization_id`).

### B. Fixed Asset & Counterparty
* **Source**: `fixed_assets.vendor_id` (UUID, nullable, FK -> `counterparties.id`)
* **Target**: `counterparties.id`
* **Tenant Column**: `counterparties.organization_id`
* **Domain Check**: `Counterparty.is_vendor` is verified as **NOT** mandated for asset creation; `Counterparty.organization_id == caller_organization_id` is authoritative.
* **Traversal**: Direct (`counterparties.organization_id == caller_organization_id`).

### C. Fixed Asset & Document
* **Source**: `fixed_assets.document_id` (UUID, nullable, FK -> `documents.id`)
* **Target**: `documents.id`
* **Tenant Column**: `documents.organization_id`
* **Traversal**: Direct (`documents.organization_id == caller_organization_id`).

### D. Settlement & Transaction
* **Source**: `settlements.transaction_id` (UUID, nullable, FK -> `transactions.id`)
* **Target**: `transactions.id`
* **Tenant Column**: `transactions.organization_id`
* **Traversal**: Direct (`transactions.organization_id == caller_organization_id`).

### E. Bank Reconciliation & JournalLine
* **Source**: `bank_reconciliations.journal_line_id` (UUID, nullable, FK -> `journal_lines.id`)
* **Target**: `journal_lines.id`
* **Tenant Resolution**: `journal_lines` table **does not store** `organization_id`. Ownership is established exclusively via `journal_entries`:
  ```sql
  SELECT jl.id
  FROM journal_lines jl
  JOIN journal_entries je ON jl.journal_entry_id = je.id
  WHERE jl.id = :journal_line_id
    AND je.organization_id = :organization_id;
  ```
* **Traversal**: 1-hop join through `journal_entries`.

### F. Bank Reconciliation & MoneyMovement
* **Source**: `bank_reconciliations.money_movement_id` (UUID, nullable, FK -> `money_movements.id`)
* **Target**: `money_movements.id`
* **Tenant Column**: `money_movements.organization_id`
* **Traversal**: Direct (`money_movements.organization_id == caller_organization_id`).

### G. Bank Reconciliation & Transaction
* **Source**: `bank_reconciliations.transaction_id` (UUID, nullable, FK -> `transactions.id`)
* **Target**: `transactions.id`
* **Tenant Column**: `transactions.organization_id`
* **Traversal**: Direct (`transactions.organization_id == caller_organization_id`).

### H. Defense-in-Depth: ProjectBudget & Project
* **Source**: `project_budgets.project_id` (UUID, not null, FK -> `projects.id`)
* **Target**: `projects.id`
* **Tenant Resolution**: `project_budgets` does not carry `organization_id`. The owning project defines the tenant boundary (`projects.organization_id == caller_organization_id`).
* **Traversal**: Direct query on parent project via `ProjectService.get_project(organization_id, project_id)`.

---

## 3. Database Schema & Migration Assessment

* **DATABASE MIGRATION REQUIRED**: **NO**
* **Rationale**:
  1. All 7 foreign key columns (`pic_user_id`, `vendor_id`, `document_id`, `transaction_id`, `journal_line_id`, `money_movement_id`, `transaction_id`) already exist in PostgreSQL with appropriate UUID data types and nullable foreign key constraints.
  2. Single-column database foreign keys (e.g. `FOREIGN KEY (vendor_id) REFERENCES counterparties(id)`) enforce referential integrity across the database instance, but do **not** enforce tenant boundaries because UUIDs are globally unique across tenants.
  3. Implementing composite tenant foreign keys (e.g., `FOREIGN KEY (organization_id, vendor_id) REFERENCES counterparties(organization_id, id)`) would require altering multiple primary keys into composite keys and migrating all referencing tables, which is explicitly out of scope for this remediation.
  4. Authoritative tenant isolation is enforced at the application service boundary using tenant-scoped queries.
