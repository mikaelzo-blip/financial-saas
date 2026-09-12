# Requirements & Invariant Checklist: FIN-P1-102

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Branch**: `hermes/fin-p1-102-transaction-type-contract`
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Core Invariant Coverage (14 / 14)

| Invariant | Description | Verification Method | Status |
|---|---|---|:---:|
| **TYPE-R01** | Generic transaction creation accepts only types with executable normal posting path. | Parameterized intake test against all 16 unsupported types plus REVERSAL. | VERIFIED CP2 |
| **TYPE-R02** | Unsupported types rejected prior to Transaction model persistence or DB flush. | DB count assertion showing zero rows added on rejection. | VERIFIED CP2 |
| **TYPE-R03** | Unsupported type rejection returns HTTP 422 with `INVARIANT_VIOLATION`. | HTTP status, error code, type, and reason assertions in API tests. | VERIFIED CP2 |
| **TYPE-R04** | Rejected generic transaction creation consumes no tenant sequence number. | `TenantSequence` assertion after rejected call. | VERIFIED CP2 |
| **TYPE-R05** | `REVERSAL` cannot enter generic transaction creation. | Intake test attempting `create_transaction` with `REVERSAL`. | VERIFIED CP2 |
| **TYPE-R06** | Dedicated `ReversalService` remains functional and unchanged. | `test_reversals.py` and dedicated reversal test pass. | VERIFIED CP2 REGRESSION |
| **TYPE-R07** | Document candidate correction cannot assign non-executable type. | Document correction API test attempting unsupported type. | PENDING IMPLEMENTATION |
| **TYPE-R08** | Document approval cannot create an unpostable Transaction. | Document candidate approval defense-in-depth test. | PENDING IMPLEMENTATION |
| **TYPE-R09** | `PETTY_CASH_EXPENSE` removed from `AUTO_SAFE_TYPES`. | `ProcessingPolicyService` evaluation test. | PENDING IMPLEMENTATION |
| **TYPE-R10** | Every `AUTO_SAFE` type must be `GENERIC_INGESTIBLE` and executable. | Mathematical set subset assertion test. | PENDING IMPLEMENTATION |
| **TYPE-R11** | All 20 `PostingRuleRegistry` types remain generic-capable. | Exact 20-type capability membership plus representative DIRECT_PURCHASE and BANK_CHARGE API controls. | VERIFIED CP2 |
| **TYPE-R12** | No new debit/credit or posting policy is introduced. | Diff inspection and accounting-engine regression: journal leg definitions unchanged. | VERIFIED CP2 |
| **TYPE-R13** | Existing unsupported historical rows are not migrated or rewritten. | Historical data boundary inspection: 0 data migrations. | CONFIRMED IN SPEC |
| **TYPE-R14** | No database migration is required. | Alembic check confirming 0 new migrations and 0 drift. | CONFIRMED IN SPEC |

---

## 2. 37-Type Classification Checklist (37 / 37)

### Group A: Normal Posting Rule Supported (20 Types) — Generic Intake ALLOWED
- [x] `DIRECT_PURCHASE` (TC-GEN-001)
- [x] `VENDOR_BILL` (TC-GEN-002)
- [x] `PAY_VENDOR_BILL` (TC-GEN-003)
- [x] `SUBCONTRACTOR_BILL` (TC-GEN-004)
- [x] `PAY_SUBCONTRACTOR` (TC-GEN-005)
- [x] `VENDOR_ADVANCE` (TC-GEN-006)
- [x] `SETTLE_VENDOR_ADVANCE` (TC-GEN-007)
- [x] `CUSTOMER_ADVANCE` (TC-GEN-008)
- [x] `BANK_TO_CASH` (TC-GEN-009)
- [x] `CASH_TO_BANK` (TC-GEN-010)
- [x] `INTERBANK_TRANSFER` (TC-GEN-011)
- [x] `ASSET_PURCHASE` (TC-GEN-012)
- [x] `FIXED_ASSET_DEPRECIATION` (TC-GEN-013)
- [x] `CUSTOMER_INVOICE` (TC-GEN-014)
- [x] `CUSTOMER_PAYMENT` (TC-GEN-015)
- [x] `RETENTION_RELEASE` (TC-GEN-016)
- [x] `OWNER_CONTRIBUTION` (TC-GEN-017)
- [x] `OWNER_WITHDRAWAL` (TC-GEN-018)
- [x] `BANK_CHARGE` (TC-GEN-019)
- [x] `JOURNAL_ADJUSTMENT` (TC-GEN-020)

### Group B: Special Workflow Supported (1 Type) — Generic Intake REJECTED, Dedicated ALLOWED
- [x] `REVERSAL` (TC-REV-001)

### Group C: Currently Unsupported (16 Types) — Generic Intake REJECTED
- [x] `EMPLOYEE_ADVANCE` (TC-UNSUP-001)
- [x] `EMPLOYEE_SETTLEMENT` (TC-UNSUP-002)
- [x] `REIMBURSEMENT` (TC-UNSUP-003)
- [x] `PAY_REIMBURSEMENT` (TC-UNSUP-004)
- [x] `PETTY_CASH_EXPENSE` (TC-UNSUP-005)
- [x] `TOPUP_PETTY_CASH` (TC-UNSUP-006)
- [x] `RETURN_PETTY_CASH` (TC-UNSUP-007)
- [x] `INVENTORY_PURCHASE` (TC-UNSUP-008)
- [x] `INVENTORY_USAGE` (TC-UNSUP-009)
- [x] `REVENUE_RECOGNITION` (TC-UNSUP-010)
- [x] `CUSTOMER_REFUND` (TC-UNSUP-011)
- [x] `VENDOR_REFUND` (TC-UNSUP-012)
- [x] `LOAN_RECEIVED` (TC-UNSUP-013)
- [x] `LOAN_PAYMENT` (TC-UNSUP-014)
- [x] `OTHER_INCOME` (TC-UNSUP-015)
- [x] `OTHER_EXPENSE` (TC-UNSUP-016)

---

## 3. Checkpoint Delivery Gates

- [x] **CP1 Gate**: Executable RED / characterization tests committed; 0 production code changes.
- [x] **CP2 Gate**: Dispatch-backed `PostingRuleRegistry` capabilities and pre-sequence `TransactionService` gate implemented; AUTHZ fixture aligned; 27 passed / 19 expected XFAIL; independent review PASS.
- [ ] **CP3 Gate**: Document correction & approval protected; `PETTY_CASH_EXPENSE` removed from `AUTO_SAFE_TYPES`; all focused tests GREEN.
- [ ] **CP4 Gate**: Full backend regression (690+ tests), Alembic zero drift, frontend build passing, independent review completed.
