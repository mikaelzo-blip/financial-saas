import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.journal import JournalEntry, JournalLine
from src.models.coa import ChartOfAccount
from src.models.enums import AccountType, NormalBalance, ProjectStatus, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.dashboard_service import DashboardService
from src.services.project_cost_service import ProjectCostService


@pytest.mark.asyncio
async def test_owner_dashboard_and_project_metrics(db_session: AsyncSession):
    org = Organization(slug=f"p5-org-{uuid.uuid4().hex[:6]}", legal_name="P5 Contractor PT")
    db_session.add(org)
    await db_session.flush()

    # Create Cash Account (1101) & Expense Account (5101)
    acc_cash = ChartOfAccount(
        organization_id=org.id,
        account_code="1101.01",
        account_name="Kas Operasional",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank"
    )
    acc_exp = ChartOfAccount(
        organization_id=org.id,
        account_code="5101.01",
        account_name="Biaya Material",
        account_type=AccountType.EXPENSE,
        normal_balance=NormalBalance.DEBIT,
        report_group="Biaya Langsung"
    )
    acc_rev = ChartOfAccount(
        organization_id=org.id,
        account_code="4101.01",
        account_name="Pendapatan Jasa Konstruksi",
        account_type=AccountType.REVENUE,
        normal_balance=NormalBalance.CREDIT,
        report_group="Pendapatan Proyek"
    )
    db_session.add_all([acc_cash, acc_exp, acc_rev])
    await db_session.flush()

    customer = Counterparty(organization_id=org.id, name="Owner Klien", is_customer=True)
    db_session.add(customer)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        customer_id=customer.id,
        project_name="Renovasi Kantor",
        project_code="PRJ-RNV-01",
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00")
    )
    db_session.add(project)
    await db_session.flush()

    # Create Transactions for Journal Entries (strict FK)
    trx1 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-P5-001",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 3, 10),
        amount=Decimal("50000000.00"),
        description="Termin 1 Cash Received",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    trx2 = Transaction(
        organization_id=org.id,
        transaction_code="TRX-P5-002",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 3, 15),
        amount=Decimal("20000000.00"),
        description="Pembelian Material Semen",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add_all([trx1, trx2])
    await db_session.flush()

    # Cash In: Rp 50.000.000 (Dr 1101 / Cr 4101)
    je1 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx1.id,
        entry_number="JE-P5-001",
        posting_date=date(2026, 3, 10),
        total_debit=Decimal("50000000.00"),
        total_credit=Decimal("50000000.00"),
        description="Termin 1 Cash Received"
    )
    db_session.add(je1)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je1.id, account_id=acc_cash.id, line_number=1, debit_amount=Decimal("50000000.00"), credit_amount=Decimal("0.00")),
        JournalLine(journal_entry_id=je1.id, account_id=acc_rev.id, line_number=2, debit_amount=Decimal("0.00"), credit_amount=Decimal("50000000.00"), project_id=project.id)
    ])

    # Cash Out / Project Spending: Rp 20.000.000 (Dr 5101 / Cr 1101)
    je2 = JournalEntry(
        organization_id=org.id,
        transaction_id=trx2.id,
        entry_number="JE-P5-002",
        posting_date=date(2026, 3, 15),
        total_debit=Decimal("20000000.00"),
        total_credit=Decimal("20000000.00"),
        description="Pembelian Material Semen"
    )
    db_session.add(je2)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je2.id, account_id=acc_exp.id, line_number=1, debit_amount=Decimal("20000000.00"), credit_amount=Decimal("0.00"), project_id=project.id),
        JournalLine(journal_entry_id=je2.id, account_id=acc_cash.id, line_number=2, debit_amount=Decimal("0.00"), credit_amount=Decimal("20000000.00"))
    ])
    await db_session.flush()

    # Query Owner Dashboard
    summary = await DashboardService.get_dashboard_summary(
        db_session,
        org.id,
        as_of_date=date(2026, 3, 31)
    )

    # Invariants for Owner Dashboard
    # 1. Total Cash & Bank = 50M - 20M = 30M
    assert summary.cash_and_bank_balance == Decimal("30000000.00")
    # 2. Cash In = 50M
    assert summary.cash_in_period == Decimal("50000000.00")
    # 3. Cash Out = 20M
    assert summary.cash_out_period == Decimal("20000000.00")
    # 4. Net Cash Flow = 30M
    assert summary.net_cash_flow == Decimal("30000000.00")
    # 5. Project Spending = 20M
    assert summary.project_spending == Decimal("20000000.00")

    # Query Project Financial Summary
    cost_service = ProjectCostService(db_session)
    proj_summary = await cost_service.get_project_financial_summary(org.id, project.id)

    assert proj_summary["contract"]["revised_contract_value"] == Decimal("100000000.00")
    assert proj_summary["pnl"]["actual_project_cost"] == Decimal("20000000.00")
    assert proj_summary["pnl"]["recognized_revenue"] == Decimal("50000000.00")
    assert proj_summary["pnl"]["gross_profit"] == Decimal("30000000.00")
    assert "cost_categories" in proj_summary
    assert "vendor_spend" in proj_summary
    assert "documents" in proj_summary
    assert "unallocated_items" in proj_summary
    assert proj_summary["cash_and_billing"]["cash_spent"] == Decimal("0.00")
    assert proj_summary["cash_and_billing"]["total_invoiced"] == Decimal("0.00")
