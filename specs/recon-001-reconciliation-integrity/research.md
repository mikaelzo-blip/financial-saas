# Architectural Research: Bank Reconciliation Integrity (RECON-001)

## 1. Executive Summary

This research document analyzes the root causes, empirical evidence, domain contracts, concurrency vulnerabilities, and schema defense mechanisms for bank reconciliation in `financial-saas`. It provides the architectural foundation for the RECON-001 remediation.

All findings have been independently verified through source code inspection and empirical throwaway execution against the authoritative baseline (`e3c33ec3432ecff81c64be02012eaf51b55c5269`).

---

## 2. Baseline Architecture & Empirical Reproductions

### 2.1 Baseline State
- **Alembic Migration Chain**: Reached `023_seed_tenant_sequences_from_history.py`. Table `bank_reconciliations` was introduced in `017_p2_bank_reconciliation.py`.
- **Existing Schema**:
  ```sql
  CREATE TABLE bank_reconciliations (
      id UUID PRIMARY KEY,
      organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      statement_line_id UUID NOT NULL REFERENCES bank_statement_lines(id) ON DELETE CASCADE,
      journal_line_id UUID REFERENCES journal_lines(id) ON DELETE SET NULL,
      money_movement_id UUID REFERENCES money_movements(id) ON DELETE SET NULL,
      transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
      status VARCHAR(50) NOT NULL DEFAULT 'MATCHED',
      matched_amount NUMERIC(18, 2) NOT NULL,
      match_rule VARCHAR(100) NOT NULL,
      notes TEXT,
      matched_at TIMESTAMP NOT NULL DEFAULT now(),
      matched_by UUID REFERENCES users(id) ON DELETE SET NULL
  );
  ```
- **Indexes**: Non-unique B-tree indexes exist on `organization_id`, `statement_line_id`, `journal_line_id`, `money_movement_id`, and `transaction_id`. There are **no unique constraints** or **check constraints**.

### 2.2 Empirical Probe Results
A throwaway test script (`probe_recon.py`) was executed against the domain models to confirm the audit findings:
1. **Probe A (Duplicate Statement Line Match)**:
   - *Test*: Called `match_manual` twice for the same statement line.
   - *Result*: Both calls succeeded (200 OK), persisting two separate `BankReconciliation` rows (`['f261503f-...', '04843626-...']`) for the exact same statement line.
   - *Conclusion*: Service fails open; duplicate matching of a statement line is fully reproducible.
2. **Probe B (Duplicate Target Reuse)**:
   - *Test*: Reconciled statement line 1 with `MoneyMovement` MM-001, then reconciled statement line 2 with the same `MoneyMovement` MM-001.
   - *Result*: Both persisted without error. Two reconciliations point to the same `money_movement_id`.
   - *Conclusion*: Service fails open; target reuse is fully reproducible.
3. **Probe C (Arbitrary Caller-Controlled Amount)**:
   - *Test*: Statement line had `credit=10,000,000.00`. Request provided `matched_amount=999,999,999.00`.
   - *Result*: Persisted `matched_amount=999,999,999.00` with zero validation.
   - *Conclusion*: API accepts fabricated financial numbers completely uncoupled from bank records.
4. **Probe D (Auto-Match Target Reuse)**:
   - *Test*: Imported two statement lines with identical amount and date matching a single `JournalLine`.
   - *Result*: `stats={'matched': 2, 'unmatched': 0}`, creating two reconciliation rows pointing to the same `JournalLine`.
   - *Conclusion*: Auto-match contains no target exclusion or intra-batch deduplication.
5. **Probe E (Dashboard Distortion)**:
   - *Test*: Observed dashboard calculations after duplicate matches.
   - *Result*: `matched_amount` escalated to 27M on 22M total bank inflow; `unmatched_book` collapsed to `0.00` because the formula `max(0, total_book - matched_amount)` subtracted inflated bank matches from ledger cash.
   - *Conclusion*: Reporting logic is distorted and untruthful under non-1:1 matching.

---

## 3. Financial Domain & Amount Semantics

### 3.1 Sign & Directional Conventions
In commercial banking (Indonesian standard practice and banking APIs):
- **Bank Statement Line**:
  - `credit > 0`: Inflow (cash deposit, transfer in). Increases bank account balance.
  - `debit > 0`: Outflow (cash withdrawal, vendor payment). Decreases bank account balance.
  - Authoritative amount: `line_amount = line.credit if line.credit > 0 else line.debit`.
- **Journal Line (Cash/Bank Asset Account)**:
  - Cash is an Asset account (`AccountType.ASSET`, normal balance `DEBIT`).
  - Cash Inflow increases Asset -> recorded as **DEBIT** (`JournalLine.debit_amount > 0`).
  - Cash Outflow decreases Asset -> recorded as **CREDIT** (`JournalLine.credit_amount > 0`).
  - Check constraint `ck_jl_one_sided_amount` ensures strictly one side is non-zero.
  - Comparable amount:
    - If bank line is inflow (`credit > 0`): Target comparable amount is `journal_line.debit_amount`. (Must have `credit_amount == 0`).
    - If bank line is outflow (`debit > 0`): Target comparable amount is `journal_line.credit_amount`. (Must have `debit_amount == 0`).
- **Money Movement**:
  - `amount: Numeric(15, 2)` (always positive).
  - `direction: MovementDirection`:
    - `IN`: Inflow (matches bank `credit > 0`).
    - `OUT`: Outflow (matches bank `debit > 0`).
  - Comparable amount: `money_movement.amount`.
- **Transaction**:
  - `amount: Numeric(18, 2)` (always positive).
  - Comparable amount: `transaction.amount`.

### 3.2 Canonical Amount Integrity Rule
In a full reconciliation model:
```text
matched_amount == bank_line_amount == target_amount
```
The caller cannot override or dictate `matched_amount`. The service must derive `matched_amount` directly from `bank_line_amount` and verify that `target_amount == bank_line_amount`.

---

## 4. Concurrency & Race Condition Analysis

### 4.1 Vulnerability of Service-Only Validation
If reconciliation validation relies solely on application logic:
```python
# Thread A and Thread B simultaneously:
existing = await session.scalar(select(BankReconciliation).where(statement_line_id == line_id))
if existing:
    raise DuplicateEntityException(...)
session.add(BankReconciliation(...))
await session.commit()
```
Under concurrent execution:
1. Thread A executes `SELECT` -> returns None.
2. Thread B executes `SELECT` -> returns None.
3. Thread A executes `INSERT` and commits.
4. Thread B executes `INSERT` and commits.
Both requests succeed, creating two active reconciliation records for the same bank statement line or target.

### 4.2 Required Multi-Tier Defense
1. **Tier 1: Service-Layer Row Locking**:
   - When initiating a match (manual or auto-match), acquire a pessimistic write lock on the `BankStatementLine`:
     ```python
     line = await session.scalar(
         select(BankStatementLine)
         .where(BankStatementLine.id == req.statement_line_id, BankStatementLine.organization_id == org_id)
         .with_for_update()
     )
     ```
   - This serializes concurrent attempts targeting the same bank statement line.
2. **Tier 2: Database Uniqueness Constraints (Fail-Closed Barrier)**:
   - For statement lines: `UNIQUE (statement_line_id)` on `bank_reconciliations`.
   - For nullable targets: Partial unique indexes in PostgreSQL:
     ```sql
     CREATE UNIQUE INDEX uq_bank_reconciliations_journal_line
     ON bank_reconciliations (journal_line_id)
     WHERE journal_line_id IS NOT NULL;

     CREATE UNIQUE INDEX uq_bank_reconciliations_money_movement
     ON bank_reconciliations (money_movement_id)
     WHERE money_movement_id IS NOT NULL;

     CREATE UNIQUE INDEX uq_bank_reconciliations_transaction
     ON bank_reconciliations (transaction_id)
     WHERE transaction_id IS NOT NULL;
     ```
   - If a race bypasses service memory, PostgreSQL raises `23505` (`UniqueViolation`), immediately poisoning the transaction and preventing corruption.

---

## 5. Historical Data Detection & Migration Safety

### 5.1 Historical Preflight Query Concept
Before applying unique indexes or check constraints in Alembic, a preflight check must inspect existing rows in `bank_reconciliations`:

```sql
-- 1. Duplicate Statement Lines
SELECT statement_line_id, COUNT(*)
FROM bank_reconciliations
GROUP BY statement_line_id
HAVING COUNT(*) > 1;

-- 2. Duplicate Journal Lines
SELECT journal_line_id, COUNT(*)
FROM bank_reconciliations
WHERE journal_line_id IS NOT NULL
GROUP BY journal_line_id
HAVING COUNT(*) > 1;

-- 3. Duplicate Money Movements
SELECT money_movement_id, COUNT(*)
FROM bank_reconciliations
WHERE money_movement_id IS NOT NULL
GROUP BY money_movement_id
HAVING COUNT(*) > 1;

-- 4. Duplicate Transactions
SELECT transaction_id, COUNT(*)
FROM bank_reconciliations
WHERE transaction_id IS NOT NULL
GROUP BY transaction_id
HAVING COUNT(*) > 1;

-- 5. Multi-Target Rows (more than one target FK populated)
SELECT id
FROM bank_reconciliations
WHERE (
    CASE WHEN journal_line_id IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN money_movement_id IS NOT NULL THEN 1 ELSE 0 END +
    CASE WHEN transaction_id IS NOT NULL THEN 1 ELSE 0 END
) > 1;

-- 6. Zero-Target Rows (all target FKs NULL)
SELECT id
FROM bank_reconciliations
WHERE journal_line_id IS NULL AND money_movement_id IS NULL AND transaction_id IS NULL;

-- 7. Amount Discrepancies
SELECT r.id, r.matched_amount, bsl.debit, bsl.credit
FROM bank_reconciliations r
JOIN bank_statement_lines bsl ON r.statement_line_id = bsl.id
WHERE r.matched_amount != CASE WHEN bsl.credit > 0 THEN bsl.credit ELSE bsl.debit END;

-- 8. Non-Positive Amounts (CHECK matched_amount > 0)
SELECT id, matched_amount
FROM bank_reconciliations
WHERE matched_amount <= 0;
```

### 5.2 Migration Preflight Policy
- If any violations are detected, the Alembic migration MUST abort with a descriptive error message stating the count and category of invalid rows.
- The migration MUST NOT execute silent `DELETE` or arbitrary winner-selection (`keep oldest` / `keep newest`). Historical data remediation requires explicit, auditable business approval.
- In offline SQL mode (`as_sql=True`), preflight queries must safely no-op to allow script generation in CI.

---

## 6. Dashboard Correction Analysis

### 6.1 Current Formula Breakdown
In `BankReconciliationService.get_cash_completeness_dashboard`:
```python
total_book_cash = await self.session.scalar(jl_query) or Decimal("0.00")
unmatched_book = max(Decimal("0.00"), total_book_cash - matched_amount)
```
**Defects**:
1. `matched_amount` represents bank statement lines matched to ANY target (including MoneyMovements or unposted Transactions). Subtracting bank matches from `JournalLine` cash produces synthetic, meaningless results.
2. If bank lines are duplicated or matched to multiple targets, `matched_amount` exceeds `total_book_cash`, forcing `unmatched_book` to `0.00` and concealing unreconciled journal lines.

### 6.2 Authoritative Expected Formula
Unmatched book cash represents actual cash `JournalLine`s that have not been reconciled:
```sql
SELECT COALESCE(SUM(jl.debit_amount + jl.credit_amount), 0.00)
FROM journal_lines jl
JOIN journal_entries je ON jl.journal_entry_id = je.id
LEFT JOIN bank_reconciliations br ON jl.id = br.journal_line_id
WHERE je.organization_id = :org_id
  AND jl.payment_account_id = :payment_account_id
  AND br.id IS NULL;
```
This directly computes the real unreconciled book volume without synthetic arithmetic.
