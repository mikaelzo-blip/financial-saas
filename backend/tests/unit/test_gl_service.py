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
from src.services.reporting.gl_service import GeneralLedgerService


@pytest.mark.asyncio
async def test_general_ledger_running_balance(db_session: AsyncSession):
    org = Organization(slug="pt-gl-test", legal_name="PT General Ledger Test")
    db_session.add(org)
    await db_session.flush()

    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.02",
        account_name="Kas Operasional",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.02",
        account_name="Pendapatan Jasa",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE"
    )
    db_session.add_all([acc_kas, acc_rev])
    await db_session.flush()

    # Entry 1: Jan 10 (+10,000,000)
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-GL-001",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 1, 10),
        amount=Decimal("10000000.00"),
        description="Pembayaran Termin 1",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx1)
    await db_session.flush()

    je1 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-GL-001",
        transaction_id=trx1.id,
        posting_date=date(2026, 1, 10),
        description="Penerimaan Kas",
        total_debit=Decimal("10000000.00"),
        total_credit=Decimal("10000000.00"),
        is_balanced=True
    )
    db_session.add(je1)
    await db_session.flush()

    jl1_1 = JournalLine(
        journal_entry_id=je1.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("10000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl1_2 = JournalLine(
        journal_entry_id=je1.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("10000000.00")
    )
    db_session.add_all([jl1_1, jl1_2])

    # Entry 2: Jan 20 (+5,000,000)
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-GL-002",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 1, 20),
        amount=Decimal("5000000.00"),
        description="Pembayaran Termin 2",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx2)
    await db_session.flush()

    je2 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-GL-002",
        transaction_id=trx2.id,
        posting_date=date(2026, 1, 20),
        description="Penerimaan Kas 2",
        total_debit=Decimal("5000000.00"),
        total_credit=Decimal("5000000.00"),
        is_balanced=True
    )
    db_session.add(je2)
    await db_session.flush()

    jl2_1 = JournalLine(
        journal_entry_id=je2.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("5000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl2_2 = JournalLine(
        journal_entry_id=je2.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("5000000.00")
    )
    db_session.add_all([jl2_1, jl2_2])
    await db_session.commit()

    # Query General Ledger
    gl = await GeneralLedgerService.get_general_ledger(
        session=db_session,
        organization_id=org.id,
        account_code="1101.02",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )

    assert gl.opening_balance == Decimal("0.00")
    assert gl.total_debit == Decimal("15000000.00")
    assert gl.closing_balance == Decimal("15000000.00")
    assert len(gl.entries) == 2
    assert gl.entries[0].running_balance == Decimal("10000000.00")
    assert gl.entries[1].running_balance == Decimal("15000000.00")
