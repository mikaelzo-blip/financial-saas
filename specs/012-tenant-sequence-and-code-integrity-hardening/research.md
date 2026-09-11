# Technical Research & Architecture Decisions: Tenant Sequence & Code Integrity Hardening

**Feature**: `012-tenant-sequence-and-code-integrity-hardening`  
**Date**: 2026-09-10  
**Governing Documents**:
- `.specify/memory/constitution.md`
- `docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md`
- `docs/FINANCIAL_SAAS_DEEP_AUDIT_AND_REMEDIATION_2026-09-09.md`
- `specs/012-tenant-sequence-and-code-integrity-hardening/spec.md`

## Evidence Boundary

This research was originally prepared against commit `538817cc87165835a962c2032c65589fdcbfe09f` on the Feature 012 branch. It has been reconciled after the branch was refreshed onto current `origin/main` at `1d502016c1133a09de8eedd1e4bf0858c501bd98`, including the merged Alembic metadata-baseline prerequisite. The PostgreSQL evidence was executed against a disposable PostgreSQL 16 database with no production data, and no production source, migration, or tracked test implementation was added in this preparation phase.

Therefore:

- FIN-P1-104 remains a **confirmed schema/generation mismatch**, reproduced against PostgreSQL.
- FIN-P1-103 is a **reproduced PostgreSQL race and collision defect**, not merely a static risk.
- SQLite tests are not accepted as evidence for PostgreSQL row-locking or MVCC behavior.
- The merged baseline prerequisite is present and `uv run alembic check` is clean; Feature 012 production implementation remains unstarted.

## 1. Generator Inventory and Findings

| Entity / field | Generator and current algorithm | Scope / constraint | Classification |
|---|---|---|---|
| `Transaction.transaction_code` | `TransactionService.generate_transaction_code` counts tenant/year `TRX-YYYY-*` rows and adds one | Tenant + code via `uq_transactions_org_code`; no year column | Static race risk; format `TRX-YYYY-######` preserved |
| Reversal `Transaction.transaction_code` | `ReversalService.generate_reversal_code` independently counts the same tenant/year `TRX-YYYY-*` namespace | Same tenant + code constraint as normal transactions | Static race/shared-namespace risk; must share allocator with normal transactions |
| `JournalEntry.entry_number` | `AccountingEngine.generate_entry_number` counts tenant/year `JE-YYYY-*` rows and adds one | Tenant + code via `uq_je_org_entry_number` | Static race risk; format `JE-YYYY-######` preserved |
| `Project.project_code` | `ProjectService.generate_project_code` counts tenant/year `PRJ-YYYY-*` rows and adds one | Tenant + code via `uq_projects_org_project_code` | Static race risk; format `PRJ-YYYY-###` preserved |
| `VendorBill.bill_code` | `VendorAPService.generate_bill_code` counts tenant/year `BIL-YYYY-*` rows and adds one | Tenant + code via `uq_vendor_bills_org_code` | Static race risk; format `BIL-YYYY-######` preserved |
| `VendorAdvance.advance_code` | `VendorAPService.generate_advance_code` counts tenant/year `ADV-YYYY-*` rows and adds one | Tenant + code via `uq_vendor_advances_org_code` | Static race risk; format `ADV-YYYY-######` preserved |
| `CustomerInvoice.invoice_code` | `CustomerARService.generate_invoice_code` counts tenant/year `INV-YYYY-*` rows and adds one | Tenant + code via `uq_customer_invoices_org_code` | Static race risk; caller override remains separately validated |
| `CustomerRetentionRelease.release_code` | `CustomerARService.generate_retention_release_code` counts tenant/year `REL-YYYY-*` rows and adds one | Tenant + code via `uq_customer_retention_releases_org_code` | Static race risk; format `REL-YYYY-######` preserved |
| `Document.document_code` | `DocumentService.generate_document_code` loads tenant/year codes and takes max numeric suffix plus one | Tenant + code via `uq_documents_org_document_code` | Static max-scan race risk; format `DOC-YYYY-######` preserved |
| `MoneyMovement.movement_code` | `_generate_movement_code` counts tenant/year `MM-YYYY-*` rows and adds one | **Global** single-column unique in model/migration | Confirmed FIN-P1-104 mismatch plus static race risk |
| `Settlement.settlement_code` | `_generate_settlement_code` counts tenant `SET-*` rows and adds one | **Global** single-column unique in model/migration | Confirmed FIN-P1-104 mismatch plus static race risk |
| `FixedAsset.asset_code` | Caller supplies code; service checks uniqueness only within tenant | **Global** single-column unique in model/migration | Confirmed FIN-P1-104 mismatch; caller-controlled format |
| Depreciation `Transaction.transaction_code` | Concatenates caller-controlled `asset_code` and `YYYYMM` as `DEP-{asset_code}-{YYYYMM}` | Inherits tenant + code transaction constraint; `asset_code` may make output exceed `String(50)` | Directly related static integrity risk; separate scope decision required before change |
| Opening-balance `Transaction.transaction_code` | `OPB-YYYY-` plus six hex characters from UUID4 | Tenant + code transaction constraint | Not COUNT-based; finite truncated randomness and format deviation are static risks |
| Remote inbox `Document.document_code` | `DOC-WA-` plus eight hex characters from UUID4 | Tenant + code document constraint | Not sequential; bypasses canonical document numbering and uses finite randomness |
| `DocumentSession.session_code` | `SESS-` plus eight hex characters from UUID4 | Global unique model/migration | Scope is internally aligned with global random generation; low-entropy collision risk is static, not a confirmed Feature 012 migration target |

Caller-supplied external references (`reference_no`, invoice numbers, PO/SPK numbers, OCR document numbers, transfer references, and account/payment identifiers) are not internal sequence generators. They must remain distinguishable from generated system codes. Existing caller overrides, especially invoice/bill references and `asset_code`, require validation/constraint handling in implementation without silently changing external formats.

## 2. Database Uniqueness Inventory

| Identifier | Model/migration semantics | Intended classification | Generation/service alignment |
|---|---|---|---|
| Transaction code | `UNIQUE (organization_id, transaction_code)` | Tenant unique | Scope aligned; allocator unsafe |
| Journal entry number | `UNIQUE (organization_id, entry_number)` | Tenant unique | Scope aligned; allocator unsafe |
| Project code | `UNIQUE (organization_id, project_code)` | Tenant unique | Scope aligned; allocator unsafe |
| Document code | `UNIQUE (organization_id, document_code)` | Tenant unique | Scope aligned; allocator unsafe |
| Invoice, bill, advance, release codes | Composite tenant/code constraints | Tenant unique | Scope aligned; allocators unsafe |
| Money movement code | `UNIQUE (movement_code)` | Tenant unique based on service behavior | **Mismatch: tenant generation vs global constraint** |
| Settlement code | `UNIQUE (settlement_code)` | Tenant unique based on service behavior | **Mismatch: tenant generation vs global constraint** |
| Fixed asset code | `UNIQUE (asset_code)`; service checks tenant | Tenant unique based on asset-register semantics | **Mismatch: tenant validation vs global constraint** |
| Document session code | `UNIQUE (session_code)` | Global random technical/session identifier | Scope aligned; entropy is a separate static concern |
| Organization slug | `UNIQUE (slug)` | Global unique | Correct for tenant routing |
| WhatsApp sender phone | `UNIQUE (phone_number)` | Global unique | Correct because inbound sender resolution lacks tenant context |
| Chart-of-accounts code | `UNIQUE (organization_id, account_code)` | Tenant unique | Correct |
| Accounting period name | `UNIQUE (organization_id, period_name)` | Tenant unique | Correct |

Relevant evidence includes `backend/src/models/money_movement.py:39-43,105-109`, `backend/src/models/fixed_asset.py:42-46`, `backend/src/models/transaction.py:43-64`, and migrations `016_p1_settlements.py:53,72`, `019_p6_periods_and_assets.py:43`, `004_transactions.py:79`, `005_journal.py:43`, `002_projects.py:57`, `003_documents.py:50`, `006_payables.py:41,89`, `007_receivables.py:42`, and `012_retention_and_closure.py:46`.

## 3. FIN-P1-103 Analysis

### Static failure mechanism

The affected generators issue a read (`COUNT` or max-suffix scan), calculate `next = current + 1` in application memory, and only later flush the new row. Two PostgreSQL transactions for the same tenant and sequence scope can observe the same committed state and calculate the same code. Existing composite constraints protect some tables from duplicate committed codes, but they turn the race into an insert failure; tables without constraints can admit duplicate codes. A constraint alone is not an allocator.

Reversal generation is especially important because it independently counts the same `TRX-YYYY-*` namespace used by normal transaction creation. It must not receive a separate counter namespace unless an approved format change is made; the current format and shared namespace are preserved.

### Reproduction result

The reproduction used N concurrent PostgreSQL transactions creating records in one tenant/year, with separate sessions and a barrier before allocation. The unmodified generators reproduced duplicate candidates and create-path uniqueness collisions. The result is therefore:

- **Static risk: CONFIRMED**
- **PostgreSQL reproduced defect: VERIFIED**
- **SQLite equivalence: REJECTED**

## 4. FIN-P1-104 Analysis

The mismatch is confirmed without concurrent execution:

1. Tenant A starts with no money movement and generates `MM-YYYY-000001`; tenant B also starts with no money movement and generates the same tenant-local code.
2. The current database accepts only one because `movement_code` is globally unique.
3. The identical sequence applies to `SET-000001` and caller-supplied asset code such as `AST-001`.

This is a semantic mismatch, not merely a timing issue. The preferred correction is to align the database with the already-observed tenant-local service behavior using composite constraints, subject to live-schema name verification and pre-migration duplicate checks.

## 5. Solution Evaluation

| Option | Correctness | Tenant isolation | Transactionality | Migration impact | Maintainability / local-first |
|---|---|---|---|---|---|
| A. PostgreSQL sequence per identifier | Strong atomic allocation, but native sequences are global unless many sequence objects or encoded keys are introduced | Requires tenant/year sequence provisioning and lifecycle management | Sequence values are not rolled back; gaps are normal | New sequence objects or provisioning logic; format mapping complexity | PostgreSQL-specific and more moving parts |
| B. Tenant/year counter table with row locking | Strong if allocation row is locked and incremented atomically in the same transaction | Natural `(organization_id, namespace, year)` key | Counter update participates in transaction; failed create can roll back allocation | One new table plus one migration; no existing code format change | PostgreSQL-native SQLAlchemy pattern, explicit, testable, suitable for local-first |
| C. `SELECT ... FOR UPDATE` on existing business rows | Works only when a stable row already exists; cannot safely lock an empty sequence | Tenant filter can be correct | Transactional lock, but first-row/bootstrap race remains | No schema change for existing rows, but requires bootstrap row strategy | Fragile for empty scopes and not suitable as the sole allocator |
| D. PostgreSQL advisory transaction lock | Can serialize a deterministic tenant/namespace/year key | Correct only if every caller computes the exact same lock key | Transaction-scoped and rollback-safe | No schema migration; PostgreSQL-specific lock protocol | Small schema impact but invisible coordination and collision-key maintenance are harder to audit |
| E. Unique constraint plus bounded retry | Provides a safety net and can recover races when constraints exist | Only as correct as the constraint scope | Failed attempts must roll back cleanly; retry needs a fresh transaction/session state | Composite constraints still required for FIN-P1-104; no allocator migration if accepting gaps | Useful defense-in-depth, but does not guarantee success for unconstrained tables or eliminate repeated race failures |
| F. Existing repository-native mechanism | No existing authoritative allocator was found; current mechanisms are COUNT/max scans | N/A | N/A | N/A | Rejected as unavailable |

### Validated recommendation

Use a tenant/year counter table with an atomic row-locked allocation in the same database transaction as the business record, retaining the current prefixes and padding. Add bounded collision retry only as defense-in-depth around authoritative unique constraints. PostgreSQL reproduction and migration dry-run evidence validate the design. Do not substitute an in-process Python lock.

The allocator supports namespaces whose format is not year-scoped, such as settlement codes, with the explicit non-null `scope_key="GLOBAL"` policy defined in the implementation contract. No new business policy is inferred from the absence of a year in `SET-######`.

## 6. Historical Data and Migration Safety

The proposed FIN-P1-104 constraint change relaxes global uniqueness to tenant-local uniqueness. Existing rows satisfying global uniqueness necessarily satisfy the composite constraint, so the data transformation is non-destructive in principle. Implementation must still run preflight duplicate queries and verify actual live constraint names before DDL. The migration must fail closed if any duplicate tuple exists or if expected constraints are absent.

No historical codes may be regenerated, renumbered, or deleted. No production database was accessed. `backend/storage` and `backend/backend/storage` were not accessed or modified.

## 7. Decisions and Open Gates

Confirmed now:

- Internal financial and operational business codes are tenant-local where existing services already filter by `organization_id`.
- Existing generated formats remain unchanged.
- Reversals share the normal transaction-code namespace.
- Global uniqueness remains correct for organization slugs and WhatsApp sender phone mappings.
- `DocumentSession.session_code` is not included in the migration scope solely because it is globally unique; its entropy concern needs a separate decision if it becomes operationally material.

Implementation checkpoints completed:

- Tracked PostgreSQL regression tests cover same-tenant concurrency and cross-tenant constraint behavior.
- The database-backed allocator and all affected generator call sites are implemented and tested.
- Feature 012 migrations `022_tenant_sequence_scope` and `023_historical_seq_bootstrap` are validated; the final head is `023_historical_seq_bootstrap`.
- Bounded retry with a clean transaction/session boundary and posting-integrity verification are complete.

CP7 note: the historical bootstrap is online-only for data inspection and fail-closed parsing. Offline Alembic SQL generation emits the schema chain and revision marker without attempting historical inspection.
- Caller-supplied `asset_code` and depreciation transaction-code length validation remain separately approved follow-up observations; they are directly related but not required to prove FIN-P1-104.
