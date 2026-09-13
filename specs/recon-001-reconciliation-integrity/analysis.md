# Architectural & Consistency Analysis: Bank Reconciliation Integrity (RECON-001)

## 1. Overview

This analysis evaluates the consistency of the proposed RECON-001 solution against the repository Constitution, accounting principles, multi-tenant boundaries, and database performance requirements.

---

## 2. Comparison: Current State vs. Target State

| Dimension | Current Implementation (Defective) | Target Implementation (RECON-001) | Rationale / Authority |
| :--- | :--- | :--- | :--- |
| **Statement Line Cardinality** | 1:N (Multiple reconciliations allowed per `BankStatementLine`) | **1:1 Strictly** (At most 1 active reconciliation per line) | Business contract: statement lines represent single external events. |
| **Target Reuse Cardinality** | 1:N (Multiple statement lines can claim the same target) | **1:1 Strictly** (A target can participate in at most 1 reconciliation) | Double-counting ledger cash falsifies cash completeness. |
| **Target Discriminator** | 0 to 3 targets simultaneously allowed (all null or all set) | **Exactly 1 target** (`journal_line_id`, `money_movement_id`, or `transaction_id`) | Orphan matches without a target or polymorphic multi-targets violate domain integrity. |
| **Amount Integrity** | Arbitrary caller-controlled `matched_amount` accepted | **Derived / Verified Equality** (`matched_amount == bank_line == target`) | Protects against fraudulent or fabricated reconciliation amounts. |
| **Directional Matching** | Undefined; bank credit can be matched to credit | **Strict Accounting Parity** (Bank Credit -> Cash Debit; Bank Debit -> Cash Credit) | Standard banking and cash accounting convention. |
| **Auto-Match Behavior** | Reuses already-matched targets; intra-batch duplicate collisions | **Excludes reconciled targets**; tracks intra-batch allocations | Auto-match must never violate rules enforced in manual flow. |
| **Concurrency Defense** | Fails open under concurrent requests (unprotected SELECT -> INSERT) | **Pessimistic Row Lock (`FOR UPDATE`) + Database Unique Indexes** | Eliminates race condition window in concurrent API requests. |
| **Database Schema** | Non-unique indexes; no check constraints | **Partial Unique Indexes + Discriminator/Positive Check Constraints** | Defense-in-depth: database guarantees fail-closed invariants. |
| **Dashboard Calculation** | Synthetic subtraction (`total_book - matched_bank`) | **Direct Unreconciled Query** (`LEFT JOIN bank_reconciliations ... WHERE br.id IS NULL`) | Accurately reports real unreconciled book cash without mathematical distortion. |
| **Historical Data Safety** | Unchecked schema updates risk breaking or silently deleting rows | **Fail-Closed Migration Preflight** (Aborts on duplicates; no silent deletes) | Prevents unreviewed mutation or corruption of historical data. |
| **Tenant Isolation** | Checked in service layer (FIN-P1-105) | **Preserved 100%** (Cross-tenant UUIDs fail closed with 404) | Constitution Principle II: Multi-Tenant Strict Separation. |
| **Actor & Role Auth** | Enforced via AUTHZ-001 | **Preserved 100%** (`ADMIN`, `MANAGER`, `OPERATOR` required) | Constitution Principle IV: Access Control & Provenance. |
| **Double-Entry Ledger** | Untouched | **Untouched 100%** (Zero modifications to journal posting or balances) | Constitution Principle I: Double-Entry Ledger Invariance. |

---

## 3. Database Constraint & Performance Analysis

### 3.1 Partial Unique Indexes vs Standard Unique Constraints
In PostgreSQL, `journal_line_id`, `money_movement_id`, and `transaction_id` are nullable foreign keys.
- A standard unique constraint `UNIQUE (journal_line_id)` in standard SQL treats NULLs as distinct (unless `NULLS NOT DISTINCT` is used).
- A **Partial Unique Index** (`WHERE <column> IS NOT NULL`) offers substantial benefits:
  1. Only indexes rows that contain values, reducing index size and maintenance overhead.
  2. Unambiguously enforces uniqueness for non-null keys across all PostgreSQL versions.
  3. Prevents indexing NULL target entries.
- For `statement_line_id`, which is `NOT NULL`, a partial unique index on active matches (`WHERE status = 'MATCHED'`) or a unique constraint on `statement_line_id` guarantees that no statement line is matched twice.

### 3.2 Check Constraint Portability
The target discriminator check constraint:
```sql
CHECK (
    (CASE WHEN journal_line_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN money_movement_id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN transaction_id IS NOT NULL THEN 1 ELSE 0 END) = 1
)
```
- Fully compliant with ANSI SQL standards.
- Supported seamlessly across PostgreSQL and SQLite (used in fast unit test environments).
- Prevents zero-target phantom reconciliations and multi-target collisions.

---

## 4. Risk Assessment & Mitigations

1. **Risk: Legacy Unit Tests Failing Due to New Invariants**
   - *Impact*: Legacy unit test `test_cash_completeness_dashboard_and_reconciliation` created a reconciliation record with no targets (`journal_line_id=None`, `money_movement_id=None`, `transaction_id=None`).
   - *Mitigation*: In CP3, update this test fixture to supply a valid same-tenant target, ensuring it tests true reconciliation semantics.
2. **Risk: Migration Failure on Dirty Historical Data**
   - *Impact*: If a production database contains existing duplicate reconciliations, applying unique indexes directly crashes the migration.
   - *Mitigation*: Migration `024` implements a fail-closed preflight inspection. If violations exist, it halts cleanly before schema mutation, reporting the exact anomaly count for explicit manual review.
3. **Risk: Concurrency Bottlenecks on Payment Accounts**
   - *Impact*: Coarse table locks could serialize all reconciliation across the organization.
   - *Mitigation*: Use row-level locking strictly on the targeted `BankStatementLine` (`select(...).with_for_update()`). Other lines and accounts proceed concurrently without blocking.
