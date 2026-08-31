from uuid import uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from src.core.config import Settings
from src.core.security import hash_password
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User


def production_settings(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+asyncpg://app:secret@db.internal/financial_saas",
        "SYNC_DATABASE_URL": "postgresql://app:secret@db.internal/financial_saas",
        "SECRET_KEY": "a-production-signing-secret-with-at-least-32-characters",
        "STORAGE_DIR": "C:/financial-saas/documents",
        "BACKEND_CORS_ORIGINS": ["https://finance.example.com"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "override",
    [
        {"DEBUG": True},
        {"SECRET_KEY": "change-this-insecure-secret-key-in-production"},
        {"BACKEND_CORS_ORIGINS": ["*"]},
        {"DATABASE_URL": "sqlite:///financial.db"},
        {"SYNC_DATABASE_URL": "postgresql://postgres:***@localhost/db"},
        {"STORAGE_DIR": "backend/storage"},
    ],
)
def test_production_configuration_rejects_unsafe_defaults(override):
    with pytest.raises(ValidationError):
        production_settings(**override)


def test_production_database_pool_settings_are_bounded():
    settings = production_settings(DB_POOL_SIZE=10, DB_MAX_OVERFLOW=20, DB_POOL_TIMEOUT_SECONDS=15, DB_POOL_RECYCLE_SECONDS=900)
    assert settings.DB_POOL_SIZE == 10
    with pytest.raises(ValidationError):
        production_settings(DB_POOL_SIZE=0)


@pytest.mark.asyncio
async def test_login_returns_tenant_bound_jwt_and_rejects_bad_credentials(client: AsyncClient, db_session):
    organization = Organization(slug="login-org", legal_name="Login Org")
    db_session.add(organization)
    await db_session.flush()
    user = User(
        organization_id=organization.id,
        email="admin@example.test",
        full_name="Admin",
        password_hash=hash_password("CorrectHorseBatteryStaple!"),
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "CorrectHorseBatteryStaple!"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["organization_id"] == str(organization.id)
    assert body["user"]["id"] == str(user.id)
    assert body["access_token"]

    invalid = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "unknown@example.test", "password": "wrong-password"})
    assert invalid.status_code == unknown.status_code == 401
    assert invalid.json()["detail"] == unknown.json()["detail"]


@pytest.mark.asyncio
async def test_production_api_rejects_missing_or_forged_tenant_identity(client, db_session, monkeypatch):
    from src.core.config import settings

    organization = Organization(slug="tenant-bound", legal_name="Tenant Bound")
    db_session.add(organization)
    await db_session.flush()
    user = User(
        organization_id=organization.id,
        email="manager@example.test",
        full_name="Manager",
        password_hash=hash_password("CorrectHorseBatteryStaple!"),
        role=UserRole.MANAGER,
    )
    db_session.add(user)
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "CorrectHorseBatteryStaple!"},
    )
    token = login.json()["access_token"]
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    assert (await client.get("/api/v1/projects")).status_code == 401
    forged = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(uuid4()),
        "X-User-ID": str(user.id),
    }
    assert (await client.get("/api/v1/projects", headers=forged)).status_code == 403
    valid = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(organization.id),
        "X-User-ID": str(user.id),
    }
    assert (await client.get("/api/v1/projects", headers=valid)).status_code == 200


@pytest.mark.asyncio
async def test_liveness_security_headers_correlation_and_readiness(client: AsyncClient):
    health = await client.get("/health", headers={"X-Request-ID": "request-123"})
    assert health.status_code == 200
    assert health.headers["X-Request-ID"] == "request-123"
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["X-Frame-Options"] == "DENY"
    assert health.headers["Referrer-Policy"] == "no-referrer"

    ready = await client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_bootstrap_creates_complete_tenant_once(db_session):
    from src.cli.bootstrap import bootstrap_organization

    result = await bootstrap_organization(
        db_session,
        slug="bootstrap-org",
        legal_name="Bootstrap Org",
        admin_email="owner@example.test",
        admin_name="Owner",
        admin_password="CorrectHorseBatteryStaple!",
    )
    await db_session.commit()
    assert result["coa_created"] > 0
    assert result["payment_accounts_created"] > 0
    user = await db_session.scalar(select(User).where(User.email == "owner@example.test"))
    assert user is not None and user.role == UserRole.ADMIN

    with pytest.raises(ValueError, match="already exists"):
        await bootstrap_organization(
            db_session,
            slug="bootstrap-org",
            legal_name="Bootstrap Org",
            admin_email="owner@example.test",
            admin_name="Owner",
            admin_password="CorrectHorseBatteryStaple!",
        )
