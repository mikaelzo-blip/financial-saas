import uuid
from decimal import Decimal
from datetime import date
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.enums import ProjectStatus, CostCategory
from src.models.project import Project, ProjectBudget
from src.services.project_service import ProjectService
from src.schemas.project import ProjectCreate, ProjectStatusUpdate
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


@pytest.mark.asyncio
async def test_project_service_create_and_sequential_code(db_session: AsyncSession):
    """Test project creation, exact decimal precision, and sequential PRJ-YYYY-### code generation."""
    org = Organization(slug="org-prj-test", legal_name="Org Project Test")
    db_session.add(org)
    await db_session.commit()

    customer = Counterparty(
        organization_id=org.id,
        name="PT Pelabuhan Indonesia",
        is_customer=True
    )
    db_session.add(customer)
    await db_session.commit()

    project_service = ProjectService(db_session)

    # Create Project 1
    create_dto_1 = ProjectCreate(
        project_name="Pembangunan Dermaga Tahap 1",
        customer_id=customer.id,
        po_spk_no="SPK/2026/001",
        po_spk_date=date(2026, 1, 15),
        original_contract_value=Decimal("1500000000.50"),
        start_date=date(2026, 2, 1),
        target_end_date=date(2026, 8, 31)
    )
    prj_1 = await project_service.create_project(org.id, create_dto_1)
    await db_session.commit()

    current_year = date.today().year
    assert prj_1.project_code == f"PRJ-{current_year}-001"
    assert prj_1.project_status == ProjectStatus.PLANNED
    assert prj_1.original_contract_value == Decimal("1500000000.50")
    assert prj_1.variation_order_value == Decimal("0.00")
    assert prj_1.revised_contract_value == Decimal("1500000000.50")

    # Create Project 2 (Sequential increment)
    create_dto_2 = ProjectCreate(
        project_name="Pembangunan Dermaga Tahap 2",
        customer_id=customer.id,
        original_contract_value=Decimal("850000000.00"),
        start_date=date(2026, 3, 1)
    )
    prj_2 = await project_service.create_project(org.id, create_dto_2)
    await db_session.commit()

    assert prj_2.project_code == f"PRJ-{current_year}-002"
    assert prj_2.revised_contract_value == Decimal("850000000.00")


@pytest.mark.asyncio
async def test_project_variation_order_and_revised_contract_value(db_session: AsyncSession):
    """Test updating variation order recalculates revised contract value: original + variation = revised."""
    org = Organization(slug="org-vo-test", legal_name="Org VO Test")
    db_session.add(org)
    await db_session.flush()
    customer = Counterparty(organization_id=org.id, name="PT Energi Nusantara", is_customer=True)
    db_session.add(customer)
    await db_session.commit()

    project_service = ProjectService(db_session)
    prj = await project_service.create_project(
        org.id,
        ProjectCreate(
            project_name="Instalasi Pipa Gas",
            customer_id=customer.id,
            original_contract_value=Decimal("500000000.00"),
            start_date=date(2026, 1, 1)
        )
    )
    await db_session.commit()

    # Add Variation Order
    updated_prj = await project_service.update_variation_order(
        org.id,
        prj.id,
        Decimal("75000000.25")
    )
    await db_session.commit()

    assert updated_prj.variation_order_value == Decimal("75000000.25")
    assert updated_prj.revised_contract_value == Decimal("575000000.25")


@pytest.mark.asyncio
async def test_project_status_transitions_via_service(db_session: AsyncSession):
    """Test transitioning project status through allowed workflow in database."""
    org = Organization(slug="org-status-test", legal_name="Org Status Test")
    db_session.add(org)
    await db_session.flush()
    customer = Counterparty(organization_id=org.id, name="PT Mega Property", is_customer=True)
    db_session.add(customer)
    await db_session.commit()

    project_service = ProjectService(db_session)
    prj = await project_service.create_project(
        org.id,
        ProjectCreate(
            project_name="Gedung Perkantoran 4 Lantai",
            customer_id=customer.id,
            original_contract_value=Decimal("2000000000.00"),
            start_date=date(2026, 1, 1)
        )
    )
    await db_session.commit()

    # PLANNED -> ACTIVE
    prj_active = await project_service.update_project_status(
        org.id, prj.id, ProjectStatusUpdate(status=ProjectStatus.ACTIVE)
    )
    await db_session.commit()
    assert prj_active.project_status == ProjectStatus.ACTIVE

    # ACTIVE -> COMPLETED
    prj_completed = await project_service.update_project_status(
        org.id, prj.id, ProjectStatusUpdate(status=ProjectStatus.COMPLETED, actual_end_date=date(2026, 12, 15))
    )
    await db_session.commit()
    assert prj_completed.project_status == ProjectStatus.COMPLETED
    assert prj_completed.actual_end_date == date(2026, 12, 15)

    # COMPLETED -> CLOSED
    prj_closed = await project_service.update_project_status(
        org.id, prj.id, ProjectStatusUpdate(status=ProjectStatus.CLOSED)
    )
    await db_session.commit()
    assert prj_closed.project_status == ProjectStatus.CLOSED

    # CLOSED -> ACTIVE (Must Fail)
    with pytest.raises(InvariantViolationException):
        await project_service.update_project_status(
            org.id, prj.id, ProjectStatusUpdate(status=ProjectStatus.ACTIVE)
        )


@pytest.mark.asyncio
async def test_project_budget_lines(db_session: AsyncSession):
    """Test creating and managing budget lines per cost category for a project."""
    org = Organization(slug="org-budget-test", legal_name="Org Budget Test")
    db_session.add(org)
    await db_session.flush()
    customer = Counterparty(organization_id=org.id, name="PT Mitra Baja", is_customer=True)
    db_session.add(customer)
    await db_session.commit()

    project_service = ProjectService(db_session)
    prj = await project_service.create_project(
        org.id,
        ProjectCreate(
            project_name="Konstruksi Gudang",
            customer_id=customer.id,
            original_contract_value=Decimal("1000000000.00"),
            start_date=date(2026, 1, 1)
        )
    )
    await db_session.commit()

    # Add budget lines for MAT and SUB
    b_mat = ProjectBudget(
        project_id=prj.id,
        cost_category=CostCategory.MAT,
        budget_amount=Decimal("450000000.00"),
        notes="Baja, semen, pasir"
    )
    b_sub = ProjectBudget(
        project_id=prj.id,
        cost_category=CostCategory.SUB,
        budget_amount=Decimal("200000000.00"),
        notes="Subkon elektrikal"
    )
    db_session.add_all([b_mat, b_sub])
    await db_session.commit()

    budgets = await project_service.get_project_budgets(prj.id)
    assert len(budgets) == 2
    categories = {b.cost_category for b in budgets}
    assert CostCategory.MAT in categories
    assert CostCategory.SUB in categories


@pytest.mark.asyncio
async def test_project_rest_api_endpoints(client: AsyncClient, db_session: AsyncSession):
    """Test FastAPI REST endpoints: POST /projects, GET /projects, GET /projects/{id}."""
    org = Organization(slug="org-api-test", legal_name="Org API Test")
    db_session.add(org)
    await db_session.flush()
    customer = Counterparty(organization_id=org.id, name="PT Customer Utama", is_customer=True)
    db_session.add(customer)
    await db_session.commit()

    # 1. POST /projects
    payload = {
        "project_name": "Pembangunan Jembatan",
        "customer_id": str(customer.id),
        "po_spk_no": "PO/2026/999",
        "po_spk_date": "2026-02-10",
        "original_contract_value": 750000000,
        "start_date": "2026-03-01",
        "target_end_date": "2026-09-30"
    }
    response = await client.post(
        "/api/v1/projects",
        json=payload,
        headers={"X-Organization-ID": str(org.id)}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["project_name"] == "Pembangunan Jembatan"
    assert data["project_status"] == "PLANNED"
    assert data["billing_status"] == "NOT_INVOICED"
    assert data["collection_status"] == "NOT_DUE"
    project_id = data["id"]

    # 2. GET /projects
    list_response = await client.get(
        "/api/v1/projects",
        headers={"X-Organization-ID": str(org.id)}
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) >= 1
    assert any(p["id"] == project_id for p in items)

    # 3. GET /projects/{id}
    get_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"X-Organization-ID": str(org.id)}
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == project_id

    # 4. GET non-existent project returns 404
    missing_id = str(uuid.uuid4())
    not_found_resp = await client.get(
        f"/api/v1/projects/{missing_id}",
        headers={"X-Organization-ID": str(org.id)}
    )
    assert not_found_resp.status_code == 404
    err = not_found_resp.json()
    assert err["error"]["code"] == "NOT_FOUND"
