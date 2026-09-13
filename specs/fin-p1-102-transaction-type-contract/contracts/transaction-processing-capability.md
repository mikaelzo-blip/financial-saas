# Transaction Processing Capability Contract

**Contract ID**: `FIN-P1-102-CONTRACT`
**Authoritative Source**: `src.services.posting_rules.PostingRuleRegistry`
**Status**: DRAFT (FIN-P1-102 Spec Kit)
**Applies To**: `TransactionService`, document API routes, `ProcessingPolicyService`, `AccountingEngine`, `ReversalService`

---

## 1. Terminology & Conceptual Boundaries

| Term | Definition | Contract Status |
|---|---|---|
| **Generic Ingestion** | Transaction creation via standard candidate intake (`POST /api/v1/transactions`, document approval, or candidate correction). | Restricted exclusively to `POSTING_RULE_SUPPORTED` types. |
| **Posting-Rule Supported** | Types possessing a deterministic, balanced double-entry journal rule implemented in `PostingRuleRegistry.generate_journal_legs`. | Exactly 20 types. Executable through `AccountingEngine`. |
| **Special-Workflow Only** | Types valid within dedicated domain services that manage specialized lifecycle, parent linkage, and offsetting entries. | Exactly 1 type (`REVERSAL`). Rejected at generic ingestion. |
| **Currently Unsupported** | Types defined in `TransactionType` enum whose debit/credit accounting policy has not been established by company policy. | Exactly 16 types. Strictly rejected at generic intake (422). |
| **Auto-Safe** | Transaction types eligible for automated posting without mandatory human review when zero review flags are present. | Must be a strict subset of `GENERIC_INGESTIBLE`. Exactly 2 types (`DIRECT_PURCHASE`, `BANK_CHARGE`). |

---

## 2. Authoritative Capability Source

`PostingRuleRegistry` in `backend/src/services/posting_rules.py` is the **single canonical source of truth** for generic transaction processing capability.

### Mathematical Invariant
$$\text{AUTO\_SAFE\_TYPES} \subseteq \text{GENERIC\_INGESTIBLE\_TYPES} \equiv \text{POSTING\_RULE\_SUPPORTED\_TYPES}$$
$$\text{SPECIAL\_WORKFLOW\_TYPES} \cap \text{GENERIC\_INGESTIBLE\_TYPES} = \emptyset$$
$$\text{ALL\_TYPES} = \text{POSTING\_RULE\_SUPPORTED} \cup \text{SPECIAL\_WORKFLOW} \cup \text{CURRENTLY\_UNSUPPORTED} \quad (20 + 1 + 16 = 37)$$

---

## 3. Authoritative 37-Type Classification Matrix

| # | TransactionType | Posting Rule | Special Workflow | Generic Ingestible | Auto-Safe | Generic Create API | Doc Correction | Generic Post | Dedicated Workflow | Expected Contract | Test ID |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|---|
| 1 | `DIRECT_PURCHASE` | YES | NO | YES | YES | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-001 |
| 2 | `VENDOR_BILL` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-002 |
| 3 | `PAY_VENDOR_BILL` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-003 |
| 4 | `SUBCONTRACTOR_BILL` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-004 |
| 5 | `PAY_SUBCONTRACTOR` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-005 |
| 6 | `VENDOR_ADVANCE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-006 |
| 7 | `SETTLE_VENDOR_ADVANCE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-007 |
| 8 | `EMPLOYEE_ADVANCE` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-001 |
| 9 | `EMPLOYEE_SETTLEMENT` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-002 |
| 10 | `CUSTOMER_ADVANCE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-008 |
| 11 | `REIMBURSEMENT` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-003 |
| 12 | `PAY_REIMBURSEMENT` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-004 |
| 13 | `PETTY_CASH_EXPENSE` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Contradiction Removed | TC-UNSUP-005 |
| 14 | `TOPUP_PETTY_CASH` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-006 |
| 15 | `RETURN_PETTY_CASH` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-007 |
| 16 | `BANK_TO_CASH` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-009 |
| 17 | `CASH_TO_BANK` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-010 |
| 18 | `INTERBANK_TRANSFER` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-011 |
| 19 | `ASSET_PURCHASE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-012 |
| 20 | `FIXED_ASSET_DEPRECIATION` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-013 |
| 21 | `INVENTORY_PURCHASE` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-008 |
| 22 | `INVENTORY_USAGE` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-009 |
| 23 | `CUSTOMER_INVOICE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-014 |
| 24 | `CUSTOMER_PAYMENT` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-015 |
| 25 | `RETENTION_RELEASE` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-016 |
| 26 | `REVENUE_RECOGNITION` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-010 |
| 27 | `CUSTOMER_REFUND` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-011 |
| 28 | `VENDOR_REFUND` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-012 |
| 29 | `OWNER_CONTRIBUTION` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-017 |
| 30 | `OWNER_WITHDRAWAL` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-018 |
| 31 | `LOAN_RECEIVED` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-013 |
| 32 | `LOAN_PAYMENT` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-014 |
| 33 | `BANK_CHARGE` | YES | NO | YES | YES | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-019 |
| 34 | `OTHER_INCOME` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-015 |
| 35 | `OTHER_EXPENSE` | NO | NO | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | N/A | Policy Blocked | TC-UNSUP-016 |
| 36 | `JOURNAL_ADJUSTMENT` | YES | NO | YES | NO | ALLOW (201) | ALLOW (200) | ALLOW (200) | N/A | Full Generic Posting | TC-GEN-020 |
| 37 | `REVERSAL` | NO | YES | NO | NO | REJECT (422) | REJECT (422) | REJECT (422) | ALLOW (201) | Dedicated Reversal Only | TC-REV-001 |

**Classification Summary**:
- Total `TransactionType` enum members: **37**
- Normal Posting Rule Supported: **20**
- Special Workflow Supported: **1** (`REVERSAL`)
- No Executable Posting Path / Unsupported: **16**
- Generically Ingestible: **20**
- Generically Rejected: **17** (16 unsupported + 1 `REVERSAL`)

---

## 4. Service Enforcement Points

### Gate 1: Generic Transaction Intake (`TransactionService.create_transaction`)
- **Boundary**: Initial entrypoint of `create_transaction`.
- **Validation**:
  ```python
  PostingRuleRegistry.validate_generic_ingestion(data.transaction_type)
  ```
- **Execution Position**: Evaluated before:
  - Allocation resolution & validation
  - Counterparty / payment account / project queries
  - Duplicate candidate heuristic checks
  - `generate_transaction_code` (preserves sequence number!)
  - `Transaction` entity instantiation
  - Database `flush()` / persistence
- **Behavior on Violation**: Raises `InvariantViolationException` -> HTTP 422 `INVARIANT_VIOLATION`. Zero DB rows written, zero sequence consumed.

### Gate 2: Document Correction (`correct_document` API route / `POST /api/v1/documents/{document_id}/corrections`)
- **Boundary**: Processing of `DocumentCorrectionRequest.changes["proposed_transaction_type"]`.
- **Validation**:
  ```python
  if validated.proposed_transaction_type is not None:
      PostingRuleRegistry.validate_generic_ingestion(validated.proposed_transaction_type)
  ```
- **Execution Position**: Before updating `document.candidate_transaction` JSON on disk.
- **Behavior on Violation**: Raises `InvariantViolationException` -> HTTP 422 `INVARIANT_VIOLATION`. Candidate is not modified to an unpostable type.

### Gate 3: Document Candidate Approval Defense-in-Depth (`approve_document_candidate`)
- **Boundary**: Prior to invoking `create_transaction`.
- **Call Graph**:
  `approve_document_candidate` (api/v1/documents.py)
  -> `TransactionService(session).create_transaction(...)` (primary gate)
  -> `AccountingEngine(session).post_transaction(...)`
- **Defense-in-Depth Guard**:
  ```python
  if not PostingRuleRegistry.is_generic_ingestible(candidate.proposed_transaction_type):
      raise InvariantViolationException(
          f"Candidate proposed transaction type '{candidate.proposed_transaction_type.value}' cannot be converted to an executable transaction.",
          details={"transaction_type": candidate.proposed_transaction_type.value}
      )
  ```
- **Behavior on Violation**: Fails before transaction code allocation, rolls back cleanly via `run_in_clean_transaction`.

---

## 5. Error Contract

When generic ingestion or candidate correction encounters a non-ingestible type, the API responds with:

- **HTTP Status**: `422 Unprocessable Content`
- **Error Code**: `INVARIANT_VIOLATION`
- **Exception Class**: `src.core.exceptions.InvariantViolationException`
- **Payload Contract**:
  ```json
  {
    "success": false,
    "error": {
      "code": "INVARIANT_VIOLATION",
      "message": "Transaction type '<TYPE>' is not supported by the generic posting workflow.",
      "details": {
        "transaction_type": "<TYPE>",
        "reason": "NO_POSTING_RULE" | "SPECIAL_WORKFLOW_ONLY"
      }
    }
  }
  ```

---

## 6. REVERSAL Dedicated-Flow Contract

- `TransactionType.REVERSAL` is a valid, production-supported business operation.
- However, `REVERSAL` requires:
  1. An existing `POSTED` transaction (`reversal_of_id`);
  2. Inverted journal legs directly cloned from the original journal entry;
  3. Status mutation of the source transaction to `REVERSED`;
  4. AR/AP allocation reversal and balance recalculation.
- Generic intake (`POST /transactions`) cannot provide these guarantees. Creating a `STAGED` reversal creates an unpostable dead-end.
- **Rule**:
  - `POST /transactions` with `REVERSAL` -> **422 INVARIANT_VIOLATION**
  - Document candidate correction to `REVERSAL` -> **422 INVARIANT_VIOLATION**
  - `POST /api/v1/transactions/{id}/reverse` via `ReversalService.reverse_transaction` -> **201 Created (Supported)**
  - `PostingRuleRegistry` must NOT add a pseudo posting rule for `REVERSAL`.

---

## 7. AUTO_SAFE Subset Invariant

In `ProcessingPolicyService`:
- Previously: `AUTO_SAFE_TYPES = {DIRECT_PURCHASE, PETTY_CASH_EXPENSE, BANK_CHARGE}`
- Flaw: `PETTY_CASH_EXPENSE` has no posting rule and no executable path.
- Remediation:
  - `PETTY_CASH_EXPENSE` is stripped from `AUTO_SAFE_TYPES`.
  - Authoritative set: `AUTO_SAFE_TYPES = {DIRECT_PURCHASE, BANK_CHARGE}`.
  - Startup / test assertion: `assert AUTO_SAFE_TYPES.issubset(PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES)`.

---

## 8. Historical Data Contract

- Existing rows in `transactions` with status `STAGED` and unsupported transaction types (created prior to FIN-P1-102 remediation) are **not altered, deleted, or migrated**.
- These rows remain as known historical dead-ends.
- No database migrations, data cleanup scripts, or deletion endpoints are introduced in this feature.
- Future remediation (e.g. administrative purge or cancellation workflow) is deferred to a dedicated feature if required.

---

## 9. Policy-Blocked Unsupported Type List

The following 16 types are explicitly blocked pending formal company accounting policy definitions:

1. `EMPLOYEE_ADVANCE` (Advance asset vs employee liability rules)
2. `EMPLOYEE_SETTLEMENT` (Advance settlement cutoff and tax withholding policy)
3. `REIMBURSEMENT` (Payable creation vs immediate payout policy)
4. `PAY_REIMBURSEMENT` (Settlement source and allocation matching)
5. `PETTY_CASH_EXPENSE` (Imprest vs fluctuating petty cash fund accounting)
6. `TOPUP_PETTY_CASH` (Disbursement to petty cash custodian)
7. `RETURN_PETTY_CASH` (Custodian excess return to operational bank)
8. `INVENTORY_PURCHASE` (Perpetual inventory asset account vs expense cutoff)
9. `INVENTORY_USAGE` (Cost of goods / project direct cost allocation)
10. `REVENUE_RECOGNITION` (BAST / percentage of completion accrual timing)
11. `CUSTOMER_REFUND` (Customer advance refund vs receivable credit balance)
12. `VENDOR_REFUND` (Vendor advance refund vs overpayment recovery)
13. `LOAN_RECEIVED` (Short-term vs long-term debt liability classification)
14. `LOAN_PAYMENT` (Principal reduction vs interest expense allocation)
15. `OTHER_INCOME` (Non-operational income COA accounts and taxability)
16. `OTHER_EXPENSE` (Non-operational expense COA accounts and deductibility)

Neither Hermes Coder nor any AI agent may invent debit/credit legs or COA mappings for these types.
