import uuid
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.organization import Organization


async def get_organization_name(session: AsyncSession, organization_id: uuid.UUID) -> str:
    stmt = select(Organization.legal_name).where(Organization.id == organization_id)
    result = await session.execute(stmt)
    name = result.scalar_one_or_none()
    return name or "Organisasi Kontraktor"
