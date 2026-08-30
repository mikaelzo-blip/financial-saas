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
from src.services.reporting.integrity_service import IntegrityService


@pytest.mark.asyncio
async def test_integrity_service_balanced_organization(db_session: AsyncSession):
    # Setup test org
    org = Organization(slug="pt-test-integrity", legal_name="PT Test Integrity", tax_id="01.234.567.8-999.000")
    db_session.add(org)
    await db_session.flush()

    # Create Asset and Revenue Accounts
    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.99",
        account_name="Kas Testing",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.99",
        account_name="Pendapatan Testing",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="REVENUE"
    )
    db_session.add_all([acc_kas, acc_rev])
    await db_session.flush()

    # Create balanced transaction & journal entry
    trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-TEST-001",
        transaction_type=TransactionType.CUSTOMER_INVOICE,
        transaction_date=date.today(),
        amount=Decimal("10000000.00"),
        payment_account_id=None,
        description="Invoice Project Test",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx)
    await db_session.flush()

    je = JournalEntry(
        organization_id=org.id,
        entry_number="JE-TEST-001",
        transaction_id=trx.id,
        posting_date=date.today(),
        description="Balanced JE Test",
        total_debit=Decimal("10000000.00"),
        total_credit=Decimal("10000000.00"),
        is_balanced=True
    )
    db_session.add(je)
    await db_session.flush()

    jl1 = JournalLine(
        journal_entry_id=je.id,
        line_number=1,
        account_id=acc_kas.id,
        debit_amount=Decimal("10000000.00"),
        credit_amount=Decimal("0.00")
    )
    jl2 = JournalLine(
        journal_entry_id=je.id,
        line_number=2,
        account_id=acc_rev.id,
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("10000000.00")
    )
    db_session.add_all([jl1, jl2])
    await db_session.commit()

    # Run diagnostics
    report = await IntegrityService.run_diagnostics(db_session, org.id)
    assert report.overall_status == "VALID"
    assert len(report.checks) == 3
    assert all(c.status == "PASS" for c in report.checks)
