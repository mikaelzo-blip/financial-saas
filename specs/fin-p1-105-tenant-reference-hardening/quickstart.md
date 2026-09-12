# Quickstart Guide: FIN-P1-105

**Feature**: FIN-P1-105 — Tenant Ownership Validation for Supplied Foreign UUID References  
**Branch**: `hermes/fin-p1-105-tenant-reference-hardening`  

---

## 1. Environment Verification

Ensure the working tree is on the dedicated remediation branch and virtual environment is active:

```bash
git branch --show-current
# Expected: hermes/fin-p1-105-tenant-reference-hardening

git status
# Expected: working tree clean (or untracked specs/ only)
```

---

## 2. Checkpoint Execution Commands

### Checkpoint 1: RED Reproduction
To verify the initial reproduction failures before implementation:

```bash
cd backend
.venv/Scripts/python -m pytest tests/security/test_fin_p1_105_tenant_reference_hardening.py -v
```

### Checkpoint 2: Core Entity Hardening Verification
After implementing CP2 (`ProjectService` and `FixedAssetService`):

```bash
cd backend
.venv/Scripts/python -m pytest tests/security/test_fin_p1_105_tenant_reference_hardening.py -k "project or fixed_asset" -v
.venv/Scripts/python -m pytest tests/unit/test_fixed_asset_service.py tests/integration/test_project_service.py -v
```

### Checkpoint 3: Financial Linkage Hardening Verification
After implementing CP3 (`MoneyMovementService` and `BankReconciliationService`):

```bash
cd backend
.venv/Scripts/python -m pytest tests/security/test_fin_p1_105_tenant_reference_hardening.py -v
.venv/Scripts/python -m pytest tests/unit/test_bank_reconciliation_p2.py tests/integration/test_money_movement_reconciliation.py -v
```

### Checkpoint 4: Full Regression & Delivery Gates
Before opening PR:

```bash
cd backend
.venv/Scripts/python -m pytest tests/unit tests/integration tests/security -q
.venv/Scripts/python -m pytest tests/security/test_authz001_role_enforcement.py -v
.venv/Scripts/alembic current
.venv/Scripts/alembic check

cd ../frontend
npm test -- --run
npm run build
```

---

## 3. Key Invariant Quick Reference

| Entity | Field | Scoping Query |
|---|---|---|
| `Project` | `pic_user_id` | `User.organization_id == org_id` |
| `FixedAsset` | `vendor_id` | `Counterparty.organization_id == org_id` |
| `FixedAsset` | `document_id` | `Document.organization_id == org_id` |
| `Settlement` | `transaction_id` | `Transaction.organization_id == org_id` |
| `BankReconciliation` | `journal_line_id` | `JournalLine -> JournalEntry.organization_id == org_id` |
| `BankReconciliation` | `money_movement_id` | `MoneyMovement.organization_id == org_id` |
| `BankReconciliation` | `transaction_id` | `Transaction.organization_id == org_id` |
| `ProjectBudget` | `project_id` | `Project.organization_id == org_id` (Defense-in-depth) |
