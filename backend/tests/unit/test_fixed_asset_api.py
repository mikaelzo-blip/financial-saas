import pytest
import uuid
from datetime import date
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.user import User, UserRole
from src.services.coa_seeder import seed_standard_coa


@pytest.mark.asyncio
async def test_fixed_asset_api_lifecycle(client: AsyncClient, db_session: AsyncSession):
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        slug=f"api-fa-{uuid.uuid4().hex[:6]}",
        legal_name="PT Fixed Asset API Test"
    )
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org_id)

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        organization_id=org_id,
        email=f"fa-api.{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="FA API Admin",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    await db_session.flush()

    headers = {
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user_id)
    }

    # 1. Capitalization guidance endpoint
    guidance_resp = await client.get(
        "/api/v1/fixed-assets/guidance/capitalization",
        params={"amount": "12000000.00", "benefit_months": 24},
        headers=headers
    )
    assert guidance_resp.status_code == 200
    guidance_data = guidance_resp.json()
    assert guidance_data["qualifies_as_fixed_asset"] is True
    assert guidance_data["recommendation"] == "FIXED_ASSET_CANDIDATE"

    # 2. Create Fixed Asset
    create_payload = {
        "asset_code": "AST-API-001",
        "asset_name": "Generator 50 KVA",
        "asset_category": "ALAT_BERAT",
        "purchase_date": "2026-01-05",
        "available_for_use_date": "2026-01-10",
        "purchase_cost": "96000000.00",
        "salvage_value": "0.00",
        "useful_life_months": 96
    }
    create_resp = await client.post(
        "/api/v1/fixed-assets",
        json=create_payload,
        headers=headers
    )
    assert create_resp.status_code == 201
    asset_data = create_resp.json()
    assert asset_data["asset_code"] == "AST-API-001"
    assert asset_data["net_book_value"] == "96000000.00"
    asset_id = asset_data["id"]

    # 3. List Fixed Assets
    list_resp = await client.get("/api/v1/fixed-assets", headers=headers)
    assert list_resp.status_code == 200
    assets = list_resp.json()
    assert len(assets) >= 1
    assert any(a["id"] == asset_id for a in assets)

    # 4. Get Fixed Asset Detail
    get_resp = await client.get(f"/api/v1/fixed-assets/{asset_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["asset_code"] == "AST-API-001"

    # 5. Run Single Asset Depreciation
    dep_resp = await client.post(
        f"/api/v1/fixed-assets/{asset_id}/depreciate",
        json={"period_date": "2026-01-31"},
        headers=headers
    )
    assert dep_resp.status_code == 200
    dep_data = dep_resp.json()
    assert dep_data["depreciation_amount"] == "1000000.00"
    assert dep_data["accumulated_depreciation"] == "1000000.00"
    assert dep_data["net_book_value"] == "95000000.00"

    # 6. Run Batch Depreciation for Feb 2026
    batch_resp = await client.post(
        "/api/v1/fixed-assets/depreciate-batch",
        json={"period_date": "2026-02-28"},
        headers=headers
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["total_assets_processed"] >= 1
    assert Decimal(str(batch_data["total_depreciation_amount"])) >= Decimal("1000000.00")

    # 7. Dispose Asset
    dispose_resp = await client.post(
        f"/api/v1/fixed-assets/{asset_id}/dispose",
        headers=headers
    )
    assert dispose_resp.status_code == 200
    assert dispose_resp.json()["status"] == "DISPOSED"
