"""Read-only RC1 Accounting Safety Baseline Verification Script."""

import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select

from src.core.database import AsyncSessionLocal, engine
from src.models.document import Document
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.organization import Organization
from src.models.payable import VendorBill
from src.models.receivable import CustomerInvoice
from src.models.transaction import Transaction
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.integrity_service import IntegrityService
from src.services.reporting.pl_service import ProfitLossService


async def verify_accounting_baseline() -> None:
    engine.echo = False
    async with AsyncSessionLocal() as session:
        print("=== ACCOUNTING SAFETY BASELINE VERIFICATION ===")

        # 1. Total Debit = Total Credit
        unbalanced_jes = (
            await session.execute(
                select(func.count(JournalEntry.id)).where(
                    JournalEntry.total_debit != JournalEntry.total_credit
                )
            )
        ).scalar() or 0

        gl_dr = (
            await session.execute(
                select(
                    func.coalesce(func.sum(JournalLine.debit_amount), Decimal("0.00"))
                )
            )
        ).scalar() or Decimal("0.00")
        gl_cr = (
            await session.execute(
                select(
                    func.coalesce(func.sum(JournalLine.credit_amount), Decimal("0.00"))
                )
            )
        ).scalar() or Decimal("0.00")
        gl_diff = abs(gl_dr - gl_cr)

        print("1. Total Debit = Total Credit:")
        print(f"   Unbalanced Journal Entries: {unbalanced_jes}")
        print(f"   Global GL Total Debit:  {gl_dr}")
        print(f"   Global GL Total Credit: {gl_cr}")
        print(f"   Global GL Discrepancy:  {gl_diff}")
        assert unbalanced_jes == 0, f"Found {unbalanced_jes} unbalanced journal entries!"
        assert gl_diff == Decimal("0.00"), f"Global GL discrepancy: {gl_diff}"
        print("   -> PASS: Total Debit == Total Credit across all entries and lines")

        # 2 & 3. Assets = Liabilities + Equity and Formal Profit ties to Current-Year Earnings
        print("\n2 & 3. Accounting Equation and Profit-to-Equity Tie-out:")
        orgs = (await session.scalars(select(Organization))).all()
        for org in orgs:
            diag = await IntegrityService.run_diagnostics(session, org.id)
            print(f"   Organization: {org.legal_name} ({org.id})")
            print(f"     Integrity overall status: {diag.overall_status}")
            for c in diag.checks:
                print(f"       - {c.check_name}: {c.status} (discrepancy: {c.discrepancy})")
                assert c.status == "PASS", f"Integrity check failed: {c.check_name}"

            bs = await BalanceSheetService.get_balance_sheet(
                session, org.id, as_of_date=date.today()
            )
            pl = await ProfitLossService.get_profit_and_loss(
                session,
                org.id,
                start_date=date(date.today().year, 1, 1),
                end_date=date.today(),
            )

            print("     Balance Sheet:")
            print(f"       Total Assets: {bs.total_assets}")
            print(f"       Total Liabilities: {bs.total_liabilities}")
            print(f"       Total Equity: {bs.total_equity}")
            print(f"       Total L+E: {bs.total_liabilities_and_equity}")
            print(f"       Balanced: {bs.is_balanced}, diff: {bs.balancing_difference}")
            assert bs.is_balanced is True, f"Balance sheet unbalanced for {org.legal_name}!"
            assert bs.balancing_difference == Decimal("0.00")

            # Tie-out check
            cy_line = next(
                (line for line in bs.equity.lines if line.account_code == "EQ-CY"), None
            )
            cy_earnings_bs = cy_line.amount if cy_line else Decimal("0.00")
            print("     Tie-out:")
            print(f"       Formal P&L Net Profit: {pl.net_profit}")
            print(f"       Balance Sheet EQ-CY:   {cy_earnings_bs}")
            assert (
                pl.net_profit == cy_earnings_bs
            ), f"P&L net profit ({pl.net_profit}) does not tie to BS current earnings ({cy_earnings_bs})"
            print("     -> PASS: Assets = Liabilities + Equity AND P&L ties to Balance Sheet")

        # 4. No orphan AR / AP / Settlement / MoneyMovement
        print("\n4. Orphan Integrity Checks:")
        # Check CustomerInvoice orphan transactions
        orphan_invoices = (
            await session.execute(
                select(func.count(CustomerInvoice.id))
                .outerjoin(Transaction, CustomerInvoice.transaction_id == Transaction.id)
                .where(
                    and_(
                        CustomerInvoice.transaction_id.isnot(None),
                        Transaction.id.is_(None),
                    )
                )
            )
        ).scalar() or 0
        print(f"   Orphan CustomerInvoices: {orphan_invoices}")
        assert orphan_invoices == 0

        # Check VendorBill orphan transactions
        orphan_bills = (
            await session.execute(
                select(func.count(VendorBill.id))
                .outerjoin(Transaction, VendorBill.transaction_id == Transaction.id)
                .where(
                    and_(
                        VendorBill.transaction_id.isnot(None),
                        Transaction.id.is_(None),
                    )
                )
            )
        ).scalar() or 0
        print(f"   Orphan VendorBills: {orphan_bills}")
        assert orphan_bills == 0

        # Check Settlement orphan transactions
        orphan_settlements = (
            await session.execute(
                select(func.count(Settlement.id))
                .outerjoin(Transaction, Settlement.transaction_id == Transaction.id)
                .where(
                    and_(
                        Settlement.transaction_id.isnot(None),
                        Transaction.id.is_(None),
                    )
                )
            )
        ).scalar() or 0
        print(f"   Orphan Settlements: {orphan_settlements}")
        assert orphan_settlements == 0

        # Check SettlementAllocation orphan settlements
        orphan_allocs = (
            await session.execute(
                select(func.count(SettlementAllocation.id))
                .outerjoin(
                    Settlement, SettlementAllocation.settlement_id == Settlement.id
                )
                .where(Settlement.id.is_(None))
            )
        ).scalar() or 0
        print(f"   Orphan SettlementAllocations: {orphan_allocs}")
        assert orphan_allocs == 0

        # Check MoneyMovement orphan payment accounts
        from src.models.coa import PaymentAccount

        orphan_mm_pa = (
            await session.execute(
                select(func.count(MoneyMovement.id))
                .outerjoin(
                    PaymentAccount,
                    MoneyMovement.payment_account_id == PaymentAccount.id,
                )
                .where(PaymentAccount.id.is_(None))
            )
        ).scalar() or 0
        print(f"   Orphan MoneyMovements (missing PaymentAccount): {orphan_mm_pa}")
        assert orphan_mm_pa == 0

        # Check Settlement orphan money movements
        orphan_settlement_mm = (
            await session.execute(
                select(func.count(Settlement.id))
                .outerjoin(
                    MoneyMovement, Settlement.money_movement_id == MoneyMovement.id
                )
                .where(MoneyMovement.id.is_(None))
            )
        ).scalar() or 0
        print(f"   Orphan Settlements (missing MoneyMovement): {orphan_settlement_mm}")
        assert orphan_settlement_mm == 0

        print("   -> PASS: Zero orphan records found")

        # 5. No WhatsApp direct accounting posting
        print("\n5. WhatsApp Direct Accounting Posting Check:")
        from src.models.document import TransactionDocumentLink

        wa_docs = (
            await session.scalars(
                select(Document).where(Document.source_channel == "WHATSAPP")
            )
        ).all()
        print(f"   Total WhatsApp Documents: {len(wa_docs)}")
        for doc in wa_docs:
            status_val = (
                doc.processing_status.value
                if hasattr(doc.processing_status, "value")
                else str(doc.processing_status)
            )
            print(f"     Doc {doc.document_code} status: {status_val}")
            # If document was not approved, ensure zero transactions and zero journal entries exist
            if status_val not in ["APPROVED", "PROCESSED"]:
                linked_trxs = (
                    await session.execute(
                        select(func.count(TransactionDocumentLink.transaction_id)).where(
                            TransactionDocumentLink.document_id == doc.id
                        )
                    )
                ).scalar() or 0
                assert (
                    linked_trxs == 0
                ), f"Unapproved doc {doc.id} linked to {linked_trxs} transactions!"

        # Confirm zero journal entries with unreviewed WhatsApp description
        direct_wa_journals = (
            await session.execute(
                select(func.count(JournalEntry.id)).where(
                    JournalEntry.description.like("%WHATSAPP_AUTO%"),
                )
            )
        ).scalar() or 0
        print(f"   Direct unapproved WhatsApp journals: {direct_wa_journals}")
        assert direct_wa_journals == 0
        print("   -> PASS: No direct WhatsApp accounting postings")


if __name__ == "__main__":
    asyncio.run(verify_accounting_baseline())
