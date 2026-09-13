# Data Model: Bank Reconciliation Subsystem (RECON-001)

## 1. Entity-Relationship Overview

```text
       +--------------------+
       |   organizations    |
       +---------+----------+
                 | 1:N
                 +-----------------------+-----------------------+
                 |                       |                       |
                 v                       v                       v
      +----------------------+ +--------------------+ +--------------------+
      |   payment_accounts   | |   journal_lines    | |  money_movements   |
      +----------+-----------+ +---------+----------+ +----------+---------+
                 | 1:N                   |                       |
                 v                       |                       |
   +---------------------------+         |                       |
   |   bank_statement_imports  |         |                       |
   +-------------+-------------+         |                       |
                 | 1:N                   |                       |
                 v                       |                       |
   +---------------------------+         |                       |
   |   bank_statement_lines    |         |                       |
   +-------------+-------------+         |                       |
                 | 1:1                   | 1:1                   | 1:1
                 v                       v                       v
      +----------------------------------------------------------------+
      |                      bank_reconciliations                      |
      +----------------------------------------------------------------+
                                         ^
                                         | 1:1
                               +---------+----------+
                               |    transactions    |
                               +--------------------+
```

---

## 2. Table Specifications

### 2.1 `bank_statement_lines`
| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | UUID | NO | PRIMARY KEY | Unique statement line identifier |
| `import_id` | UUID | NO | FK `bank_statement_imports(id)` ON DELETE CASCADE | Owning statement import |
| `organization_id` | UUID | NO | FK `organizations(id)` ON DELETE CASCADE | Tenant isolation |
| `line_number` | INTEGER | NO | | Row sequence within statement |
| `transaction_date`| DATE | NO | | Date of bank mutation |
| `description` | TEXT | NO | | Bank transaction description |
| `debit` | NUMERIC(18, 2) | NO | DEFAULT 0.00, CHECK (debit >= 0) | Outflow amount |
| `credit` | NUMERIC(18, 2) | NO | DEFAULT 0.00, CHECK (credit >= 0) | Inflow amount |
| `balance` | NUMERIC(18, 2) | YES | | Running balance reported by bank |
| `reference` | VARCHAR(255) | YES | | Bank reference or transaction number |
| `counterparty_name`| VARCHAR(255)| YES | | Third-party name from statement |
| `reconciliation_status`| VARCHAR(50)| NO | DEFAULT 'UNMATCHED_BANK' | `UNMATCHED_BANK`, `MATCHED` |

### 2.2 `bank_reconciliations` (Hardened Schema)
| Column | Type | Nullable | Constraints & Defaults | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | UUID | NO | PRIMARY KEY | Unique reconciliation record ID |
| `organization_id` | UUID | NO | FK `organizations(id)` ON DELETE CASCADE | Tenant isolation |
| `statement_line_id`| UUID | NO | FK `bank_statement_lines(id)` ON DELETE CASCADE | Bank statement line |
| `journal_line_id` | UUID | YES | FK `journal_lines(id)` ON DELETE SET NULL | Book target: Journal line |
| `money_movement_id`| UUID | YES | FK `money_movements(id)` ON DELETE SET NULL | Book target: Money movement |
| `transaction_id` | UUID | YES | FK `transactions(id)` ON DELETE SET NULL | Book target: Transaction |
| `status` | VARCHAR(50) | NO | DEFAULT 'MATCHED' | Reconciliation status |
| `matched_amount` | NUMERIC(18, 2) | NO | CHECK (matched_amount > 0) | Authoritative reconciled amount |
| `match_rule` | VARCHAR(100) | NO | | Rule identifier |
| `notes` | TEXT | YES | | Optional audit remarks |
| `matched_at` | TIMESTAMP | NO | DEFAULT now() | Timestamp of match execution |
| `matched_by` | UUID | YES | FK `users(id)` ON DELETE SET NULL | User who executed manual match |

---

## 3. Database Indexes & Constraints (Migration 024)

### 3.1 Unique Indexes
1. `uq_bank_reconciliations_statement_line`:
   - Enforces 1:1 active matching for statement lines while allowing potential future unmatch/cancellation transitions.
   ```sql
   CREATE UNIQUE INDEX uq_bank_reconciliations_statement_line
   ON bank_reconciliations (statement_line_id)
   WHERE status = 'MATCHED';
   ```
2. `uq_bank_reconciliations_journal_line`:
   - Prevents duplicate reuse of a `JournalLine`.
   ```sql
   CREATE UNIQUE INDEX uq_bank_reconciliations_journal_line
   ON bank_reconciliations (journal_line_id)
   WHERE journal_line_id IS NOT NULL;
   ```
3. `uq_bank_reconciliations_money_movement`:
   - Prevents duplicate reuse of a `MoneyMovement`.
   ```sql
   CREATE UNIQUE INDEX uq_bank_reconciliations_money_movement
   ON bank_reconciliations (money_movement_id)
   WHERE money_movement_id IS NOT NULL;
   ```
4. `uq_bank_reconciliations_transaction`:
   - Prevents duplicate reuse of a `Transaction`.
   ```sql
   CREATE UNIQUE INDEX uq_bank_reconciliations_transaction
   ON bank_reconciliations (transaction_id)
   WHERE transaction_id IS NOT NULL;
   ```

*Dialect Support*: In the SQLAlchemy `BankReconciliation` model, each partial index must declare both `postgresql_where` and `sqlite_where` to enforce identical partial indexing across PostgreSQL and in-memory SQLite (`sqlite+aiosqlite`) test runners.

### 3.2 Check Constraints
1. `ck_bank_recon_exactly_one_target`:
   - Enforces that exactly one polymorphic target column is populated.
   ```sql
   CHECK (
       (CASE WHEN journal_line_id IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN money_movement_id IS NOT NULL THEN 1 ELSE 0 END +
        CASE WHEN transaction_id IS NOT NULL THEN 1 ELSE 0 END) = 1
   )
   ```
   *Interaction with ON DELETE SET NULL*: Migration 017 established target foreign keys with `ON DELETE SET NULL`. If an underlying target entity is deleted in the database, setting the foreign key to NULL will cause this check constraint (sum = 1) to fail with a `CheckViolation`, effectively upgrading the behavior to `RESTRICT` and preventing orphan reconciliation records.

2. `ck_bank_recon_matched_amount_positive`:
   - Enforces non-zero, positive monetary amount.
   ```sql
   CHECK (matched_amount > 0)
   ```

---

## 4. State Lifecycle

```text
[BankStatementLine: UNMATCHED_BANK]
                |
                | (Auto-Match OR Manual Match)
                v
[BankStatementLine: MATCHED] <---- (1:1 Active Reference) ----> [BankReconciliation: MATCHED]
                                                                        |
                                                                        +--> Exactly 1 Target (JL, MM, TX)
```
- In the current full-match product scope, transitions are terminal upon reconciliation.
- Future unmatch capabilities (out of scope for RECON-001) would transition `BankStatementLine` back to `UNMATCHED_BANK` and delete or cancel the `BankReconciliation` record.
