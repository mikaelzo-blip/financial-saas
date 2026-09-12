pytest_plugins = [
    "tests.integration.f012_postgresql_support",
    "tests.integration.fin001_postgresql_support",
]

from typing import AsyncGenerator
from uuid import UUID

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.auth import require_application_user
from src.core.database import Base, get_db
from src.models.user import User
from src.main import create_application

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def authenticated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_application()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_authenticated_user(request: Request) -> User:
        user_id = request.headers.get("X-User-ID")
        organization_id = request.headers.get("X-Organization-ID")
        if not user_id or not organization_id:
            raise AssertionError("authenticated_client requires a seeded user identity")
        user = await db_session.get(User, UUID(user_id))
        if not user or str(user.organization_id) != organization_id:
            raise AssertionError("authenticated_client requires a matching seeded user identity")
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_application_user] = override_authenticated_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(authenticated_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    yield authenticated_client


@pytest.fixture
async def security_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_application()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
