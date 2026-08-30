import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.coa import ChartOfAccount
from src.models.journal import JournalEntry, JournalLine
from src.models.enums import AccountType, NormalBalance, CostCategory, ProjectStatus, TransactionType, WorkflowStatus
from src.models.transaction import Transaction
from src.services.reporting.project_reporting_service import ProjectReportingService


@pytest.mark.asyncio
async def test_project_profitability_and_cash_position(db_session: AsyncSession):
    org = Organization(slug="pt-proj-test", legal_name="PT Project Report Test")
    db_session.add(org)
    await db_session.flush()

    client = Counterparty(organization_id=org.id, name="Klien Proyek A", is_customer=True)
    db_session.add(client)
    await db_session.flush()

    proj = Project(
        organization_id=org.id,
        project_code="PRJ-REP-001",
        project_name="Proyek Gedung Serbaguna",
        customer_id=client.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-001",
        original_contract_value=Decimal("500000000.00"),
        variation_order_value=Decimal("0.00"),
        revised_contract_value=Decimal("500000000.00"),
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31)
    )
    db_session.add(proj)
    await db_session.flush()

    # Accounts
    acc_kas = ChartOfAccount(organization_id=org.id, account_code="1101.01", account_name="Kas", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="CURRENT_ASSETS")
    acc_mat = ChartOfAccount(organization_id=org.id, account_code="5101.01", account_name="Bahan", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    acc_lab = ChartOfAccount(organization_id=org.id, account_code="5103.01", account_name="Upah", account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="COGS")
    db_session.add_all([acc_kas, acc_mat, acc_lab])
    await db_session.flush()

    # 1. Invoiced: 200M (Paid: 150M)
    inv = CustomerInvoice(
        organization_id=org.id,
        customer_id=client.id,
        project_id=proj.id,
        invoice_code="INV-PRJ-01",
        invoice_date=date(2026, 2, 1),
        due_date=date(2026, 3, 1),
        total_amount=Decimal("200000000.00"),
        status="PARTIAL"
    )
    db_session.add(inv)
    await db_session.flush()

    trx_pay = Transaction(
        organization_id=org.id,
        transaction_code="TRX-REC-01",
        transaction_type=TransactionType.CUSTOMER_PAYMENT,
        transaction_date=date(2026, 2, 10),
        amount=Decimal("150000000.00"),
        description="Termin Proyek",
        source_channel="WEB",
        workflow_status=WorkflowStatus.POSTED
    )
    db_session.add(trx_pay)
    await db_session.flush()

    alloc = CustomerPaymentAllocation(
        invoice_id=inv.id,
        payment_transaction_id=trx_pay.id,
        allocated_amount=Decimal("150000000.00")
    )
    db_session.add(alloc)
    await db_session.flush()

    # 2. Direct Costs: Material 60M (Dr Material, Cr Kas), Labor 40M (Dr Labor, Cr Kas)
    trx1 = Transaction(organization_id=org.id, transaction_code="TRX-MAT-01", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 2, 5), amount=Decimal("60000000.00"), description="Material", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    trx2 = Transaction(organization_id=org.id, transaction_code="TRX-LAB-01", transaction_type=TransactionType.DIRECT_PURCHASE, transaction_date=date(2026, 2, 10), amount=Decimal("40000000.00"), description="Upah", source_channel="WEB", workflow_status=WorkflowStatus.POSTED)
    db_session.add_all([trx1, trx2])
    await db_session.flush()

    je1 = JournalEntry(organization_id=org.id, entry_number="JE-MAT-01", transaction_id=trx1.id, posting_date=date(2026, 2, 5), description="Material", total_debit=Decimal("60000000.00"), total_credit=Decimal("60000000.00"), is_balanced=True)
    je2 = JournalEntry(organization_id=org.id, entry_number="JE-LAB-01", transaction_id=trx2.id, posting_date=date(2026, 2, 10), description="Labor", total_debit=Decimal("40000000.00"), total_credit=Decimal("40000000.00"), is_balanced=True)
    db_session.add_all([je1, je2])
    await db_session.flush()

    jl1_1 = JournalLine(journal_entry_id=je1.id, line_number=1, account_id=acc_mat.id, debit_amount=Decimal("60000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id, cost_category=CostCategory.MAT)
    jl1_2 = JournalLine(journal_entry_id=je1.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("60000000.00"), project_id=proj.id)

    jl2_1 = JournalLine(journal_entry_id=je2.id, line_number=1, account_id=acc_lab.id, debit_amount=Decimal("40000000.00"), credit_amount=Decimal("0.00"), project_id=proj.id, cost_category=CostCategory.LAB)
    jl2_2 = JournalLine(journal_entry_id=je2.id, line_number=2, account_id=acc_kas.id, debit_amount=Decimal("0.00"), credit_amount=Decimal("40000000.00"), project_id=proj.id)
    db_session.add_all([jl1_1, jl1_2, jl2_1, jl2_2])
    await db_session.commit()

    # Query Profitability
    prof = await ProjectReportingService.get_project_profitability(db_session, org.id, proj.id)
    assert prof.revenue_recognized == Decimal("200000000.00")
    assert prof.total_project_cost == Decimal("100000000.00")
    assert prof.gross_profit == Decimal("100000000.00")
    assert prof.gross_margin_percentage == Decimal("50.00")

    # Query Cash Position
    cash_pos = await ProjectReportingService.get_project_cash_position(db_session, org.id, proj.id)
    assert cash_pos.invoiced_amount == Decimal("200000000.00")
    assert cash_pos.cash_received == Decimal("150000000.00")
    assert cash_pos.receivable_outstanding == Decimal("50000000.00")
    assert cash_pos.cash_spent == Decimal("100000000.00")
    assert cash_pos.net_cash_position == Decimal("50000000.00")
    assert cash_pos.is_surplus is True
