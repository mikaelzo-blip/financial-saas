import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project, ProjectBudget
from src.models.enums import CostCategory, ProjectStatus
from src.services.reporting.budget_service import BudgetVsActualService


@pytest.mark.asyncio
async def test_budget_vs_actual_service(db_session: AsyncSession):
    org = Organization(slug="pt-bva-test", legal_name="PT Budget Test")
    db_session.add(org)
    await db_session.flush()

    client = Counterparty(organization_id=org.id, name="Klien Proyek B", is_customer=True)
    db_session.add(client)
    await db_session.flush()

    # 1. Project without budget
    proj_no_budget = Project(
        organization_id=org.id,
        project_code="PRJ-NO-BUDGET",
        project_name="Proyek Tanpa Anggaran",
        customer_id=client.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-002",
        original_contract_value=Decimal("100000000.00"),
        variation_order_value=Decimal("0.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31)
    )
    db_session.add(proj_no_budget)
    await db_session.flush()

    res_no_budget = await BudgetVsActualService.get_budget_vs_actual(db_session, org.id, proj_no_budget.id)
    assert res_no_budget.has_budget is False
    assert res_no_budget.budget_status_label == "Anggaran Belum Ditetapkan"

    # 2. Project with budget
    proj_with_budget = Project(
        organization_id=org.id,
        project_code="PRJ-WITH-BUDGET",
        project_name="Proyek Dengan Anggaran",
        customer_id=client.id,
        project_status=ProjectStatus.ACTIVE,
        po_spk_no="SPK-003",
        original_contract_value=Decimal("200000000.00"),
        variation_order_value=Decimal("0.00"),
        revised_contract_value=Decimal("200000000.00"),
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 12, 31)
    )
    db_session.add(proj_with_budget)
    await db_session.flush()

    b1 = ProjectBudget(project_id=proj_with_budget.id, cost_category=CostCategory.MAT, budget_amount=Decimal("50000000.00"))
    b2 = ProjectBudget(project_id=proj_with_budget.id, cost_category=CostCategory.LAB, budget_amount=Decimal("30000000.00"))
    db_session.add_all([b1, b2])
    await db_session.commit()

    res_with_budget = await BudgetVsActualService.get_budget_vs_actual(db_session, org.id, proj_with_budget.id)
    assert res_with_budget.has_budget is True
    assert res_with_budget.budget_status_label == "Anggaran Ditetapkan"
    assert res_with_budget.total_budget == Decimal("80000000.00")
