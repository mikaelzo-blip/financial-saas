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
from src.services.reporting.balance_sheet_service import BalanceSheetService


@pytest.mark.asyncio
async def test_balance_sheet_accounting_equation(db_session: AsyncSession):
    org = Organization(slug="pt-bs-test", legal_name="PT Balance Sheet Test")
    db_session.add(org)
    await db_session.flush()

    acc_kas = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.04",
        account_name="Kas Bank BCA",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="CURRENT_ASSETS"
    )
    acc_alat = ChartOfAccount(
        organization_id=org.id,
        account_code="1201.01",
        account_name="Alat Berat Excavator",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="FIXED_ASSETS"
    )
    acc_utang = ChartOfAccount(
        organization_id=org.id,
        account_code="2101.01",
        account_name="Utang Usaha Supplier",
        account_type=AccountType.LIABILITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="CURRENT_LIABILITIES"
    )
    acc_modal = ChartOfAccount(
        organization_id=org.id,
        account_code="3101.01",
        account_name="Modal Pemilik",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="EQUITY"
    )
    db_session.add_all([acc_kas, acc_alat, acc_utang, acc_modal])
    await db_session.flush()

    # Trx 1: Modal Setoran Rp 100,000,000 (Kas Dr, Modal Cr)
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-MODAL-01",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 1, 1),
        amount=Decimal("100000000.00"),
        description="Setoran Modal",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx1)
    await db_session.flush()

    je1 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-MODAL-01",
        transaction_id=trx1.id,
        posting_date=date(2026, 1, 1),
        description="Setoran Modal",
        total_debit=Decimal("100000000.00"),
        total_credit=Decimal("100000000.00"),
        is_balanced=True
    )
    db_session.add(je1)
    await db_session.flush()

    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("100000000.00"), credit_amount=Decimal("0.00"))
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_modal.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("100000000.00"))
    db_session.add_all([jl1_1, jl1_2])

    # Trx 2: Beli Excavator Rp 80,000,000 (Alat Dr Rp 80M, Kas Cr Rp 30M, Utang Cr Rp 50M)
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-ASSET-01",
        transaction_type=TransactionType.ASSET_PURCHASE,
        transaction_date=date(2026, 1, 15),
        amount=Decimal("80000000.00"),
        description="Beli Excavator",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx2)
    await db_session.flush()

    je2 = JournalEntry(
        organization_id=org.id,
        entry_number="JE-ASSET-01",
        transaction_id=trx2.id,
        posting_date=date(2026, 1, 15),
        description="Beli Excavator",
        total_debit=Decimal("80000000.00"),
        total_credit=Decimal("80000000.00"),
        is_balanced=True
    )
    db_session.add(je2)
    await db_session.flush()

    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_alat.id, debit_amount=Decimal("80000000.00"), credit_amount=Decimal("0.00"))
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("30000000.00"))
    jl2_3 = JournalLine(journal_entry_id=je2.id, line_number=3, account_id=acc_utang.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"))
    db_session.add_all([jl2_1, jl2_2, jl2_3])
    await db_session.commit()

    # Query Balance Sheet
    bs = await BalanceSheetService.get_balance_sheet(
        session=db_session,
        organization_id=org.id,
        as_of_date=date(2026, 1, 31)
    )

    assert bs.is_balanced is True
    assert bs.balancing_difference == Decimal("0.00")
    assert bs.integrity_status == "VALID"
    # Total Assets: Kas (70M) + Alat (80M) = 150M
    assert bs.total_assets == Decimal("150000000.00")
    # Liabilities (50M) + Equity (100M) = 150M
    assert bs.total_liabilities == Decimal("50000000.00")
    assert bs.total_equity == Decimal("100000000.00")
    assert bs.total_liabilities_and_equity == Decimal("150000000.00")
