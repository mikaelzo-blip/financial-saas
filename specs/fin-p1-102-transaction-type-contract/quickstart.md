# Developer Quickstart: FIN-P1-102 Transaction Processing Capabilities

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Branch**: `hermes/fin-p1-102-transaction-type-contract`

---

## 1. Running the Test Suite

All commands are run from the repository root using the declared Python toolchain:

### Run Focused Capability Test Suite
```bash
python -m pytest backend/tests/unit/test_fin_p1_102_transaction_capabilities.py -v
```

### Run AUTHZ-001 Security Regression
```bash
python -m pytest backend/tests/security/test_authz001_role_enforcement.py -v
```

### Run Accounting Engine & Reversal Regression
```bash
python -m pytest backend/tests/unit/test_accounting_engine.py backend/tests/unit/test_reversals.py -v
```

---

## 2. Capability Invariant Verification

Verify the 37-type capability contract directly via Python:

```python
from src.models.enums import TransactionType
from src.services.posting_rules import PostingRuleRegistry
from src.services.processing_policy_service import ProcessingPolicyService

# 1. Verify total enum members
assert len(TransactionType) == 37

# 2. Verify posting rule supported types
assert len(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES) == 20

# 3. Verify special workflow types
assert PostingRuleRegistry.SPECIAL_WORKFLOW_TYPES == frozenset({TransactionType.REVERSAL})

# 4. Verify AUTO_SAFE types is a subset of supported types
assert ProcessingPolicyService.AUTO_SAFE_TYPES.issubset(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)
assert TransactionType.PETTY_CASH_EXPENSE not in ProcessingPolicyService.AUTO_SAFE_TYPES

# 5. Verify non-overlapping sets
assert not PostingRuleRegistry.SPECIAL_WORKFLOW_TYPES.intersection(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)
```

---

## 3. Behavioral API Verification Examples

### Generic Ingestion of Unsupported Type (Rejection)
```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_type": "OTHER_EXPENSE",
    "transaction_date": "2026-09-12",
    "amount": "1000000.00",
    "description": "Probe unsupported type"
  }'
```
**Expected Response**: `422 Unprocessable Content`
```json
{
  "success": false,
  "error": {
    "code": "INVARIANT_VIOLATION",
    "message": "Transaction type 'OTHER_EXPENSE' is not supported by the generic posting workflow.",
    "details": {
      "transaction_type": "OTHER_EXPENSE",
      "reason": "NO_POSTING_RULE"
    }
  }
}
```

### Generic Ingestion of REVERSAL (Rejection)
```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_type": "REVERSAL",
    "transaction_date": "2026-09-12",
    "amount": "1000000.00",
    "description": "Probe reversal generic intake"
  }'
```
**Expected Response**: `422 Unprocessable Content`
```json
{
  "success": false,
  "error": {
    "code": "INVARIANT_VIOLATION",
    "message": "Transaction type 'REVERSAL' is restricted to dedicated domain workflows and cannot be created through generic ingestion.",
    "details": {
      "transaction_type": "REVERSAL",
      "reason": "SPECIAL_WORKFLOW_ONLY"
    }
  }
}
```

### Dedicated Reversal Execution (Success)
```bash
curl -X POST http://localhost:8000/api/v1/transactions/<TRANSACTION_ID>/reverse \
  -H "Authorization: Bearer <MANAGER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Salah pencatatan akun biaya"
  }'
```
**Expected Response**: `201 Created` (Reversal transaction created in `POSTED` status).
