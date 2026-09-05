import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.transaction import Transaction
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus

from src.services.coa_seeder import seed_standard_coa
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.balance_sheet_service import BalanceSheetService


@pytest.mark.asyncio
async def test_pl_consultant_classification_mapping(db_session: AsyncSession):
    org = Organization(slug="org-pl-mapping", legal_name="Org PL Mapping")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    # Create transaction to associate with journal entry
    trx_1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000099",
        transaction_type=TransactionType.OTHER_INCOME,
        transaction_date=date(2026, 3, 15),
        amount=Decimal("10000000.00"),
        description="Non-operating entries",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_1)
    await db_session.flush()

    # Create journal entry with Other Income (4201) and Other Expense (7101)
    je = JournalEntry(
        organization_id=org.id,
        transaction_id=trx_1.id,
        entry_number="JE-2026-000099",
        posting_date=date(2026, 3, 15),
        description="Non-operating entries",
        total_debit=Decimal("12000000.00"),
        total_credit=Decimal("12000000.00"),
        is_balanced=True
    )
    db_session.add(je)
    await db_session.flush()


    coa_1101 = await db_session.scalar(ChartOfAccount.get_by_code(org.id, "1101")) if hasattr(ChartOfAccount, "get_by_code") else None
    from sqlalchemy import select
    acc_1101 = await db_session.scalar(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code == "1101"))
    acc_4201 = await db_session.scalar(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code == "4201"))
    acc_7101 = await db_session.scalar(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code == "7101"))

    # Dr 1101 10.000.000 / Cr 4201 10.000.000 (Pendapatan Lain-lain)
    l1 = JournalLine(journal_entry_id=je.id, account_id=acc_1101.id, line_number=1, debit_amount=Decimal("10000000.00"), credit_amount=Decimal("0.00"))
    l2 = JournalLine(journal_entry_id=je.id, account_id=acc_4201.id, line_number=2, debit_amount=Decimal("0.00"), credit_amount=Decimal("10000000.00"))
    # Dr 7101 2.000.000 / Cr 1101 2.000.000 (Beban Non-Operasional)
    l3 = JournalLine(journal_entry_id=je.id, account_id=acc_7101.id, line_number=3, debit_amount=Decimal("2000000.00"), credit_amount=Decimal("0.00"))
    l4 = JournalLine(journal_entry_id=je.id, account_id=acc_1101.id, line_number=4, debit_amount=Decimal("0.00"), credit_amount=Decimal("2000000.00"))
    db_session.add_all([l1, l2, l3, l4])
    await db_session.commit()


    pl = await ProfitLossService.get_profit_and_loss(
        session=db_session,
        organization_id=org.id,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31)
    )

    assert pl.other_income_expense_section.subtotal == Decimal("8000000.00")
    assert pl.net_profit == Decimal("8000000.00")



@pytest.mark.asyncio
async def test_balance_sheet_long_term_liabilities_classification(db_session: AsyncSession):
    org = Organization(slug="org-bs-ltl", legal_name="Org BS LTL")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    from sqlalchemy import select
    acc_1101 = await db_session.scalar(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code == "1101"))
    acc_2501 = await db_session.scalar(select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code == "2501"))

    trx_2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000100",
        transaction_type=TransactionType.LOAN_RECEIVED,
        transaction_date=date(2026, 3, 20),
        amount=Decimal("50000000.00"),
        description="Pinjaman Bank Jangka Panjang",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_2)
    await db_session.flush()

    # Dr 1101 50.000.000 / Cr 2501 50.000.000 (Pinjaman Jangka Panjang)
    je = JournalEntry(
        organization_id=org.id,
        transaction_id=trx_2.id,
        entry_number="JE-2026-000100",
        posting_date=date(2026, 3, 20),
        description="Pinjaman Bank Jangka Panjang",
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00"),
        is_balanced=True
    )
    db_session.add(je)
    await db_session.flush()


    l1 = JournalLine(journal_entry_id=je.id, account_id=acc_1101.id, line_number=1, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"))
    l2 = JournalLine(journal_entry_id=je.id, account_id=acc_2501.id, line_number=2, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"))
    db_session.add_all([l1, l2])
    await db_session.commit()


    bs = await BalanceSheetService.get_balance_sheet(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 3, 31)
    )

    assert bs.long_term_liabilities.subtotal == Decimal("50000000.00")
    assert bs.total_liabilities == Decimal("50000000.00")
    assert bs.is_balanced is True
    assert bs.total_assets == bs.total_liabilities_and_equity
