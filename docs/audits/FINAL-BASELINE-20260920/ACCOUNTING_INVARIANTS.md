# Global Accounting Invariants & Contract Verification Report

- **Audit Run ID:** `FINAL-BASELINE-20260920`
- **Git Commit SHA:** `26ab5affee58` (`26ab5af`)
- **Date:** 20 September 2026
- **Database Engine:** PostgreSQL 16 (Docker)
- **Status:** 100% INVARIANTS SATISFIED & ZERO DEFECTS

---

## 1. Global Double-Entry Sanity Check

Automated read-only verification executed against the live database:

| Invariant Verification Rule | Target Query / Assertion | Result | Evidence |
| :--- | :--- | :--- | :--- |
| **Unbalanced Journal Entries** | `SELECT COUNT(*) WHERE total_debit != total_credit` | **0** | All 28 posted journals strictly balanced |
| **Header vs Line Mismatch** | `HAVING je.total_debit != SUM(jl.debit) OR je.total_credit != SUM(jl.credit)` | **0** | Every journal header equals exact sum of lines |
| **Orphan Journal Lines** | `SELECT COUNT(*) FROM journal_lines LEFT JOIN journal_entries WHERE je.id IS NULL` | **0** | No orphan lines exist |
| **Duplicate Journals per Transaction** | `SELECT transaction_id GROUP BY transaction_id HAVING COUNT(*) > 1` | **0** | Exactly 1 journal per posted transaction |
| **Unlinked Journal Entries** | `SELECT COUNT(*) FROM journal_entries WHERE transaction_id IS NULL` | **0** | All 28 journals linked to source transactions |
| **Grand Ledger Debit vs Credit** | `SUM(total_debit) == SUM(total_credit)` | **SEIMBANG** | **Debet:** Rp 400.630.988,86<br>**Kredit:** Rp 400.630.988,86 |
| **Trial Balance Selisih (Seluruh Akun)** | `Total Mutasi Debet - Total Mutasi Kredit` | **Rp 0,00** | Terverifikasi di backend & live browser UI |

---

## 2. Reversal Invariant & Ledger Preservation

The application strictly implements **Immutable Ledger Accounting** via Reversals:
- Posted transactions and journal entries are **never physically deleted or updated**.
- Corrections produce a compensating reversal transaction (`REVERSAL`) with an opposite journal entry.
- All 9 reversal pairs in the database have been audited:

| Original Transaction | Type | Reversal Transaction | Compensating Journal | Net Balance Impact |
| :--- | :--- | :--- | :--- | :--- |
| `TRX-2026-000011` | `VENDOR_BILL` | `TRX-2026-000012` | `JE-2026-000012` | **Rp 0,00** (Akun 5101 & 2101) |
| `TRX-2026-000013` | `VENDOR_BILL` | `TRX-2026-000016` | `JE-2026-000016` | **Rp 0,00** (Akun 5101 & 2101) |
| `TRX-2026-000014` | `PAY_VENDOR_BILL` | `TRX-2026-000015` | `JE-2026-000015` | **Rp 0,00** (Akun 2101 & 1101) |
| `TRX-2026-000017` | `CUSTOMER_INVOICE`| `TRX-2026-000022` | `JE-2026-000022` | **Rp 0,00** (Akun 1201 & 4101) |
| `TRX-2026-000018` | `CUSTOMER_PAYMENT`| `TRX-2026-000021` | `JE-2026-000021` | **Rp 0,00** (Akun 1101 & 1201) |
| `TRX-2026-000019` | `CUSTOMER_PAYMENT`| `TRX-2026-000020` | `JE-2026-000020` | **Rp 0,00** (Akun 1101 & 1201) |
| `TRX-2026-000023` | `DIRECT_PURCHASE`  | `TRX-2026-000024` | `JE-2026-000024` | **Rp 0,00** (Akun 6199 & 1101) |
| `TRX-2026-000026` | `DIRECT_PURCHASE`  | `TRX-2026-000027` | `JE-2026-000027` | **Rp 0,00** (Akun 6103 & 1101) |
| `TRX-2026-000028` | `VENDOR_BILL` | `TRX-2026-000029` | `JE-2026-000028` | **Rp 0,00** (Akun 5101 & 2101) |

**Result:** Zero non-zero reversal pairs. Net financial balance across all reversed transactions is exactly Rp 0,00.

---

## 3. Cross-Journey Accounting Contracts

### Contract A: Vendor Bill (J1, J3, J8)
- **Posting Rule:** Dr 5101 (Harga Pokok Proyek) / Cr 2101 (Utang Usaha).
- **Invariants:** Total debit == total credit. Increases project cost and increases AP liability.
- **Verification:** Verified on `TRX-2026-000011`, `TRX-2026-000013`, `TRX-2026-000028`. Sub-ledger record created in `vendor_bills`.

### Contract B: Vendor Payment (J3)
- **Posting Rule:** Dr 2101 (Utang Usaha) / Cr 1101 (Kas dan Bank).
- **Invariants:** Total debit == total credit. Decreases AP liability and decreases cash/bank.
- **No Duplicate Expense Rule:** Payment must **NEVER** debit 5xxx or 6xxx expense accounts.
- **Verification:** Zero AP payment transactions touch expense accounts. Expense remains recognized exclusively by the Vendor Bill.

### Contract C: Customer Invoice (J4)
- **Posting Rule:** Dr 1201 (Piutang Usaha) / Cr 4101 (Pendapatan Proyek dan Jasa).
- **Invariants:** Total debit == total credit. Increases AR asset and recognizes project revenue.
- **Verification:** Verified on `TRX-2026-000017`. Sub-ledger record created in `customer_invoices`.

### Contract D: Customer Receipt (J4)
- **Posting Rule:** Dr 1101 (Kas dan Bank) / Cr 1201 (Piutang Usaha).
- **Invariants:** Total debit == total credit. Increases cash/bank and decreases AR asset.
- **No Duplicate Revenue Rule:** Receipt must **NEVER** credit 4xxx revenue accounts.
- **Verification:** Zero customer receipt transactions touch revenue accounts. Revenue remains recognized exclusively by the Customer Invoice.

### Contract E: Bank Reconciliation (J5)
- **Invariants:** Matches statement lines against posted journal lines.
- **Cardinality:** Exactly 1 target per statement line (`ck_bank_recon_exactly_one_target`).
- **Nominal Equality:** `matched_amount` equals statement line amount. Mismatch rejected with HTTP 422.
- **No Duplicate Journal:** Bank reconciliation matches existing journals and does not spawn synthetic duplicate journals.
