import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.transaction import Transaction
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_cash_flow_service_includes_1102_and_1103(db_session: AsyncSession):
    org = Organization(slug="pt-cf-multi-cash", legal_name="PT Multi Cash")
    db_session.add(org)
    await db_session.flush()

    acc_bank_bca = ChartOfAccount(
        organization_id=org.id,
        account_code="1102.01",
        account_name="Bank Operasional BCA",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
    )
    acc_kas_kecil = ChartOfAccount(
        organization_id=org.id,
        account_code="1103.01",
        account_name="Kas Kecil",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE",
    )
    acc_opex = ChartOfAccount(
        organization_id=org.id,
        account_code="6101.01",
        account_name="Beban Operasional",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="OPEX",
    )
    db_session.add_all([acc_bank_bca, acc_kas_kecil, acc_rev, acc_opex])
    await db_session.flush()

    # Opening balance prior to 2026-01-01 in 1102.01
    trx_open = Transaction(
        organization_id=org.id,
        transaction_code="TRX-OPEN-01",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2025, 12, 31),
        amount=Decimal("15000000.00"),
        description="Saldo Awal Bank",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_open)
    await db_session.flush()

    je_open = JournalEntry(
        organization_id=org.id,
        entry_number="JE-OPEN-01",
        transaction_id=trx_open.id,
        posting_date=date(2025, 12, 31),
        description="Saldo Awal Bank",
        total_debit=Decimal("15000000.00"),
        total_credit=Decimal("15000000.00"),
        is_balanced=True,
    )
    db_session.add(je_open)
    await db_session.flush()
    jl_open_dr = JournalLine(
        journal_entry_id=je_open.id,
        line_number=1,
        account_id=acc_bank_bca.id,
        debit_amount=Decimal("15000000.00"),
        credit_amount=Decimal("0.00"),
    )
    jl_open_cr = JournalLine(
        journal_entry_id=je_open.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("15000000.00"),
    )
    db_session.add_all([jl_open_dr, jl_open_cr])

    # 1. Customer Payment -> 1102.01 (Bank BCA): 50,000,000
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-MC-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 1, 10),
        amount=Decimal("50000000.00"),
        description="Penerimaan Jasa",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-MC-01",
        transaction_id=trx1.id,
        posting_date=date(2026, 1, 10),
        description="Penerimaan Jasa",
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00"),
        is_balanced=True,
    )
    db_session.add(je1)
    await db_session.flush()
    jl1_dr = JournalLine(
        journal_entry_id=je1.id,
        line_number=1,
        account_id=acc_bank_bca.id,
        debit_amount=Decimal("50000000.00"),
        credit_amount=Decimal("0.00"),
    )
    jl1_cr = JournalLine(
        journal_entry_id=je1.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("50000000.00"),
    )
    db_session.add_all([jl1_dr, jl1_cr])

    # 2. Operating Expense -> paid from 1103.01 (Kas Kecil): 10,000,000
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-MC-02",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 1, 20),
        amount=Decimal("10000000.00"),
        description="Beban Operasional",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-MC-02",
        transaction_id=trx2.id,
        posting_date=date(2026, 1, 20),
        description="Beban Operasional",
        total_debit=Decimal("10000000.00"),
        total_credit=Decimal("10000000.00"),
        is_balanced=True,
    )
    db_session.add(je2)
    await db_session.flush()
    jl2_dr = JournalLine(
        journal_entry_id=je2.id,
        line_number=1,
        account_id=acc_opex.id,
        debit_amount=Decimal("10000000.00"),
        credit_amount=Decimal("0.00"),
    )
    jl2_cr = JournalLine(
        journal_entry_id=je2.id,
        line_number=2,
        account_id=acc_kas_kecil.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("10000000.00"),
    )
    db_session.add_all([jl2_dr, jl2_cr])
    await db_session.commit()

    # Generate Cash Flow Report for Jan 2026
    cf = await CashFlowService.get_cash_flow(
        db_session,
        org.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    # Opening balance should discover 1102.01 (15M)
    assert cf.opening_cash_balance == Decimal("15000000.00")
    # Operating inflow +50M and outflow -10M -> net operating = 40M
    assert cf.net_operating_cash == Decimal("40000000.00")
    assert cf.net_cash_change == Decimal("40000000.00")
    # Closing cash = 15M + 40M = 55M
    assert cf.closing_cash_balance == Decimal("55000000.00")


@pytest.mark.asyncio
async def test_dashboard_summary_sums_1101_and_1102(db_session: AsyncSession):
    org = Organization(slug="pt-dash-multi-cash", legal_name="PT Dash Multi Cash")
    db_session.add(org)
    await db_session.flush()

    acc_kas_1101 = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Kas Tunai",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
    )
    acc_bank_1102 = ChartOfAccount(
        organization_id=org.id,
        account_code="1102.01",
        account_name="Bank Operasional Mandiri",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS",
    )
    # Also test an account discovered via PaymentAccount mapping even if code is unusual
    acc_custom = ChartOfAccount(
        organization_id=org.id,
        account_code="1099.01",
        account_name="Rekening Kliring Khusus",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="OTHER",
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE",
    )
    db_session.add_all([acc_kas_1101, acc_bank_1102, acc_custom, acc_rev])
    await db_session.flush()

    # Link acc_custom via PaymentAccount
    pa = PaymentAccount(
        organization_id=org.id,
        coa_account_id=acc_custom.id,
        name="Rekening Kliring",
    )
    db_session.add(pa)
    await db_session.flush()

    # JE 1: Inflow 30M to 1101.01
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-DM-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 2, 5),
        amount=Decimal("30000000.00"),
        description="Kas Inflow",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-DM-01",
        transaction_id=trx1.id,
        posting_date=date(2026, 2, 5),
        description="Kas Inflow",
        total_debit=Decimal("30000000.00"),
        total_credit=Decimal("30000000.00"),
        is_balanced=True,
    )
    db_session.add(je1)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_kas_1101.id, debit_amount=Decimal("30000000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("30000000.00")),
    ])

    # JE 2: Inflow 70M to 1102.01
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-DM-02",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 2, 10),
        amount=Decimal("70000000.00"),
        description="Bank Inflow",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-DM-02",
        transaction_id=trx2.id,
        posting_date=date(2026, 2, 10),
        description="Bank Inflow",
        total_debit=Decimal("70000000.00"),
        total_credit=Decimal("70000000.00"),
        is_balanced=True,
    )
    db_session.add(je2)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_bank_1102.id, debit_amount=Decimal("70000000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("70000000.00")),
    ])

    # JE 3: Inflow 20M to acc_custom (mapped via PaymentAccount)
    trx3 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-DM-03",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 2, 12),
        amount=Decimal("20000000.00"),
        description="Custom Account Inflow",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx3)
    await db_session.flush()
    je3 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-DM-03",
        transaction_id=trx3.id,
        posting_date=date(2026, 2, 12),
        description="Custom Account Inflow",
        total_debit=Decimal("20000000.00"),
        total_credit=Decimal("20000000.00"),
        is_balanced=True,
    )
    db_session.add(je3)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je3.id, line_number=1, account_id=acc_custom.id, debit_amount=Decimal("20000000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=je3.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("20000000.00")),
    ])
    await db_session.commit()

    # Query Dashboard Summary as of Feb 2026
    dash = await DashboardService.get_dashboard_summary(
        db_session,
        org.id,
        as_of_date=date(2026, 2, 28),
    )

    # 30M (1101) + 70M (1102) + 20M (custom payment account) = 120M
    assert dash.cash_and_bank_balance == Decimal("120000000.00")
    assert dash.cash_in_period == Decimal("120000000.00")
    assert dash.net_cash_flow == Decimal("120000000.00")

    # Trend check
    trend = await DashboardService.get_cash_flow_trend(
        db_session,
        org.id,
        months=1,
        as_of_date=date(2026, 2, 28),
    )
    assert len(trend.items) >= 1
    # Check that cash in the trend reflects the 120M for this month
    feb_item = next(it for it in trend.items if it.period == "2026-02")
    assert feb_item.cash_in == Decimal("120000000.00")
