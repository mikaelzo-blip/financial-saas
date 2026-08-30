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
from src.services.reporting.pl_service import ProfitLossService


@pytest.mark.asyncio
async def test_profit_and_loss_math(db_session: AsyncSession):
    org = Organization(slug="pt-pl-test", legal_name="PT Profit Loss Test")
    db_session.add(org)
    await db_session.flush()

    # Accounts
    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.03",
        account_name="Bank Operasional",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa Konstruksi",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE"
    )
    acc_cogs = ChartOfAccount(
        organization_id=org.id,
        account_code="5101.01",
        account_name="Biaya Material Pasir & Semen",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="COGS"
    )
    acc_opex = ChartOfAccount(
        organization_id=org.id,
        account_code="6101.01",
        account_name="Gaji Pegawai Kantor",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="OPEX"
    )
    db_session.add_all([acc_kas, acc_rev, acc_cogs, acc_opex])
    await db_session.flush()

    # 1. Revenue: Rp 100,000,000
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-REV-01",
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date(2026, 1, 5),
        amount=Decimal("100000000.00"),
        description="Termin 1 Proyek",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx1)
    await db_session.flush()

    je1 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-REV-01",
        transaction_id=trx1.id,
        posting_date=date(2026, 1, 5),
        description="Termin 1 Proyek",
        total_debit=Decimal("100000000.00"),
        total_credit=Decimal("100000000.00"),
        is_balanced=True
    )
    db_session.add(je1)
    await db_session.flush()

    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("100000000.00"), credit_amount=Decimal("0.00"))
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000000.00"))
    db_session.add_all([jl1_1, jl1_2])

    # 2. COGS (Material): Rp 40,000,000
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-COGS-01",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 1, 10),
        amount=Decimal("40000000.00"),
        description="Beli Semen Proyek",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx2)
    await db_session.flush()

    je2 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-COGS-01",
        transaction_id=trx2.id,
        posting_date=date(2026, 1, 10),
        description="Beli Semen Proyek",
        total_debit=Decimal("40000000.00"),
        total_credit=Decimal("40000000.00"),
        is_balanced=True
    )
    db_session.add(je2)
    await db_session.flush()

    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_cogs.id, debit_amount=Decimal("40000000.00"), credit_amount=Decimal("0.00"))
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("40000000.00"))
    db_session.add_all([jl2_1, jl2_2])

    # 3. OPEX (Gaji Kantor): Rp 10,000,000
    trx3 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-OPEX-01",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 1, 25),
        amount=Decimal("10000000.00"),
        description="Gaji Staff",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx3)
    await db_session.flush()

    je3 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-OPEX-01",
        transaction_id=trx3.id,
        posting_date=date(2026, 1, 25),
        description="Gaji Staff Kantor",
        total_debit=Decimal("10000000.00"),
        total_credit=Decimal("10000000.00"),
        is_balanced=True
    )
    db_session.add(je3)
    await db_session.flush()

    jl3_1 = JournalLine(journal_entry_id=je3.id, line_number=1, account_id=acc_opex.id, debit_amount=Decimal("10000000.00"), credit_amount=Decimal("0.00"))
    jl3_2 = JournalLine(journal_entry_id=je3.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("10000000.00"))
    db_session.add_all([jl3_1, jl3_2])
    await db_session.commit()

    # Query Profit and Loss
    pl = await ProfitLossService.get_profit_and_loss(
        session=db_session,
        organization_id=org.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )

    assert pl.revenue_section.subtotal == Decimal("100000000.00")
    assert pl.cogs_section.subtotal == Decimal("40000000.00")
    assert pl.gross_profit == Decimal("60000000.00")
    assert pl.gross_margin_percentage == Decimal("60.00")
    assert pl.operating_expenses_section.subtotal == Decimal("10000000.00")
    assert pl.operating_profit == Decimal("50000000.00")
    assert pl.net_profit == Decimal("50000000.00")
