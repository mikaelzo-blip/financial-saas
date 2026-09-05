import uuid
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user


from src.schemas.money_movement import (
    MoneyMovementCreate,
    MoneyMovementResponse
)
from src.services.money_movement_service import MoneyMovementService

router = APIRouter()


@router.get(
    "",
    response_model=List[MoneyMovementResponse],
    summary="List Money Movements"
)
async def list_money_movements(
    payment_account_id: Optional[uuid.UUID] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = MoneyMovementService(db)
    return await service.list_money_movements(org_id, payment_account_id=payment_account_id)


@router.post(
    "",
    response_model=MoneyMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Money Movement with Optional Settlement & Allocations"
)
async def create_money_movement(
    data: MoneyMovementCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user = Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = MoneyMovementService(db)
    return await service.create_money_movement(org_id, data)


@router.get(
    "/unallocated-summary",
    summary="Get Unallocated Cash Summary"
)
async def get_unallocated_summary(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = MoneyMovementService(db)
    unallocated = await service.get_unallocated_cash_summary(org_id)
    return {"unallocated_cash": unallocated}
