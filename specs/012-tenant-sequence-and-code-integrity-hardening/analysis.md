# Pre-Implementation Consistency Analysis: Feature 012

**Feature**: `012-tenant-sequence-and-code-integrity-hardening`  
**Spec**: `specs/012-tenant-sequence-and-code-integrity-hardening/spec.md`  
**Plan**: `specs/012-tenant-sequence-and-code-integrity-hardening/plan.md`  
**Tasks**: `specs/012-tenant-sequence-and-code-integrity-hardening/tasks.md`  
**Analysis date**: 2026-09-10
**Reconciled baseline**: `origin/main` / `1d502016c1133a09de8eedd1e4bf0858c501bd98`
**Feature evidence checkpoint**: `01e2e3dd73259fa8d41f33adaaccc9bf80abf586` (rebased preservation of analysis checkpoint `b3773485d0a332bf332d28b49e589a77aeb3adfd`)

## 1. Requirement Traceability Matrix

| Requirement | Plan coverage | Task coverage | Result |
|---|---|---|---|
| FR-001 inventory and route every internal generator | Evidence and scope; CP3 | T033, T034 | COVERED |
| FR-002 atomic year-coded namespaces | Architecture; CP2/CP3 | T006-T019 | COVERED |
| FR-003 atomic non-year SET namespace | Data model scope policy | T017 | COVERED, policy resolved |
| FR-004 shared TRX normal/reversal namespace | CP3 | T013-T014, T018 | COVERED |
| FR-005 preserve formats/API/history | Global constraints; CP3/CP6 | T014, T016, T029, T034 | COVERED |
| FR-006 tenant isolation | Constitution check; counter schema | T012, T018, T019, T025, T028 | COVERED |
| FR-007 three composite uniqueness changes only | CP4; migration strategy | T020-T025 | COVERED |
| FR-008 same-tenant duplicate rejection | CP4 | T020, T025 | COVERED |
| FR-009 same transaction/no partial records | Counter allocation; rollback strategy | T010-T012, T018, T028 | COVERED |
| FR-010 bounded clean retry/no duplicate posting | Contract; CP5 | T011, T026-T028 | COVERED, production implementation pending |
| FR-011 accounting and immutability invariants | Constitution check | T028, T034 | COVERED |
| FR-012 PostgreSQL-specific verification | Evidence boundary; CP1/CP6 | T002-T005, T019, T025, T031-T032 | EVIDENCE COMPLETE; tracked regression coverage pending |
| FR-013 preflight/fail-closed/non-destructive migration | Data model migration strategy | T021-T025 | COVERED; preflight simulation passed |
| FR-014 intentional global identifiers | Research inventory | T030, T033 | COVERED |
| FR-015 protected storage untouched | Global constraints | T034 | COVERED |
| FR-016 classify excluded/related identifiers | Research and scope gate | T029-T030, T033 | COVERED |
| FR-017 complete regression/concurrency matrix | CP1/CP6 | T003-T005, T019, T024-T030, T031-T032 | COVERED by plan; tracked tests pending |

**Traceability result: 17/17 requirements covered (100%).**

## 2. PostgreSQL Evidence Boundary

**Method**: Disposable Docker container `pg_disposable_f012`, image `postgres:16`, local-only `127.0.0.1:54329`. Disposable database and credentials were used; no production data or credentials were used. Credentials remain in an ignored environment file and are not recorded here.

### Baseline

- Fresh database: Alembic upgrade from scratch completed through `021_fixed_asset_enhancements`.
- Existing disposable database: `alembic current` and `alembic heads` both report `021_fixed_asset_enhancements (head)`.
- Current branch contains the merged metadata reconciliation; authoritative model registration is complete and `uv run alembic check` reports `No new upgrade operations detected.`
- Live schema constraints verified:
  - `uq_money_movements_movement_code` — global `UNIQUE (movement_code)`.
  - `uq_settlements_settlement_code` — global `UNIQUE (settlement_code)`.
  - `uq_fixed_assets_asset_code` — global `UNIQUE (asset_code)`.
  - `uq_document_sessions_session_code` — global `UNIQUE (session_code)`.
- `tenant_sequences` is not part of the current baseline; it was created only by a throwaway harness and removed afterward.
- **Schema drift**: **NO** on the refreshed branch baseline. The merged metadata reconciliation is present, and `uv run alembic check` completed with `No new upgrade operations detected.`

## 3. FIN-P1-103 — Concurrency Evidence

| Generator | Current algorithm | Namespace | PostgreSQL concurrency result | Duplicate candidate | DB behavior | Partial write | Rollback | Retry | Classification |
|---|---|---|---|---|---|---|---|---|---|
| `TransactionService.generate_transaction_code` | Tenant/year `COUNT(*) + 1` | `TRX` + year | N=50 returned 1 unique value | 49 collisions; all `TRX-2026-000001` | Candidate-only calls do not write; create path produced 1 success/49 `UniqueViolationError` on `uq_transactions_org_code` | Create path left 1 committed row, no failed partial rows | Explicit rollback cleared failed inserts | Not implemented in current code; fresh retry boundary required | REPRODUCED DEFECT |
| `ReversalService.generate_reversal_code` | Independent tenant/year `COUNT(*) + 1` | Shared `TRX` + year | Concurrent normal/reversal calls returned same `TRX-2026-000002` | 1 shared collision | Would be rejected by transaction-code uniqueness if both persisted | No rows in candidate-only probe | No business write in candidate-only probe | Not implemented | REPRODUCED DEFECT |
| `AccountingEngine.generate_entry_number` | Tenant/year `COUNT(*) + 1` | `JE` + year | N=50 returned 1 unique value | 49 collisions; all `JE-2026-000001` | Candidate-only probe; persistence path remains unsafe | No rows in candidate-only probe | Not applicable to candidate-only probe | Not implemented | REPRODUCED DEFECT |
| `ProjectService.generate_project_code` | Tenant/year `COUNT(*) + 1` | `PRJ` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `DocumentService.generate_document_code` | Tenant/year max suffix + 1 | `DOC` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `VendorAPService.generate_bill_code` | Tenant/year `COUNT(*) + 1` | `BIL` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `VendorAPService.generate_advance_code` | Tenant/year `COUNT(*) + 1` | `ADV` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `CustomerARService.generate_invoice_code` | Tenant/year `COUNT(*) + 1` | `INV` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `CustomerARService.generate_retention_release_code` | Tenant/year `COUNT(*) + 1` | `REL` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `MoneyMovementService._generate_movement_code` | Tenant/year `COUNT(*) + 1` | `MM` + year | N=20 returned 1 unique value | 19 collisions | Candidate-only probe; current global DB uniqueness is a separate FIN-P1-104 mismatch | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |
| `MoneyMovementService._generate_settlement_code` | Tenant `COUNT(*) + 1` | `SET` + `GLOBAL` | N=20 returned 1 unique value | 19 collisions; all `SET-000001` | Candidate-only probe; current global DB uniqueness is a separate FIN-P1-104 mismatch | No rows in candidate-only probe | Not applicable | Not implemented | REPRODUCED DEFECT |

**Rejected findings**: `DocumentSession.session_code` is intentionally global and aligned with its global constraint; it is not part of FIN-P1-103/104 remediation. Opening-balance and remote-inbox UUID-derived codes are separate static observations, not COUNT/MAX sequence defects.

## 4. FIN-P1-104 — Constraint Evidence

| Identifier | Current constraint | Actual live name | Generation/validation scope | Intended scope | Proposed constraint | Preflight | Migration safe | Downgrade risk |
|---|---|---|---|---|---|---|---|---|
| `movement_code` | Global unique | `uq_money_movements_movement_code` | Tenant/year generation | Tenant-local | `UNIQUE (organization_id, movement_code)` | 0 duplicate tenant/code tuples | Yes, after expected-name and duplicate checks | Global downgrade becomes impossible if cross-tenant duplicates are legitimately created |
| `settlement_code` | Global unique | `uq_settlements_settlement_code` | Tenant-global generation | Tenant-local | `UNIQUE (organization_id, settlement_code)` | 0 duplicate tenant/code tuples | Yes, after expected-name and duplicate checks | Same downgrade limitation |
| `asset_code` | Global unique | `uq_fixed_assets_asset_code` | Tenant-scoped service validation | Tenant-local | `UNIQUE (organization_id, asset_code)` | 0 duplicate tenant/code tuples | Yes, after expected-name and duplicate checks | Same downgrade limitation |

Live reproduction against two organizations:

- Same `movement_code` was rejected by PostgreSQL with `UniqueViolationError` on `uq_money_movements_movement_code`.
- Same `settlement_code` was rejected by PostgreSQL with `UniqueViolationError` on `uq_settlements_settlement_code`.
- Same `asset_code` passed tenant service validation but commit was rejected by PostgreSQL with `UniqueViolationError` on `uq_fixed_assets_asset_code`.
- `DocumentSession.session_code` remained globally unique under `uq_document_sessions_session_code`; rejected as a mismatch.

## 5. Counter Design Validation

Proposed key:

```text
organization_id | namespace | scope_key
```

- Year-coded namespaces: `TRX`, `JE`, `PRJ`, `DOC`, `INV`, `BIL`, `ADV`, `REL`, `MM` with scope keys such as `"2026"`.
- Tenant-global non-year namespace: `SET` with explicit non-null `scope_key="GLOBAL"`.
- Required unique key: `(organization_id, namespace, scope_key)`; all columns `NOT NULL`.
- Visible formats remain unchanged, including `SET-######`.

Throwaway PostgreSQL validation passed:

- N=50 concurrent first-row allocations for one tenant/namespace/year: 50 unique values, contiguous 1..50.
- Different tenants on `SET|GLOBAL`: each received 1..5 independently.
- Different years: `TRX|2026` continued while `TRX|2027` started at 1.
- Namespace matrix: `TRX`, `JE`, `PRJ`, `DOC`, `INV`, `BIL`, `ADV`, `REL`, `MM`, and `SET|GLOBAL` rendered expected first codes.
- Rollback: a rolled-back first allocation was not committed; the next allocation returned 1.
- Failed transaction: a unique violation poisoned the transaction until rollback; after rollback a clean retry returned 1.
- Application restart/multiple worker proxy: a new SQLAlchemy engine continued the existing sequence and returned 2.
- Different tenant/scope rows did not collide in the harness.

The harness used PostgreSQL `INSERT ... ON CONFLICT (...) DO UPDATE ... RETURNING` and did not modify production source. The production allocator remains unimplemented.

## 6. Retry and Poisoned Session Gate

Verified database behavior:

1. A PostgreSQL uniqueness violation aborts the current transaction.
2. SQLAlchemy rejects subsequent work before rollback (`DBAPIError` observed).
3. Explicit rollback recovers the session.
4. A fresh transaction/session unit is required for retry.

Production retry result: **NOT IMPLEMENTED**. The future implementation must bound retries and establish a clean transaction boundary; it must not catch and continue on the poisoned session.

## 7. Proposed Migration — Analysis Only

One Alembic revision is required, after `021_fixed_asset_enhancements`.

### Upgrade operations

1. Verify the current revision/head and expected live global constraint names. Abort without DDL if any expected constraint is absent or has unexpected definition.
2. Run duplicate preflight for `(organization_id, movement_code)`, `(organization_id, settlement_code)`, and `(organization_id, asset_code)`. Abort without DDL if any rows are returned.
3. Create `uq_money_movements_org_code`, `uq_settlements_org_code`, and `uq_fixed_assets_org_code` composite unique constraints.
4. Drop the corresponding global constraints only after the composite constraints exist.
5. Verify metadata and same-tenant/cross-tenant behavior.
6. Perform no data updates, deletes, renumbering, or historical rewrites.

### Downgrade operations

1. Preflight global duplicate codes for each affected table.
2. Abort downgrade before DDL if any code is shared across organizations.
3. If clean, create the original global constraints and then drop composite constraints.
4. Never delete or reconcile records automatically to force downgrade success.

## 8. Consistency and Readiness

| Gate | Status | Evidence |
|---|---|---|
| Policy decisions | PASS | SET is tenant-global/non-year via `GLOBAL`; asset/depreciation validation length deferred. |
| FIN-P1-103 PostgreSQL reproduction | PASS | Unmodified generators reproduced duplicate candidates and unique violations. |
| FIN-P1-104 PostgreSQL reproduction | PASS | Three global constraints rejected legitimate same-code cross-tenant usage. |
| First-row bootstrap design | PASS as throwaway harness evidence | N=50 concurrent first-row allocations were unique and contiguous. |
| Rollback/session recovery | PASS as database behavior; implementation pending | Poisoned session required rollback; clean retry then succeeded. |
| Live constraint verification | PASS | Expected names and definitions verified. |
| Duplicate preflight | PASS | Zero existing tenant/code duplicate tuples. |
| Alembic head | PASS | Fresh and existing disposable databases reached `021_fixed_asset_enhancements`. |
| Alembic drift check | PASS | Refreshed current-main baseline reports `No new upgrade operations detected.` |
| Tracked evidence tests | PENDING | Throwaway scripts are ignored; no tracked integration tests were added. |
| Production implementation | NOT STARTED | No production source, model, migration, or tracked test changes. |

**Requirement coverage: 100% (17/17).**

**Critical/High consistency result**: No Feature 012 Critical/High consistency issue is identified. Baseline drift is resolved. Tracked PostgreSQL tests and production clean-retry behavior remain implementation work.

**Constitution violations**: 0 identified.

**Spec Kit consistency result**: **YES for implementation authorization**. The policy, evidence, current baseline, counter design, migration parent, and checkpoint tasks are consistent. Tracked regression tests and clean-retry behavior are pending implementation, not unresolved design ambiguity.

**Exact next action**: Begin CP1 by adding the tracked PostgreSQL evidence/regression tests for FIN-P1-103 and FIN-P1-104. Do not begin CP1 in this reconciliation turn.
