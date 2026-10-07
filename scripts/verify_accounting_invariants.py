import asyncio
import sys
import os

# add backend to path
sys.path.insert(0, os.path.abspath("backend"))

from sqlalchemy import text
from src.core.database import AsyncSessionLocal

async def check_accounting():
    async with AsyncSessionLocal() as s:
        # 1. Unbalanced Journal Entries
        res = await s.execute(text('''
            SELECT id, entry_number, total_debit, total_credit, transaction_id, is_reversed
            FROM journal_entries
            WHERE total_debit != total_credit
        '''))
        unbalanced = res.fetchall()
        print(f"1. Unbalanced journal entries count: {len(unbalanced)}")
        for row in unbalanced:
            print(f"   Unbalanced: {row}")

        # 2. Line vs Header Mismatches
        res = await s.execute(text('''
            SELECT je.id, je.entry_number, je.total_debit, SUM(jl.debit_amount) as line_debit,
                   je.total_credit, SUM(jl.credit_amount) as line_credit
            FROM journal_entries je
            JOIN journal_lines jl ON je.id = jl.journal_entry_id
            GROUP BY je.id, je.entry_number, je.total_debit, je.total_credit
            HAVING je.total_debit != SUM(jl.debit_amount) OR je.total_credit != SUM(jl.credit_amount)
        '''))
        line_mismatches = res.fetchall()
        print(f"2. Header vs Lines mismatch count: {len(line_mismatches)}")
        for row in line_mismatches:
            print(f"   Mismatch: {row}")

        # 3. Orphan Journal Lines
        res = await s.execute(text('''
            SELECT jl.id, jl.journal_entry_id
            FROM journal_lines jl
            LEFT JOIN journal_entries je ON jl.journal_entry_id = je.id
            WHERE je.id IS NULL
        '''))
        orphans = res.fetchall()
        print(f"3. Orphan journal lines count: {len(orphans)}")

        # 4. Duplicate Journals for same transaction
        res = await s.execute(text('''
            SELECT transaction_id, COUNT(*) as cnt
            FROM journal_entries
            WHERE transaction_id IS NOT NULL
            GROUP BY transaction_id
            HAVING COUNT(*) > 1
        '''))
        dup_journals = res.fetchall()
        print(f"4. Duplicate journals per transaction count: {len(dup_journals)}")
        for row in dup_journals:
            print(f"   Duplicate: {row}")

        # 5. Journal Entries without transaction linkage
        res = await s.execute(text('''
            SELECT id, entry_number, posting_date, total_debit
            FROM journal_entries
            WHERE transaction_id IS NULL
        '''))
        no_trx = res.fetchall()
        print(f"5. Journal entries without transaction_id count: {len(no_trx)}")
        for row in no_trx:
            print(f"   No transaction: {row}")

        # 6. Reversal consistency: check all reversed transactions
        res = await s.execute(text('''
            SELECT t1.id as orig_id, t1.transaction_code as orig_code, t1.transaction_type as orig_type, t1.workflow_status as orig_status,
                   t2.id as rev_id, t2.transaction_code as rev_code, t2.transaction_type as rev_type, t2.workflow_status as rev_status
            FROM transactions t1
            JOIN transactions t2 ON t2.reversal_of_id = t1.id
            ORDER BY t1.transaction_code
        '''))
        reversals = res.fetchall()
        print(f"6. Reversal transaction pairs count: {len(reversals)}")
        for row in reversals:
            print(f"   Orig: {row.orig_code} ({row.orig_type}, {row.orig_status}) <-> Rev: {row.rev_code} ({row.rev_type}, {row.rev_status})")

        # 7. Check net financial impact of each reversal pair
        res = await s.execute(text('''
            SELECT t1.transaction_code as orig_code, t2.transaction_code as rev_code,
                   jl.account_id, a.account_code, a.account_name,
                   SUM(jl.debit_amount - jl.credit_amount) as net_balance
            FROM transactions t1
            JOIN transactions t2 ON t2.reversal_of_id = t1.id
            JOIN journal_entries je ON je.transaction_id IN (t1.id, t2.id)
            JOIN journal_lines jl ON jl.journal_entry_id = je.id
            JOIN chart_of_accounts a ON a.id = jl.account_id
            GROUP BY t1.transaction_code, t2.transaction_code, jl.account_id, a.account_code, a.account_name
            HAVING SUM(jl.debit_amount - jl.credit_amount) != 0
        '''))
        non_zero_reversals = res.fetchall()
        print(f"7. Non-zero net balance reversal pairs count: {len(non_zero_reversals)}")
        for row in non_zero_reversals:
            print(f"   Anomaly non-zero reversal: {row}")

        # 8. Check AP Vendor Payment posting consistency:
        # PAY_VENDOR_BILL must debit 2101 Utang Usaha and credit 1101 Kas/Bank. Must NEVER touch 5xxx or 6xxx expense!
        res = await s.execute(text('''
            SELECT t.transaction_code, a.account_code, a.account_name, jl.debit_amount, jl.credit_amount
            FROM transactions t
            JOIN journal_entries je ON je.transaction_id = t.id
            JOIN journal_lines jl ON jl.journal_entry_id = je.id
            JOIN chart_of_accounts a ON a.id = jl.account_id
            WHERE t.transaction_type = 'PAY_VENDOR_BILL'
              AND (a.account_code LIKE '5%' OR a.account_code LIKE '6%')
        '''))
        bad_ap_payments = res.fetchall()
        print(f"8. AP payments touching expense accounts (anomaly count): {len(bad_ap_payments)}")
        for row in bad_ap_payments:
            print(f"   Bad AP payment: {row}")

        # 9. Check AR Customer Receipt posting consistency:
        # CUSTOMER_PAYMENT must debit 1101 Kas/Bank and credit 1201 Piutang Usaha. Must NEVER touch 4xxx revenue!
        res = await s.execute(text('''
            SELECT t.transaction_code, a.account_code, a.account_name, jl.debit_amount, jl.credit_amount
            FROM transactions t
            JOIN journal_entries je ON je.transaction_id = t.id
            JOIN journal_lines jl ON jl.journal_entry_id = je.id
            JOIN chart_of_accounts a ON a.id = jl.account_id
            WHERE t.transaction_type = 'CUSTOMER_PAYMENT'
              AND a.account_code LIKE '4%'
        '''))
        bad_ar_receipts = res.fetchall()
        print(f"9. AR receipts touching revenue accounts (anomaly count): {len(bad_ar_receipts)}")
        for row in bad_ar_receipts:
            print(f"   Bad AR receipt: {row}")

        # 10. Total posted transactions and journals summary
        res = await s.execute(text('''
            SELECT COUNT(t.id) as total_transactions,
                   COUNT(je.id) as total_journals,
                   SUM(je.total_debit) as grand_total_debit,
                   SUM(je.total_credit) as grand_total_credit
            FROM journal_entries je
            LEFT JOIN transactions t ON je.transaction_id = t.id
        '''))
        totals = res.fetchone()
        print(f"10. Global Accounting Summary: Transactions={totals.total_transactions}, Journals={totals.total_journals}, GrandDebit={totals.grand_total_debit}, GrandCredit={totals.grand_total_credit}")

if __name__ == "__main__":
    asyncio.run(check_accounting())
