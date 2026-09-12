# Requirements & Invariant Checklist: FIN-P1-102

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Branch**: `hermes/fin-p1-102-transaction-type-contract`
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Core Invariant Coverage (14 / 14)

| Invariant | Description | Verification Method | Status |
|---|---|---|:---:|
| **TYPE-R01** | Generic transaction creation accepts only types with executable normal posting path. | Parameterized intake test against all 16 unsupported types. | PENDING IMPLEMENTATION |
| **TYPE-R02** | Unsupported types rejected prior to Transaction model persistence or DB flush. | DB count assertion showing zero rows added on rejection. | PENDING IMPLEMENTATION |
| **TYPE-R03** | Unsupported type rejection returns HTTP 422 with `INVARIANT_VIOLATION`. | HTTP status & error code assertion in API tests. | PENDING IMPLEMENTATION |
| **TYPE-R04** | Rejected generic transaction creation consumes no tenant sequence number. | `TenantSequenceCounter` assertion before and after rejected call. | PENDING IMPLEMENTATION |
| **TYPE-R05** | `REVERSAL` cannot enter generic transaction creation. | Intake test attempting `create_transaction` with `REVERSAL`. | PENDING IMPLEMENTATION |
| **TYPE-R06** | Dedicated `ReversalService` remains functional and unchanged. | `test_reversals.py` and dedicated reversal test pass. | VERIFIED IN BASELINE |
| **TYPE-R07** | Document candidate correction cannot assign non-executable type. | Document correction API test attempting unsupported type. | PENDING IMPLEMENTATION |
| **TYPE-R08** | Document approval cannot create an unpostable Transaction. | Document candidate approval defense-in-depth test. | PENDING IMPLEMENTATION |
| **TYPE-R09** | `PETTY_CASH_EXPENSE` removed from `AUTO_SAFE_TYPES`. | `ProcessingPolicyService` evaluation test. | PENDING IMPLEMENTATION |
| **TYPE-R10** | Every `AUTO_SAFE` type must be `GENERIC_INGESTIBLE` and executable. | Mathematical set subset assertion test. | PENDING IMPLEMENTATION |
| **TYPE-R11** | All 20 `PostingRuleRegistry` types remain generically creatable. | Parameterized positive-control suite with schema-valid, type-appropriate fixtures for all 20 types. | PENDING IMPLEMENTATION (CP2) |
| **TYPE-R12** | No new debit/credit or posting policy is introduced. | Code diff inspection: 0 changes to journal generation legs. | CONFIRMED IN SPEC |
| **TYPE-R13** | Existing unsupported historical rows are not migrated or rewritten. | Historical data boundary inspection: 0 data migrations. | CONFIRMED IN SPEC |
| **TYPE-R14** | No database migration is required. | Alembic check confirming 0 new migrations and 0 drift. | CONFIRMED IN SPEC |

---

## 2. 37-Type Classification Checklist (37 / 37)

### Group A: Normal Posting Rule Supported (20 Types) — Generic Intake ALLOWED
- [ ] `DIRECT_PURCHASE` (TC-GEN-001)
- [ ] `VENDOR_BILL` (TC-GEN-002)
- [ ] `PAY_VENDOR_BILL` (TC-GEN-003)
- [ ] `SUBCONTRACTOR_BILL` (TC-GEN-004)
- [ ] `PAY_SUBCONTRACTOR` (TC-GEN-005)
- [ ] `VENDOR_ADVANCE` (TC-GEN-006)
- [ ] `SETTLE_VENDOR_ADVANCE` (TC-GEN-007)
- [ ] `CUSTOMER_ADVANCE` (TC-GEN-008)
- [ ] `BANK_TO_CASH` (TC-GEN-009)
- [ ] `CASH_TO_BANK` (TC-GEN-010)
- [ ] `INTERBANK_TRANSFER` (TC-GEN-011)
- [ ] `ASSET_PURCHASE` (TC-GEN-012)
- [ ] `FIXED_ASSET_DEPRECIATION` (TC-GEN-013)
- [ ] `CUSTOMER_INVOICE` (TC-GEN-014)
- [ ] `CUSTOMER_PAYMENT` (TC-GEN-015)
- [ ] `RETENTION_RELEASE` (TC-GEN-016)
- [ ] `OWNER_CONTRIBUTION` (TC-GEN-017)
- [ ] `OWNER_WITHDRAWAL` (TC-GEN-018)
- [ ] `BANK_CHARGE` (TC-GEN-019)
- [ ] `JOURNAL_ADJUSTMENT` (TC-GEN-020)

### Group B: Special Workflow Supported (1 Type) — Generic Intake REJECTED, Dedicated ALLOWED
- [ ] `REVERSAL` (TC-REV-001)

### Group C: Currently Unsupported (16 Types) — Generic Intake REJECTED
- [ ] `EMPLOYEE_ADVANCE` (TC-UNSUP-001)
- [ ] `EMPLOYEE_SETTLEMENT` (TC-UNSUP-002)
- [ ] `REIMBURSEMENT` (TC-UNSUP-003)
- [ ] `PAY_REIMBURSEMENT` (TC-UNSUP-004)
- [ ] `PETTY_CASH_EXPENSE` (TC-UNSUP-005)
- [ ] `TOPUP_PETTY_CASH` (TC-UNSUP-006)
- [ ] `RETURN_PETTY_CASH` (TC-UNSUP-007)
- [ ] `INVENTORY_PURCHASE` (TC-UNSUP-008)
- [ ] `INVENTORY_USAGE` (TC-UNSUP-009)
- [ ] `REVENUE_RECOGNITION` (TC-UNSUP-010)
- [ ] `CUSTOMER_REFUND` (TC-UNSUP-011)
- [ ] `VENDOR_REFUND` (TC-UNSUP-012)
- [ ] `LOAN_RECEIVED` (TC-UNSUP-013)
- [ ] `LOAN_PAYMENT` (TC-UNSUP-014)
- [ ] `OTHER_INCOME` (TC-UNSUP-015)
- [ ] `OTHER_EXPENSE` (TC-UNSUP-016)

---

## 3. Checkpoint Delivery Gates

- [ ] **CP1 Gate**: Executable RED / characterization tests committed; 0 production code changes.
- [ ] **CP2 Gate**: `PostingRuleRegistry` capabilities and `TransactionService` gate implemented; `test_authz001_role_enforcement.py` aligned; CP2 tests turn GREEN.
- [ ] **CP3 Gate**: Document correction & approval protected; `PETTY_CASH_EXPENSE` removed from `AUTO_SAFE_TYPES`; all focused tests GREEN.
- [ ] **CP4 Gate**: Full backend regression (690+ tests), Alembic zero drift, frontend build passing, independent review completed.
