# Tenant Foreign-Reference Ownership Contract: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References  
**Authority**: Constitution v2.0.0, AGENTS.md, Security Audit 2026-09-09/2026-09-12  
**Status**: DRAFT / SPECIFICATION  

---

## 1. Vulnerable Foreign-Reference Contract Matrix

The following matrix specifies the exact validation, query structure, response contract, and atomicity invariants for all 7 confirmed vulnerable foreign-reference fields across the application service boundary.

| REFERENCE FIELD | SOURCE ENTITY | TARGET ENTITY | ENTRYPOINT | SERVICE METHOD | TENANT OWNERSHIP QUERY | NULLABLE | VALID SAME-TENANT | FOREIGN-TENANT RESPONSE | NONEXISTENT RESPONSE | PARTIAL WRITE ALLOWED | TEST ID | CHECKPOINT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **1. pic_user_id (create)** | `Project` | `User` | `POST /api/v1/projects` | `ProjectService.create_project` | `SELECT 1 FROM users WHERE id = :pic_user_id AND organization_id = :org_id` | YES | 201 Created (persists `pic_user_id`) | 404 `EntityNotFoundException("User", :id)` | 404 `EntityNotFoundException("User", :id)` | NO (no project created, no code allocated) | `TEST-REF-01A` | CP1 / CP2 |
| **2. pic_user_id (update)** | `Project` | `User` | Internal Service (future `PATCH /projects/{id}`) | `ProjectService.update_project` | `SELECT 1 FROM users WHERE id = :pic_user_id AND organization_id = :org_id` | YES | 200 OK (updates `pic_user_id` / null clears) | 404 `EntityNotFoundException("User", :id)` | 404 `EntityNotFoundException("User", :id)` | NO (no field mutated on project) | `TEST-REF-01B` | CP1 / CP2 |
| **3. vendor_id** | `FixedAsset` | `Counterparty` | `POST /api/v1/fixed-assets` | `FixedAssetService.create_asset` | `SELECT 1 FROM counterparties WHERE id = :vendor_id AND organization_id = :org_id` | YES | 201 Created (persists `vendor_id`) | 404 `EntityNotFoundException("Counterparty", :id)` | 404 `EntityNotFoundException("Counterparty", :id)` | NO (no asset created, no audit log) | `TEST-REF-02` | CP1 / CP2 |
| **4. document_id** | `FixedAsset` | `Document` | `POST /api/v1/fixed-assets` | `FixedAssetService.create_asset` | `SELECT 1 FROM documents WHERE id = :document_id AND organization_id = :org_id` | YES | 201 Created (persists `document_id`) | 404 `EntityNotFoundException("Document", :id)` | 404 `EntityNotFoundException("Document", :id)` | NO (no asset created, no audit log) | `TEST-REF-03` | CP1 / CP2 |
| **5. transaction_id** | `Settlement` | `Transaction` | `POST /api/v1/money-movements` | `MoneyMovementService.create_money_movement` | `SELECT 1 FROM transactions WHERE id = :transaction_id AND organization_id = :org_id` | YES | 201 Created (persists `transaction_id` on Settlement) | 404 `EntityNotFoundException("Transaction", :id)` | 404 `EntityNotFoundException("Transaction", :id)` | NO (no money movement, settlement, or allocs created) | `TEST-REF-04` | CP1 / CP3 |
| **6. journal_line_id** | `BankReconciliation` | `JournalLine` (via `JournalEntry`) | `POST /api/v1/bank-reconciliation/reconcile` | `BankReconciliationService.match_manual` | `SELECT 1 FROM journal_lines jl JOIN journal_entries je ON jl.journal_entry_id = je.id WHERE jl.id = :jl_id AND je.organization_id = :org_id` | YES | 200 OK (reconciles statement line) | 404 `EntityNotFoundException("JournalLine", :id)` | 404 `EntityNotFoundException("JournalLine", :id)` | NO (statement line stays UNMATCHED, no recon row) | `TEST-REF-05` | CP1 / CP3 |
| **7. money_movement_id** | `BankReconciliation` | `MoneyMovement` | `POST /api/v1/bank-reconciliation/reconcile` | `BankReconciliationService.match_manual` | `SELECT 1 FROM money_movements WHERE id = :mm_id AND organization_id = :org_id` | YES | 200 OK (reconciles statement line) | 404 `EntityNotFoundException("MoneyMovement", :id)` | 404 `EntityNotFoundException("MoneyMovement", :id)` | NO (statement line stays UNMATCHED, no recon row) | `TEST-REF-06` | CP1 / CP3 |
| **8. transaction_id** | `BankReconciliation` | `Transaction` | `POST /api/v1/bank-reconciliation/reconcile` | `BankReconciliationService.match_manual` | `SELECT 1 FROM transactions WHERE id = :tx_id AND organization_id = :org_id` | YES | 200 OK (reconciles statement line) | 404 `EntityNotFoundException("Transaction", :id)` | 404 `EntityNotFoundException("Transaction", :id)` | NO (statement line stays UNMATCHED, no recon row) | `TEST-REF-07` | CP1 / CP3 |

---

## 2. Separate Defense-In-Depth Item (Service-Layer Boundary)

*Note: Project Budget endpoints (`GET /projects/{id}/budgets`, `POST /projects/{id}/budgets`) are **NOT** active cross-tenant API vulnerabilities because `api/v1/projects.py` performs `await service.get_project(org_id, project_id)` prior to delegating to service methods. This item hardens the service layer itself.*

| REFERENCE FIELD | SOURCE ENTITY | TARGET ENTITY | ENTRYPOINT | SERVICE METHOD | TENANT OWNERSHIP QUERY | NULLABLE | VALID SAME-TENANT | FOREIGN-TENANT RESPONSE | NONEXISTENT RESPONSE | PARTIAL WRITE ALLOWED | TEST ID | CHECKPOINT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **DID-1. project_id (budgets)** | `ProjectBudget` | `Project` | Internal Service / `api/v1/projects.py` | `ProjectService.get_project_budgets` & `ProjectService.add_or_update_project_budget` | `SELECT 1 FROM projects WHERE id = :project_id AND organization_id = :org_id` (via `get_project`) | NO | 200/201 (lists/upserts budgets) | 404 `EntityNotFoundException("Project", :id)` | 404 `EntityNotFoundException("Project", :id)` | NO (no budget row persisted or altered) | `TEST-DID-01` | CP1 / CP2 |

---

## 3. Information-Leakage & Oracle Defense Contract

1. **Uniform Status Code**: Both foreign-tenant UUIDs and non-existent UUIDs return `HTTP 404 Not Found`.
2. **Uniform Payload Structure**:
   ```json
   {
     "error": {
       "code": "NOT_FOUND",
       "message": "<EntityName> with identifier '<uuid>' not found.",
       "details": {
         "entity": "<EntityName>",
         "identifier": "<uuid>"
       }
     }
   }
   ```
3. **No Leakage**:
   - MUST NOT return `403 Forbidden` for a foreign-tenant entity reference (which would confirm the entity exists in another tenant).
   - MUST NOT return `422 Unprocessable Content` indicating cross-tenant ownership.
   - MUST NOT return entity name, owner organization, creation date, or metadata in response or logs.

---

## 4. Atomicity & Ordering Invariants

1. **Pre-Validation**: All foreign references must be verified before any entity instantiation, sequence allocation, state mutation, or database session flush.
2. **Multi-Item Collections**: In composite structures (such as `MoneyMovementCreate.settlements`), all settlements and their foreign `transaction_id` references must be fully verified prior to creating the parent `MoneyMovement` or allocating a sequence code.
3. **Rollback on Denial**: Any rejection via `EntityNotFoundException` aborts the transaction cleanly; zero rows, audit events, or sequence allocations survive.
