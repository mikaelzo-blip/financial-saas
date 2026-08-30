"""Authentication specific to the WhatsApp SaaS boundary."""
import hmac
import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import decode_access_token
from src.models.user import User
from src.models.enums import UserRole


def matches(request: Request, secret: str | None) -> bool:
    authorization = request.headers.get("Authorization", "")
    return bool(secret and hmac.compare_digest(authorization.encode(), ("Bearer " + secret).encode()))


async def require_adapter(request: Request):
    token = settings.WHATSAPP_ADAPTER_TOKEN
    if not token or not matches(request, token.get_secret_value()):
        raise HTTPException(401, "Invalid adapter credential")


def whatsapp_machine_organization(request: Request) -> uuid.UUID | None:
    organizations = [uuid.UUID(org) for org, secret in settings.WHATSAPP_TENANT_TOKENS.items() if matches(request, secret.get_secret_value())]
    if len(organizations) > 1:
        raise HTTPException(503, "Ambiguous machine credential configuration")
    return organizations[0] if organizations else None


async def require_whatsapp_machine(request: Request) -> uuid.UUID:
    org = whatsapp_machine_organization(request)
    if org is None:
        raise HTTPException(401, "Invalid tenant machine credential")
    return org


async def require_whatsapp_admin(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    authorization = request.headers.get("Authorization", "")
    payload = decode_access_token(authorization.removeprefix("Bearer ")) if authorization.startswith("Bearer ") else None
    try:
        user_id = uuid.UUID(payload["sub"]) if payload and payload.get("exp") else None
    except (KeyError, ValueError, TypeError):
        user_id = None
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True))) if user_id else None
    if not user:
        raise HTTPException(401, "Authenticated user required")
    if user.role != UserRole.ADMIN or request.headers.get("X-Organization-ID") != str(user.organization_id):
        raise HTTPException(403, "Organization administrator required")
    return user
