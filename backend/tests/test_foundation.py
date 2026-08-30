import pytest
from httpx import AsyncClient
from src.core.config import settings
from src.core.database import Base
from src.core.exceptions import (
    AppException,
    EntityNotFoundException,
    InvariantViolationException,
    DuplicateEntityException
)


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    """Verify application starts up and responds to healthcheck."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == settings.PROJECT_NAME


def test_settings_initialization():
    """Verify application configuration has correct defaults."""
    assert settings.PROJECT_NAME == "Financial SaaS Backend"
    assert settings.API_V1_STR == "/api/v1"
    assert "postgresql" in settings.DATABASE_URL
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0


def test_database_base_metadata():
    """Verify SQLAlchemy declarative Base has constraint naming conventions."""
    assert Base.metadata is not None
    assert "pk" in Base.metadata.naming_convention
    assert "fk" in Base.metadata.naming_convention
    assert "ck" in Base.metadata.naming_convention


def test_custom_exceptions_structure():
    """Verify custom domain exceptions have required attributes."""
    exc = InvariantViolationException("Debit != Credit", details={"debit": 100, "credit": 90})
    assert exc.status_code == 422
    assert exc.error_code == "INVARIANT_VIOLATION"
    assert exc.details["debit"] == 100

    not_found = EntityNotFoundException("Project", "PRJ-2026-001")
    assert not_found.status_code == 404
    assert not_found.error_code == "NOT_FOUND"
    assert not_found.details["identifier"] == "PRJ-2026-001"

    dup = DuplicateEntityException("Duplicate file hash detected")
    assert dup.status_code == 409
    assert dup.error_code == "DUPLICATE_ENTITY"
