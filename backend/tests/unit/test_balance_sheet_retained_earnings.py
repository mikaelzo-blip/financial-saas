import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.balance_sheet_service import BalanceSheetService


@pytest.mark.asyncio
async def test_balance_sheet_multi_year_retained_earnings_rollover(db_session: AsyncSession):
    """
    Test multi-year retained earnings rollover:
    - 2024 profit: 100M
    - 2025 profit: 20M
    - Balance Sheet as of 2025-12-31:
      - 3201 (Saldo Laba Ditahan) should include prior year profit (100M)
      - EQ-CY (Laba Periode Berjalan) should only include current year profit (20M)
      - Neraca is balanced (Total Assets == Total Liabilities + Equity)
    """
    org = Organization(slug="pt-rollover-test", legal_name="PT Rollover Retained Earnings Test")
    db_session.add(org)
    await db_session.flush()

    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas & Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_modal = ChartOfAccount(
        organization_id=org.id,
        account_code="3101",
        account_name="Modal Disetor",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="EQUITY"
    )
    acc_re = ChartOfAccount(
        organization_id=org.id,
        account_code="3201",
        account_name="Saldo Laba Ditahan",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="EQUITY"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101",
        account_name="Pendapatan Proyek",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="OPERATING_REVENUE"
    )

    db_session.add_all([acc_kas, acc_modal, acc_re, acc_rev])
    await db_session.flush()

    # Trx 1: Profit 100M di 2024 (Kas Dr 100M, Pendapatan Cr 100M)
    trx_2024 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-REV-2024",
        transaction_type=TransactionType.REVENUE_RECOGNITION,
        transaction_date=date(2024, 6, 15),
        amount=Decimal("100000000.00"),
        description="Pendapatan Jasa 2024",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_2024)
    await db_session.flush()

    je_2024 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-REV-2024",
        transaction_id=trx_2024.id,
        posting_date=date(2024, 6, 15),
        description="Jurnal Pendapatan 2024",
        total_debit=Decimal("100000000.00"),
        total_credit=Decimal("100000000.00"),
        is_balanced=True
    )
    db_session.add(je_2024)
    await db_session.flush()

    jl_2024_dr = JournalLine(
        journal_entry_id=je_2024.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("100000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl_2024_cr = JournalLine(
        journal_entry_id=je_2024.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("100000000.00")
    )
    db_session.add_all([jl_2024_dr, jl_2024_cr])

    # Trx 2: Profit 20M di 2025 (Kas Dr 20M, Pendapatan Cr 20M)
    trx_2025 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-REV-2025",
        transaction_type=TransactionType.REVENUE_RECOGNITION,
        transaction_date=date(2025, 6, 15),
        amount=Decimal("20000000.00"),
        description="Pendapatan Jasa 2025",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_2025)
    await db_session.flush()

    je_2025 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-REV-2025",
        transaction_id=trx_2025.id,
        posting_date=date(2025, 6, 15),
        description="Jurnal Pendapatan 2025",
        total_debit=Decimal("20000000.00"),
        total_credit=Decimal("20000000.00"),
        is_balanced=True
    )
    db_session.add(je_2025)
    await db_session.flush()

    jl_2025_dr = JournalLine(
        journal_entry_id=je_2025.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("20000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl_2025_cr = JournalLine(
        journal_entry_id=je_2025.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("20000000.00")
    )
    db_session.add_all([jl_2025_dr, jl_2025_cr])
    await db_session.commit()

    # Tarik neraca per 31 Des 2025
    bs = await BalanceSheetService.get_balance_sheet(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2025, 12, 31)
    )

    # Invariants
    assert bs.is_balanced is True
    assert bs.balancing_difference == Decimal("0.00")
    assert bs.integrity_status == "VALID"
    assert bs.total_assets == Decimal("120000000.00")
    assert bs.total_liabilities == Decimal("0.00")
    assert bs.total_equity == Decimal("120000000.00")
    assert bs.total_liabilities_and_equity == Decimal("120000000.00")

    # Equity breakdown check
    equity_dict = {line.account_code: line.amount for line in bs.equity.lines}

    # 3201 (Saldo Laba Ditahan) bertambah 100M (dari laba 2024)
    assert "3201" in equity_dict
    assert equity_dict["3201"] == Decimal("100000000.00")

    # EQ-CY (Laba Periode Berjalan) hanya 20M (dari laba 2025)
    assert "EQ-CY" in equity_dict
    assert equity_dict["EQ-CY"] == Decimal("20000000.00")
