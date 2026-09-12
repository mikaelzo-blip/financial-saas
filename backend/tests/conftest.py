pytest_plugins = [
    "tests.integration.f012_postgresql_support",
    "tests.integration.fin001_postgresql_support",
]

from typing import AsyncGenerator
from uuid import UUID

import pytest
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.auth import require_application_user
from src.core.database import Base, get_db
from src.core.security import decode_access_token
from src.models.enums import UserRole
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

    async def override_authenticated_user(request: Request) -> User | None:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            payload = decode_access_token(auth[7:])
            if payload and payload.get("exp") and "sub" in payload:
                try:
                    user_id = UUID(payload["sub"])
                    user = await db_session.get(User, user_id)
                    if user and user.is_active:
                        org_id_header = request.headers.get("X-Organization-ID")
                        if org_id_header and org_id_header != str(user.organization_id):
                            raise HTTPException(403, "Organization mismatch")
                        user_id_header = request.headers.get("X-User-ID")
                        if user_id_header and user_id_header != str(user.id):
                            raise HTTPException(403, "User mismatch")
                        return user
                except (ValueError, TypeError):
                    pass

        user_id = request.headers.get("X-User-ID")
        organization_id = request.headers.get("X-Organization-ID")
        if user_id and organization_id:
            try:
                uid = UUID(user_id)
                user = await db_session.get(User, uid)
                if not user or str(user.organization_id) != organization_id:
                    raise HTTPException(403, "Organization mismatch")
                return user
            except (ValueError, TypeError):
                raise HTTPException(401, "Authenticated user required")

        if organization_id:
            try:
                oid = UUID(organization_id)
                user = await db_session.scalar(
                    select(User).where(User.organization_id == oid, User.is_active.is_(True))
                )
                if not user:
                    user = User(
                        organization_id=oid,
                        email=f"test-admin-{organization_id[:8]}@example.test",
                        full_name="Test Admin",
                        password_hash="not-used",
                        role=UserRole.ADMIN,
                        is_active=True,
                    )
                    db_session.add(user)
                    await db_session.flush()
                return user
            except (ValueError, TypeError):
                raise HTTPException(401, "Authenticated user required")

        return None

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
