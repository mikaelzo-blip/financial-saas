import uuid
from typing import Optional
from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.core.database import get_db


async def get_current_org_id(
    x_organization_id: Optional[str] = Header(None, description="Organization Tenant UUID")
) -> uuid.UUID:
    """
    Extracts the organization ID from the request header.
    """
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Organization-ID' header."
        )
    try:
        return uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid UUID format for 'X-Organization-ID' header."
        )


async def get_current_user_id(
    x_user_id: Optional[str] = Header(None, description="Current User UUID")
) -> uuid.UUID:
    """Extracts user ID from request header, falling back to a default system user UUID if omitted."""
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid UUID format for 'X-User-ID' header."
            )
    return uuid.UUID("00000000-0000-0000-0000-000000000001")
