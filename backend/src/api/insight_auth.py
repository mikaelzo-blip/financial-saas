"""Authenticated read access, with tenant scope derived from the active user."""
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db
from src.core.security import decode_access_token
from src.models.user import User


async def require_insight_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth = request.headers.get('Authorization', '')
    payload = decode_access_token(auth[7:]) if auth.startswith('Bearer ') else None
    try:
        user_id = UUID(payload['sub']) if payload and payload.get('exp') else None
    except (KeyError, ValueError, TypeError):
        user_id = None
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True))) if user_id else None
    if not user:
        raise HTTPException(401, 'Authenticated user required')
    if request.headers.get('X-Organization-ID') != str(user.organization_id):
        raise HTTPException(403, 'Organization mismatch')
    return user
