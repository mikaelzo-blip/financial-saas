"""Browser-user authentication and production tenant binding."""

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import create_access_token, decode_access_token, verify_password
from src.models.organization import Organization
from src.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


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
    return {
        "access_token": create_access_token(str(user.id), {"organization_id": str(user.organization_id)}),
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "organization_id": str(user.organization_id),
            "organization_name": organization.legal_name if organization else None,
        },
    }


async def require_application_user(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    """Bind production requests to an active JWT principal.

    Development keeps legacy header fixtures until their APIs are migrated;
    staging and production always fail closed.
    """
    if settings.ENVIRONMENT.lower() not in {"staging", "production"}:
        return None
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
    supplied_org = request.headers.get("X-Organization-ID")
    supplied_user = request.headers.get("X-User-ID")
    if supplied_org != str(user.organization_id):
        raise HTTPException(403, "Organization mismatch")
    if supplied_user != str(user.id):
        raise HTTPException(403, "User mismatch")
    return user
