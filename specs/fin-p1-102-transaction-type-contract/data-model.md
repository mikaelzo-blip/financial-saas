# Data Model & Schema Specification: FIN-P1-102

**Feature**: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
**Baseline Commit**: `befb74a9b60ab746e8ac779accccc151c5552047`

---

## 1. Database Schema & Migration Status

- **Database Migrations Required**: **NONE (0)**.
- **PostgreSQL Enum Modifications**: **NONE**. The PostgreSQL enum `transaction_type` retains all 37 values.
- **Table Alterations**: **NONE**.
- **Constraint Changes**: **NONE**.
- **Historical Data Migrations**: **NONE**. Existing rows in `transactions` are not updated or deleted.

---

## 2. In-Memory Domain Models & Classifications

### `TransactionType` Enum (`backend/src/models/enums.py`)
All 37 enum values remain untouched:
```python
class TransactionType(str, Enum):
    DIRECT_PURCHASE = "DIRECT_PURCHASE"
    VENDOR_BILL = "VENDOR_BILL"
    PAY_VENDOR_BILL = "PAY_VENDOR_BILL"
    SUBCONTRACTOR_BILL = "SUBCONTRACTOR_BILL"
    PAY_SUBCONTRACTOR = "PAY_SUBCONTRACTOR"
    VENDOR_ADVANCE = "VENDOR_ADVANCE"
    SETTLE_VENDOR_ADVANCE = "SETTLE_VENDOR_ADVANCE"
    EMPLOYEE_ADVANCE = "EMPLOYEE_ADVANCE"
    EMPLOYEE_SETTLEMENT = "EMPLOYEE_SETTLEMENT"
    CUSTOMER_ADVANCE = "CUSTOMER_ADVANCE"
    REIMBURSEMENT = "REIMBURSEMENT"
    PAY_REIMBURSEMENT = "PAY_REIMBURSEMENT"
    PETTY_CASH_EXPENSE = "PETTY_CASH_EXPENSE"
    TOPUP_PETTY_CASH = "TOPUP_PETTY_CASH"
    RETURN_PETTY_CASH = "RETURN_PETTY_CASH"
    BANK_TO_CASH = "BANK_TO_CASH"
    CASH_TO_BANK = "CASH_TO_BANK"
    INTERBANK_TRANSFER = "INTERBANK_TRANSFER"
    ASSET_PURCHASE = "ASSET_PURCHASE"
    FIXED_ASSET_DEPRECIATION = "FIXED_ASSET_DEPRECIATION"
    INVENTORY_PURCHASE = "INVENTORY_PURCHASE"
    INVENTORY_USAGE = "INVENTORY_USAGE"
    CUSTOMER_INVOICE = "CUSTOMER_INVOICE"
    CUSTOMER_PAYMENT = "CUSTOMER_PAYMENT"
    RETENTION_RELEASE = "RETENTION_RELEASE"
    REVENUE_RECOGNITION = "REVENUE_RECOGNITION"
    CUSTOMER_REFUND = "CUSTOMER_REFUND"
    VENDOR_REFUND = "VENDOR_REFUND"
    OWNER_CONTRIBUTION = "OWNER_CONTRIBUTION"
    OWNER_WITHDRAWAL = "OWNER_WITHDRAWAL"
    LOAN_RECEIVED = "LOAN_RECEIVED"
    LOAN_PAYMENT = "LOAN_PAYMENT"
    BANK_CHARGE = "BANK_CHARGE"
    OTHER_INCOME = "OTHER_INCOME"
    OTHER_EXPENSE = "OTHER_EXPENSE"
    JOURNAL_ADJUSTMENT = "JOURNAL_ADJUSTMENT"
    REVERSAL = "REVERSAL"
```

### Capability Sets on `PostingRuleRegistry` (`backend/src/services/posting_rules.py`)
```python
POSTING_RULE_SUPPORTED_TYPES: frozenset[TransactionType] = frozenset({
    TransactionType.DIRECT_PURCHASE,
    TransactionType.VENDOR_BILL,
    TransactionType.PAY_VENDOR_BILL,
    TransactionType.SUBCONTRACTOR_BILL,
    TransactionType.PAY_SUBCONTRACTOR,
    TransactionType.VENDOR_ADVANCE,
    TransactionType.SETTLE_VENDOR_ADVANCE,
    TransactionType.CUSTOMER_INVOICE,
    TransactionType.RETENTION_RELEASE,
    TransactionType.CUSTOMER_PAYMENT,
    TransactionType.CUSTOMER_ADVANCE,
    TransactionType.BANK_TO_CASH,
    TransactionType.CASH_TO_BANK,
    TransactionType.INTERBANK_TRANSFER,
    TransactionType.JOURNAL_ADJUSTMENT,
    TransactionType.OWNER_CONTRIBUTION,
    TransactionType.OWNER_WITHDRAWAL,
    TransactionType.BANK_CHARGE,
    TransactionType.FIXED_ASSET_DEPRECIATION,
    TransactionType.ASSET_PURCHASE,
})

SPECIAL_WORKFLOW_TYPES: frozenset[TransactionType] = frozenset({
    TransactionType.REVERSAL,
})
```

### Remediated `AUTO_SAFE_TYPES` on `ProcessingPolicyService` (`backend/src/services/processing_policy_service.py`)
```python
AUTO_SAFE_TYPES: Set[TransactionType] = {
    TransactionType.DIRECT_PURCHASE,
    TransactionType.BANK_CHARGE,
}
```
*Note*: `PETTY_CASH_EXPENSE` is removed from `AUTO_SAFE_TYPES`.

---

## 3. Invariant Verification Equation
The domain model enforces:
```python
assert AUTO_SAFE_TYPES.issubset(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)
assert not SPECIAL_WORKFLOW_TYPES.intersection(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)
assert len(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES) == 20
assert len(PostingRuleRegistry.SPECIAL_WORKFLOW_TYPES) == 1
assert len(TransactionType) == 37
```
