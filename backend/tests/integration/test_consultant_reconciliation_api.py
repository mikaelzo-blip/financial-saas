from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.models.organization import Organization
from src.models.user import User
from src.models.enums import UserRole
from src.services.coa_seeder import seed_standard_coa


@pytest.mark.asyncio
async def test_consultant_reconciliation_api_flow(db_session: AsyncSession):
    # Setup test tenant and user
    org = Organization(slug="org-api-consultant-rec", legal_name="PT Konsultan Rec API")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)

    user = User(
        organization_id=org.id,
        email="owner@konsultan-rec.id",
        full_name="Owner Konsultan",
        password_hash="test-hash",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.commit()

    # Override auth and db dependencies for integration test
    from src.api.auth import require_application_user
    from src.core.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_application_user] = lambda: user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-Organization-ID": str(org.id)}

            # 1. Fetch verified 2023 statement
            resp_2023 = await client.get("/api/v1/reports/consultant-reconciliation/verified/2023", headers=headers)
            assert resp_2023.status_code == 200
            data_2023 = resp_2023.json()
            assert data_2023["year"] == 2023
            assert Decimal(data_2023["revenue"]) == Decimal("1569062699.00")
            assert Decimal(data_2023["total_assets"]) == Decimal("944566738.00")

            # 2. Fetch verified 2024 statement
            resp_2024 = await client.get("/api/v1/reports/consultant-reconciliation/verified/2024", headers=headers)
            assert resp_2024.status_code == 200
            data_2024 = resp_2024.json()
            assert data_2024["year"] == 2024
            assert Decimal(data_2024["revenue"]) == Decimal("3271190594.00")
            assert Decimal(data_2024["total_assets"]) == Decimal("1077775151.00")

            # 3. Fetch verified 2025 statement
            resp_2025 = await client.get("/api/v1/reports/consultant-reconciliation/verified/2025", headers=headers)
            assert resp_2025.status_code == 200
            data_2025 = resp_2025.json()
            assert data_2025["year"] == 2025
            assert Decimal(data_2025["revenue"]) == Decimal("6047503085.00")
            assert Decimal(data_2025["profit_after_tax"]) == Decimal("552216471.00")
            assert Decimal(data_2025["current_year_earnings"]) == Decimal("552008841.00")

            # 4. Reconcile verified 2024 against live ledger
            resp_rec_2024 = await client.post("/api/v1/reports/consultant-reconciliation/reconcile-verified/2024", headers=headers)
            assert resp_rec_2024.status_code == 200
            rec_2024 = resp_rec_2024.json()
            assert rec_2024["year"] == 2024
            assert rec_2024["statement_integrity"]["is_balanced"] is True
            assert len(rec_2024["pl_comparisons"]) == 10
            assert len(rec_2024["bs_comparisons"]) == 17

            # 5. Reconcile verified 2025 against live ledger (detecting consultant internal defect)
            resp_rec_2025 = await client.post("/api/v1/reports/consultant-reconciliation/reconcile-verified/2025", headers=headers)
            assert resp_rec_2025.status_code == 200
            rec_2025 = resp_rec_2025.json()
            assert rec_2025["statement_integrity"]["is_balanced"] is False
            assert Decimal(rec_2025["statement_integrity"]["assets_liabilities_equity_discrepancy"]) == Decimal("207630.00")
            assert Decimal(rec_2025["statement_integrity"]["pat_vs_current_earnings_discrepancy"]) == Decimal("207630.00")

            # 6. Test 404 for unverified year
            resp_404 = await client.get("/api/v1/reports/consultant-reconciliation/verified/2019", headers=headers)
            assert resp_404.status_code == 404
    finally:
        app.dependency_overrides.pop(require_application_user, None)
        app.dependency_overrides.pop(get_db, None)
