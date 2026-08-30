from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.integrity_service import IntegrityService
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.trial_balance_service import TrialBalanceService
from tests.reporting_support import seed_cash_profit_ledger


@pytest.mark.asyncio
async def test_all_sak_statements_reconcile_to_authoritative_ledger(db_session: AsyncSession):
    org = await seed_cash_profit_ledger(db_session, "sak-reconcile", Decimal("100000000.03"), Decimal("30000000.01"))
    start, end = date(2026, 8, 1), date(2026, 8, 31)
    profit_loss = await ProfitLossService.get_profit_and_loss(db_session, org.id, start, end)
    balance_sheet = await BalanceSheetService.get_balance_sheet(db_session, org.id, end)
    cash_flow = await CashFlowService.get_cash_flow(db_session, org.id, start, end)
    trial_balance = await TrialBalanceService.get_trial_balance(db_session, org.id, start, end, end)
    integrity = await IntegrityService.run_diagnostics(db_session, org.id, end)

    current_earnings = next(line.amount for line in balance_sheet.equity.lines if line.account_code == "3301")
    assert profit_loss.net_profit == current_earnings == Decimal("70000000.02")

    cash_account_ids = select(ChartOfAccount.id).where(ChartOfAccount.organization_id == org.id, ChartOfAccount.account_code.like("1101%"))
    cash_ledger = await db_session.scalar(select(func.sum(JournalLine.debit_amount - JournalLine.credit_amount)).join(JournalEntry).where(JournalEntry.organization_id == org.id, JournalEntry.posting_date <= end, JournalLine.account_id.in_(cash_account_ids)))
    assert cash_flow.closing_cash_balance == Decimal(str(cash_ledger)) == Decimal("70000000.02")

    assert trial_balance.total_period_debit == trial_balance.total_period_credit == Decimal("130000000.04")
    assert trial_balance.total_ending_debit == trial_balance.total_ending_credit
    assert balance_sheet.total_assets == balance_sheet.total_liabilities_and_equity
    assert balance_sheet.balancing_difference == Decimal("0.00")
    assert balance_sheet.is_balanced is True
    assert integrity.overall_status == "VALID"
    assert all(check.discrepancy == Decimal("0.00") for check in integrity.checks)
