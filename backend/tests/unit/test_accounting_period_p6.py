import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, NormalBalance, TransactionType, WorkflowStatus, AccountingPeriodStatus
from src.models.transaction import Transaction
from src.models.accounting_period import AccountingPeriod
from src.models.fixed_asset import FixedAsset
from src.services.processing_policy_service import ProcessingPolicyService
from src.core.exceptions import InvariantViolationException


@pytest.mark.asyncio
async def test_accounting_period_closure_blocks_posting(db_session: AsyncSession):
    org = Organization(slug=f"p6-org-{uuid.uuid4().hex[:6]}", legal_name="P6 Contractor PT")
    db_session.add(org)
    await db_session.flush()

    # Closed period for Jan 2026
    closed_period = AccountingPeriod(
        organization_id=org.id,
        period_name="Januari 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=AccountingPeriodStatus.CLOSED
    )
    # Open period for Feb 2026
    open_period = AccountingPeriod(
        organization_id=org.id,
        period_name="Februari 2026",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        status=AccountingPeriodStatus.OPEN
    )
    db_session.add_all([closed_period, open_period])
    await db_session.flush()

    # Create Cash and Capital Accounts
    acc_cash = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    acc_cap = ChartOfAccount(
        organization_id=org.id,
        account_code="3101",
        account_name="Modal Disetor",
        account_type=AccountType.EQUITY,
        normal_balance=NormalBalance.CREDIT,
        report_group="Modal"
    )
    db_session.add_all([acc_cash, acc_cap])
    await db_session.flush()

    # Transaction in Jan 2026 (CLOSED PERIOD)
    trx_closed = Transaction(
        organization_id=org.id,
        transaction_code="TRX-P6-001",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 1, 15),
        amount=Decimal("10000000.00"),
        description="Setoran Modal di Periode Tutup",
        source_channel="WEB",
        workflow_status=WorkflowStatus.STAGED
    )
    db_session.add(trx_closed)
    await db_session.flush()

    policy_svc = ProcessingPolicyService(db_session)

    # Invariant: Posting to CLOSED period MUST be rejected
    with pytest.raises(InvariantViolationException) as exc_info:
        await policy_svc.authorize_and_post(
            organization_id=org.id,
            transaction_id=trx_closed.id,
            bypass_role_check=True
        )
    assert "CLOSED" in str(exc_info.value)
    assert "Januari 2026" in str(exc_info.value)

    # Transaction in Feb 2026 (OPEN PERIOD)
    trx_open = Transaction(
        organization_id=org.id,
        transaction_code="TRX-P6-002",
        transaction_type=TransactionType.OWNER_CONTRIBUTION,
        transaction_date=date(2026, 2, 10),
        amount=Decimal("10000000.00"),
        description="Setoran Modal di Periode Buka",
        source_channel="WEB",
        workflow_status=WorkflowStatus.STAGED
    )
    db_session.add(trx_open)
    await db_session.flush()

    posted_trx, je = await policy_svc.authorize_and_post(
        organization_id=org.id,
        transaction_id=trx_open.id,
        bypass_role_check=True
    )
    assert posted_trx.workflow_status == WorkflowStatus.POSTED
    assert je.is_balanced is True
    assert je.total_debit == Decimal("10000000.00")
    assert je.total_credit == Decimal("10000000.00")


@pytest.mark.asyncio
async def test_opening_balance_and_balance_sheet_integrity(db_session: AsyncSession):
    org = Organization(slug=f"p6-bs-{uuid.uuid4().hex[:6]}", legal_name="P6 Consultant Rec PT")
    db_session.add(org)
    await db_session.flush()

    # Create Accounts corresponding to consultant report
    acc_cash = ChartOfAccount(organization_id=org.id, account_code="1101", account_name="Kas & Bank", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="Aset Lancar")
    acc_ar = ChartOfAccount(organization_id=org.id, account_code="1201", account_name="Piutang Usaha", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="Aset Lancar")
    acc_fa = ChartOfAccount(organization_id=org.id, account_code="1501", account_name="Peralatan Proyek", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="Aset Tetap")
    acc_ap = ChartOfAccount(organization_id=org.id, account_code="2101", account_name="Utang Usaha", account_type=AccountType.LIABILITY, normal_balance=NormalBalance.CREDIT, report_group="Kewajiban Jangka Pendek")
    acc_cap = ChartOfAccount(organization_id=org.id, account_code="3101", account_name="Modal Saham", account_type=AccountType.EQUITY, normal_balance=NormalBalance.CREDIT, report_group="Modal")
    db_session.add_all([acc_cash, acc_ar, acc_fa, acc_ap, acc_cap])
    await db_session.flush()

    # Opening balance entries:
    # Assets: Kas 50M + Piutang 30M + Aset Tetap 70M = 150M Debit
    # Liabilities & Equity: Utang 40M + Modal 110M = 150M Credit
    from src.services.opening_balance_service import OpeningBalanceService
    from src.services.reporting.balance_sheet_service import BalanceSheetService

    ob_service = OpeningBalanceService(db_session)
    balance_entries = [
        {"account_code": "1101", "debit": Decimal("50000000.00"), "credit": Decimal("0.00")},
        {"account_code": "1201", "debit": Decimal("30000000.00"), "credit": Decimal("0.00")},
        {"account_code": "1501", "debit": Decimal("70000000.00"), "credit": Decimal("0.00")},
        {"account_code": "2101", "debit": Decimal("0.00"), "credit": Decimal("40000000.00")},
        {"account_code": "3101", "debit": Decimal("0.00"), "credit": Decimal("110000000.00")},
    ]

    trx = await ob_service.post_opening_balances(
        organization_id=org.id,
        as_of_date=date(2026, 1, 1),
        balance_entries=balance_entries,
        notes="Saldo Awal Konsultan 2026"
    )

    assert trx.workflow_status == WorkflowStatus.POSTED
    assert trx.amount == Decimal("150000000.00")

    # Invariant: Balance sheet MUST reconcile exactly: Total Assets == Total Liabilities + Equity
    bs_report = await BalanceSheetService.get_balance_sheet(
        db_session,
        org.id,
        as_of_date=date(2026, 1, 31)
    )

    assert bs_report.is_balanced is True
    assert bs_report.total_assets == Decimal("150000000.00")
    assert bs_report.current_assets.subtotal == Decimal("80000000.00")
    assert bs_report.fixed_assets.subtotal == Decimal("70000000.00")
    assert bs_report.current_liabilities.subtotal == Decimal("40000000.00")
    assert bs_report.equity.subtotal == Decimal("110000000.00")

