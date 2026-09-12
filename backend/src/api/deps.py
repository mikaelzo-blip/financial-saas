import uuid
from typing import Optional
from fastapi import Header, HTTPException, status


async def get_current_org_id(
    x_organization_id: Optional[str] = Header(None, description="Organization Tenant UUID")
) -> uuid.UUID:
    """Extract the organization ID from the request header."""
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
