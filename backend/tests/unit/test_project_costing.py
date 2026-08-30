from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project, ProjectBudget
from src.models.enums import ProjectStatus, TransactionType, CostCategory
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.receivable_service import CustomerARService
from src.services.project_cost_service import ProjectCostService


@pytest.mark.asyncio
async def test_project_cost_breakdown_and_profitability(db_session: AsyncSession):
    """
    Test Project Cost & Profitability Derivation:
    1. Project created with Revised Contract Value = Rp 500.000.000 (Original 450M + VO 50M).
    2. Budgets: MAT = 150M, SUB = 100M, LAB = 50M.
    3. Transactions:
       - Direct Material Purchase: Rp 120.000.000 (MAT)
       - Subcontractor Bill: Rp 80.000.000 (SUB)
       - Labor Payroll: Rp 45.000.000 (LAB)
       - Total Actual Cost = Rp 245.000.000
    4. Customer Invoice (Progress 60%): Rp 300.000.000 (Recognized Revenue)
    5. Profitability:
       - Gross Profit = 300M - 245M = Rp 55.000.000
       - Margin % = (55M / 300M) * 100 = 18.33%
    6. Verify all numbers are exact Decimals derived dynamically.
    """
    org = Organization(slug="org-cost-unit", legal_name="Org Cost Unit")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    customer = Counterparty(organization_id=org.id, name="PT Properti Sejahtera", is_customer=True)
    vendor = Counterparty(organization_id=org.id, name="PT Supplier Material", is_vendor=True)
    subcon = Counterparty(organization_id=org.id, name="PT Subkon Spesialis", is_vendor=True)
    db_session.add_all([customer, vendor, subcon])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-901",
        project_name="Gedung Olahraga Kampus",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        original_contract_value=Decimal("450000000.00"),
        variation_order_value=Decimal("50000000.00"),
        revised_contract_value=Decimal("500000000.00"),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.flush()

    # Budgets
    b_mat = ProjectBudget(project_id=project.id, cost_category=CostCategory.MAT, budget_amount=Decimal("150000000.00"))
    b_sub = ProjectBudget(project_id=project.id, cost_category=CostCategory.SUB, budget_amount=Decimal("100000000.00"))
    b_lab = ProjectBudget(project_id=project.id, cost_category=CostCategory.LAB, budget_amount=Decimal("50000000.00"))
    db_session.add_all([b_mat, b_sub, b_lab])
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    ar_svc = CustomerARService(db_session)
    cost_svc = ProjectCostService(db_session)

    # Initial Capital
    t_cap = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("500000000.00"),
            description="Modal Kerja"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_cap.id)
    await db_session.commit()

    # Cost 1: Material (120M)
    t1 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("120000000.00"),
            counterparty_id=vendor.id,
            description="Besi & Semen Proyek",
            project_id=project.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t1.id)
    await db_session.commit()

    # Cost 2: Subcontractor (80M)
    t2 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("80000000.00"),
            counterparty_id=subcon.id,
            description="Tagihan Subkon Pasang Baja",
            project_id=project.id,
            cost_category=CostCategory.SUB
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t2.id)
    await db_session.commit()

    # Cost 3: Labor (45M)
    t3 = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("45000000.00"),
            description="Upah Tukang & Mandor Periode 1",
            project_id=project.id,
            cost_category=CostCategory.LAB
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t3.id)
    await db_session.commit()

    # Revenue: Customer Invoice Progress (300M)
    t_inv = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.CUSTOMER_INVOICE,
            transaction_date=date(2026, 1, 25),
            amount=Decimal("300000000.00"),
            counterparty_id=customer.id,
            description="Termin 1 (60% Progress)",
            project_id=project.id
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_inv.id)
    await db_session.commit()

    # Issue invoice in AR sub-ledger
    await ar_svc.issue_customer_invoice(
        organization_id=org.id,
        customer_id=customer.id,
        project_id=project.id,
        invoice_date=date(2026, 1, 25),
        total_amount=Decimal("300000000.00"),
        transaction_id=t_inv.id
    )
    await db_session.commit()

    # Verify Cost Breakdown
    costs = await cost_svc.get_project_cost_breakdown(org.id, project.id)
    assert costs["total_actual_cost"] == Decimal("245000000.00")
    assert costs["category_breakdown"]["MAT"] == Decimal("120000000.00")
    assert costs["category_breakdown"]["SUB"] == Decimal("80000000.00")
    assert costs["category_breakdown"]["LAB"] == Decimal("45000000.00")
    assert costs["total_budgeted_cost"] == Decimal("300000000.00")
    assert costs["total_cost_variance"] == Decimal("55000000.00")

    # Verify Profitability
    pnl = await cost_svc.get_project_profitability(org.id, project.id)
    assert pnl["recognized_revenue"] == Decimal("300000000.00")
    assert pnl["actual_project_cost"] == Decimal("245000000.00")
    assert pnl["gross_profit"] == Decimal("55000000.00")
    assert pnl["margin_percentage"] == Decimal("18.33")

    # Verify Full Summary
    summary = await cost_svc.get_project_financial_summary(org.id, project.id)
    assert summary["contract"]["revised_contract_value"] == Decimal("500000000.00")
    assert summary["cash_and_billing"]["total_invoiced"] == Decimal("300000000.00")
