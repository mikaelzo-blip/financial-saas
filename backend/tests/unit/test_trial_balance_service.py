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
from src.services.reporting.trial_balance_service import TrialBalanceService


@pytest.mark.asyncio
async def test_trial_balance_debit_equals_credit(db_session: AsyncSession):
    org = Organization(slug="pt-tb-test", legal_name="PT Trial Balance Test")
    db_session.add(org)
    await db_session.flush()

    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Kas Utama",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_modal = ChartOfAccount(
        organization_id=org.id,
        account_code="3101.01",
        account_name="Modal Disetor",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="EQUITY"
    )
    db_session.add_all([acc_kas, acc_modal])
    await db_session.flush()

    trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-CAPITAL-001",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 1, 15),
        amount=Decimal("50000000.00"),
        description="Setoran Modal Awal",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx)
    await db_session.flush()

    je = JournalEntry(
        organization_id=org.id,
        entry_number="JE-CAPITAL-001",
        transaction_id=trx.id,
        posting_date=date(2026, 1, 15),
        description="Setoran Modal Pemilik",
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00"),
        is_balanced=True
    )
    db_session.add(je)
    await db_session.flush()

    jl1 = JournalLine(
        journal_entry_id=je.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("50000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl2 = JournalLine(
        journal_entry_id=je.id,
        line_number=2,
        account_id=acc_modal.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("50000000.00")
    )
    db_session.add_all([jl1, jl2])
    await db_session.commit()

    # Get Trial Balance
    tb = await TrialBalanceService.get_trial_balance(
        session=db_session,
        organization_id=org.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )

    assert tb.is_balanced is True
    assert tb.difference == Decimal("0.00")
    assert tb.total_ending_debit == Decimal("50000000.00")
    assert tb.total_ending_credit == Decimal("50000000.00")
    assert len(tb.lines) == 2
