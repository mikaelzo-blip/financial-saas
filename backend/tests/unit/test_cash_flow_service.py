import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.cash_flow_service import CashFlowService


@pytest.mark.asyncio
async def test_cash_flow_direct_method(db_session: AsyncSession):
    org = Organization(slug="pt-cf-test", legal_name="PT Cash Flow Test")
    db_session.add(org)
    await db_session.flush()

    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.05",
        account_name="Kas Induk",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE"
    )
    acc_alat = ChartOfAccount(
        organization_id=org.id,
        account_code="1201.01",
        account_name="Alat Berat",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="FIXED_ASSETS"
    )
    acc_modal = ChartOfAccount(
        organization_id=org.id,
        account_code="3101.01",
        account_name="Modal Setor",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="EQUITY"
    )
    db_session.add_all([acc_kas, acc_rev, acc_alat, acc_modal])
    await db_session.flush()

    # 1. Financing: Modal +50M
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-CF-01",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 1, 2),
        amount=Decimal("50000000.00"),
        description="Setor Modal",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(organization_id=org.id, entry_number="JE-CF-01", transaction_id=trx1.id, posting_date=date(2026, 1, 2), description="Setor", total_debit=Decimal("50000000.00"), total_credit=Decimal("50000000.00"), is_balanced=True)
    db_session.add(je1)
    await db_session.flush()
    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00"))
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_modal.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"))
    db_session.add_all([jl1_1, jl1_2])

    # 2. Operating: Customer Payment +20M
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-CF-02",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 1, 10),
        amount=Decimal("20000000.00"),
        description="Bayar Tagihan",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(organization_id=org.id, entry_number="JE-CF-02", transaction_id=trx2.id, posting_date=date(2026, 1, 10), description="Bayar", total_debit=Decimal("20000000.00"), total_credit=Decimal("20000000.00"), is_balanced=True)
    db_session.add(je2)
    await db_session.flush()
    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("20000000.00"), credit_amount=Decimal("0.00"))
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("20000000.00"))
    db_session.add_all([jl2_1, jl2_2])

    # 3. Investing: Asset Purchase -15M
    trx3 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-CF-03",
        transaction_type=TransactionType.ASSET_PURCHASE,
        transaction_date=date(2026, 1, 20),
        amount=Decimal("15000000.00"),
        description="Beli Alat",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx3)
    await db_session.flush()
    je3 = JournalEntry(organization_id=org.id, entry_number="JE-CF-03", transaction_id=trx3.id, posting_date=date(2026, 1, 20), description="Beli Alat", total_debit=Decimal("15000000.00"), total_credit=Decimal("15000000.00"), is_balanced=True)
    db_session.add(je3)
    await db_session.flush()
    jl3_1 = JournalLine(journal_entry_id=je3.id, line_number=1, account_id=acc_alat.id, debit_amount=Decimal("15000000.00"), credit_amount=Decimal("0.00"))
    jl3_2 = JournalLine(journal_entry_id=je3.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("15000000.00"))
    db_session.add_all([jl3_1, jl3_2])
    await db_session.commit()

    # Query Cash Flow
    cf = await CashFlowService.get_cash_flow(
        session=db_session,
        organization_id=org.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )

    assert cf.net_operating_cash == Decimal("20000000.00")
    assert cf.net_investing_cash == Decimal("-15000000.00")
    assert cf.net_financing_cash == Decimal("50000000.00")
    assert cf.net_cash_change == Decimal("55000000.00")
    assert cf.closing_cash_balance == Decimal("55000000.00")
