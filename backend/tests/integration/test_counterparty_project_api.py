import uuid

import pytest
from sqlalchemy import select

from src.models.counterparty import Counterparty
from src.models.organization import Organization


@pytest.mark.asyncio
async def test_created_customer_is_listed_and_can_own_project(client, db_session):
    organization = Organization(slug="uat-customer-project", legal_name="UAT Customer Project")
    db_session.add(organization)
    await db_session.commit()
    headers = {"X-Organization-ID": str(organization.id)}

    created = await client.post(
        "/api/v1/counterparties",
        headers=headers,
        json={
            "name": "PT Customer UAT Baru",
            "is_customer": True,
            "is_vendor": False,
            "phone": "081234567890",
            "email": "uat@example.test",
            "address": "Jakarta",
            "npwp": "01.234.567.8-901.000",
        },
    )
    assert created.status_code == 201, created.text
    customer = created.json()

    listed = await client.get("/api/v1/counterparties?is_customer=true", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["name"] for item in listed.json()] == ["PT Customer UAT Baru"]

    project = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "project_name": "Demo Perbaikan Panel Listrik",
            "customer_id": customer["id"],
            "original_contract_value": 100000000,
            "po_spk_no": "1234232000012",
            "po_spk_date": "2026-09-01",
            "start_date": "2026-09-01",
            "target_end_date": "2026-12-10",
        },
    )
    assert project.status_code == 201, project.text
    assert project.json()["customer_id"] == customer["id"]

    stored = await db_session.scalar(select(Counterparty).where(Counterparty.id == uuid.UUID(customer["id"])))
    assert stored is not None
    assert stored.contact_info == {
        "phone": "081234567890",
        "email": "uat@example.test",
        "address": "Jakarta",
    }
    assert stored.tax_id == "01.234.567.8-901.000"


@pytest.mark.asyncio
async def test_customer_listing_is_tenant_scoped_and_database_driven(client, db_session):
    org_a = Organization(slug="uat-customer-a", legal_name="UAT Customer A")
    org_b = Organization(slug="uat-customer-b", legal_name="UAT Customer B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()
    db_session.add_all([
        Counterparty(organization_id=org_a.id, name="Customer A", is_customer=True),
        Counterparty(organization_id=org_a.id, name="Vendor A", is_vendor=True),
        Counterparty(organization_id=org_b.id, name="Customer B", is_customer=True),
    ])
    await db_session.commit()

    response = await client.get(
        "/api/v1/counterparties?is_customer=true",
        headers={"X-Organization-ID": str(org_a.id)},
    )
    assert response.status_code == 200, response.text
    assert [item["name"] for item in response.json()] == ["Customer A"]
