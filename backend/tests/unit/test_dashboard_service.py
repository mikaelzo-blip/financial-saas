import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, ProjectStatus, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_dashboard_kpis_and_runway(db_session: AsyncSession):
    org = Organization(slug="pt-dash-test", legal_name="PT Dashboard Test")
    db_session.add(org)
    await db_session.flush()

    cust = Counterparty(organization_id=org.id, name="Klien Dash", is_customer=True)
    db_session.add(cust)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-DASH-01",
        project_name="Proyek Dashboard",
        customer_id=cust.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-DASH",
        original_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 1, 1)
    )
    db_session.add(proj)
    await db_session.flush()

    acc_kas = ChartOfAccount(organization_id=org.id, account_code="1101.01", account_name="Kas", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_rev = ChartOfAccount(organization_id=org.id, account_code="4101.01", account_name="Pendapatan", account_type=AccountType.REVENUE, normal_balance=NormalBalance.CREDIT, report_group="REVENUE")
    acc_opex = ChartOfAccount(organization_id=org.id, account_code="6101.01", account_name="Beban", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="OPEX")
    db_session.add_all([acc_kas, acc_rev, acc_opex])
    await db_session.flush()

    # Inflow: Revenue 120M -> Kas 120M
    trx1 = Transaction(organization_id=org.id, transaction_code="TRX-D1", transaction_type=TransactionType.CUSTOMER_PAYMENT, transaction_date=date(2026, 1, 15), amount=Decimal("120000000.00"), description="Income", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx1)
    await db_session.flush()
    je1 = JournalEntry(organization_id=org.id, entry_number="JE-D1", transaction_id=trx1.id, posting_date=date(2026, 1, 15), description="Income", total_debit=Decimal("120000000.00"), total_credit=Decimal("120000000.00"), is_balanced=True)
    db_session.add(je1)
    await db_session.flush()
    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_kas.id, debit_amount=Decimal("120000000.00"), credit_amount=Decimal("0.00"))
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_rev.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("120000000.00"))
    db_session.add_all([jl1_1, jl1_2])

    # Outflow: Expense 20M -> Kas -20M
    trx2 = Transaction(organization_id=org.id, transaction_code="TRX-D2", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 1, 20), amount=Decimal("20000000.00"), description="Expense", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add(trx2)
    await db_session.flush()
    je2 = JournalEntry(organization_id=org.id, entry_number="JE-D2", transaction_id=trx2.id, posting_date=date(2026, 1, 20), description="Expense", total_debit=Decimal("20000000.00"), total_credit=Decimal("20000000.00"), is_balanced=True)
    db_session.add(je2)
    await db_session.flush()
    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_opex.id, debit_amount=Decimal("20000000.00"), credit_amount=Decimal("0.00"))
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("20000000.00"))
    db_session.add_all([jl2_1, jl2_2])
    await db_session.commit()

    # Query Dashboard
    dash = await DashboardService.get_dashboard_summary(db_session, org.id, as_of_date=date(2026, 1, 31))
    assert dash.cash_and_bank_balance == Decimal("100000000.00")
    assert dash.revenue_ytd == Decimal("120000000.00")
    assert dash.net_profit_ytd == Decimal("100000000.00")
    assert dash.active_projects_count == 1
    assert dash.integrity_status == "VALID"
    assert dash.estimated_monthly_burn_rate == Decimal("20000000.00")
    assert dash.cash_runway_months == Decimal("5.0")
