import uuid
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_roles
from src.models.enums import AssetStatus, UserRole
from src.models.user import User
from src.schemas.fixed_asset import (
    FixedAssetCreate,
    FixedAssetUpdate,
    FixedAssetResponse,
    DepreciationRunRequest,
    DepreciationRunResult,
    BatchDepreciationResponse,
    CapitalizationGuidanceResponse
)
from src.services.fixed_asset_service import FixedAssetService
from src.services.transaction_retry import run_in_clean_transaction


router = APIRouter(prefix="/fixed-assets", tags=["Fixed Assets / Aset Tetap"])


@router.get("", response_model=List[FixedAssetResponse])
async def list_assets(
    status: Optional[AssetStatus] = Query(None, description="Filter status aset"),
    category: Optional[str] = Query(None, description="Filter kategori aset"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = FixedAssetService(db)
    return await service.list_assets(
        organization_id=org_id,
        status=status,
        category=category
    )


@router.post("", response_model=FixedAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: FixedAssetCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    service = FixedAssetService(db)
    return await service.create_asset(
        organization_id=org_id,
        data=payload,
        actor_id=current_user.id
    )


@router.get("/guidance/capitalization", response_model=CapitalizationGuidanceResponse)
async def get_capitalization_guidance(
    amount: Decimal = Query(..., gt=0, description="Nilai transaksi perolehan"),
    benefit_months: int = Query(12, gt=0, description="Perkiraan masa manfaat dalam bulan"),
    org_id: uuid.UUID = Depends(get_current_org_id)
):
    return FixedAssetService.get_capitalization_guidance(amount, benefit_months)


@router.get("/{asset_id}", response_model=FixedAssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = FixedAssetService(db)
    return await service.get_asset(
        organization_id=org_id,
        asset_id=asset_id
    )


@router.put("/{asset_id}", response_model=FixedAssetResponse)
@router.patch("/{asset_id}", response_model=FixedAssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    payload: FixedAssetUpdate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    service = FixedAssetService(db)
    return await service.update_asset(
        organization_id=org_id,
        asset_id=asset_id,
        data=payload,
        actor_id=current_user.id
    )


@router.post("/{asset_id}/depreciate", response_model=DepreciationRunResult)
async def depreciate_single_asset(
    asset_id: uuid.UUID,
    payload: DepreciationRunRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    actor_id = current_user.id
    actor_role = current_user.role

    async def depreciate(session: AsyncSession):
        return await FixedAssetService(session).depreciate_asset(
            organization_id=org_id,
            asset_id=asset_id,
            period_date=payload.period_date,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    return await run_in_clean_transaction(db, depreciate)


@router.post("/depreciate-batch", response_model=BatchDepreciationResponse)
async def depreciate_batch(
    payload: DepreciationRunRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    actor_id = current_user.id
    actor_role = current_user.role

    async def depreciate(session: AsyncSession):
        return await FixedAssetService(session).depreciate_batch(
            organization_id=org_id,
            period_date=payload.period_date,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    return await run_in_clean_transaction(db, depreciate)


@router.post("/{asset_id}/dispose", response_model=FixedAssetResponse)
async def dispose_asset(
    asset_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    service = FixedAssetService(db)
    from datetime import date
    return await service.dispose_asset(
        organization_id=org_id,
        asset_id=asset_id,
        disposal_date=date.today(),
        actor_id=current_user.id
    )
