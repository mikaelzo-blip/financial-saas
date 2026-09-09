"""Browser-user authentication and production tenant binding."""

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import AuthorizationException
from src.core.security import create_access_token, decode_access_token, verify_password
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


def session_payload(user: User, organization: Organization, access_token: str | None = None) -> dict:
    payload = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "organization_id": str(user.organization_id),
            "organization_name": organization.legal_name,
        },
    }
    if access_token:
        payload.update({"access_token": access_token, "token_type": "bearer"})
    return payload


async def authenticated_user(request: Request, db: AsyncSession) -> User:
    authorization = request.headers.get("Authorization", "")
    payload = decode_access_token(authorization[7:]) if authorization.startswith("Bearer ") else None
    if not payload:
        raise HTTPException(401, "Authenticated user required")
    try:
        from uuid import UUID
        user_id = UUID(payload["sub"])
        organization_id = UUID(payload["organization_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(401, "Authenticated user required") from None
    user = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.organization_id == organization_id,
            User.is_active.is_(True),
        )
    )
    if not user:
        raise HTTPException(401, "Authenticated user required")
    if request.headers.get("X-Organization-ID") != str(user.organization_id):
        raise HTTPException(403, "Organization mismatch")
    if request.headers.get("X-User-ID") != str(user.id):
        raise HTTPException(403, "User mismatch")
    return user


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    users = (
        await db.scalars(
            select(User).where(User.email == data.email.strip().lower(), User.is_active.is_(True)).limit(2)
        )
    ).all()
    if len(users) != 1 or not verify_password(data.password, users[0].password_hash):
        raise HTTPException(401, "Invalid email or password")
    user = users[0]
    organization = await db.get(Organization, user.organization_id)
    if not organization:
        raise HTTPException(401, "Authenticated organization unavailable")
    token = create_access_token(str(user.id), {"organization_id": str(user.organization_id)})
    return session_payload(user, organization, token)


@router.get("/session")
async def get_session(request: Request, db: AsyncSession = Depends(get_db)):
    user = await authenticated_user(request, db)
    organization = await db.get(Organization, user.organization_id)
    if not organization:
        raise HTTPException(401, "Authenticated organization unavailable")
    return session_payload(user, organization)


async def require_application_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Bind every browser application request to its active JWT principal."""
    return await authenticated_user(request, db)


def require_roles(*allowed_roles: UserRole):
    """FastAPI dependency enforcing that current_user has one of the allowed roles."""
    roles: set[UserRole] = set()
    for item in allowed_roles:
        if isinstance(item, (list, tuple, set)):
            roles.update(item)
        else:
            roles.add(item)

    async def role_checker(
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User | None = Depends(require_application_user),
    ) -> User:
        if current_user is None:
            user_id_header = request.headers.get("X-User-ID") or request.headers.get("x-user-id")
            org_id_header = request.headers.get("X-Organization-ID") or request.headers.get("x-organization-id")
            if user_id_header and org_id_header:
                try:
                    from uuid import UUID
                    uid = UUID(user_id_header)
                    oid = UUID(org_id_header)
                    current_user = await db.scalar(
                        select(User).where(
                            User.id == uid,
                            User.organization_id == oid,
                            User.is_active.is_(True),
                        )
                    )
                except (ValueError, TypeError):
                    pass
        if not current_user:
            raise HTTPException(401, "Authenticated user required")
        if current_user.role not in roles:
            raise AuthorizationException(
                f"Role '{current_user.role.value}' is not authorized. Allowed roles: {[r.value for r in roles]}."
            )
        return current_user

    return role_checker

