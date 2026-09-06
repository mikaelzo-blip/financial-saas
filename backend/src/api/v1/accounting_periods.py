import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.auth import require_application_user
from src.models.user import User
from src.models.enums import UserRole
from src.core.exceptions import AuthorizationException
from src.schemas.accounting_period import (
    AccountingPeriodCreate,
    AccountingPeriodUpdate,
    AccountingPeriodResponse
)
from src.services.accounting_period_service import AccountingPeriodService

router = APIRouter(prefix="/periods", tags=["Accounting Periods"])


@router.get("", response_model=List[AccountingPeriodResponse])
async def list_periods(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user)
):
    service = AccountingPeriodService(db)
    return await service.list_periods(current_user.organization_id)


@router.post("", response_model=AccountingPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create_period(
    payload: AccountingPeriodCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user)
):
    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise AuthorizationException("Only ADMIN or MANAGER can configure accounting periods.")
    service = AccountingPeriodService(db)
    return await service.create_period(current_user.organization_id, payload)


@router.patch("/{period_id}/status", response_model=AccountingPeriodResponse)
async def update_period_status(
    period_id: uuid.UUID,
    payload: AccountingPeriodUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_application_user)
):
    if current_user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise AuthorizationException("Only ADMIN or MANAGER can modify accounting period status.")
    service = AccountingPeriodService(db)
    return await service.update_period_status(
        current_user.organization_id, period_id, payload, actor_id=current_user.id
    )
