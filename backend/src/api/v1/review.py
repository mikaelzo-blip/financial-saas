import uuid
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id, get_current_user_id
from src.models.enums import ReviewFlag
from src.schemas.transaction import TransactionResponse
from src.services.review_service import ReviewQueueService

router = APIRouter(tags=["Review Queue"])


class AddReviewFlagRequest(BaseModel):
    flag: ReviewFlag
    message: str = Field(min_length=3)
    severity: str = "WARNING"


class ResolveReviewFlagRequest(BaseModel):
    resolution_notes: str = Field(min_length=3)


class ReviewFlagResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    flag: ReviewFlag
    severity: str
    message: str
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/review-queue",
    response_model=List[TransactionResponse],
    summary="List Transactions Requiring Review"
)
async def list_review_queue(
    flag_type: Optional[ReviewFlag] = Query(None, description="Filter by specific review flag"),
    unresolved_only: bool = Query(True, description="Only show transactions with unresolved flags"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = ReviewQueueService(db)
    return await service.list_review_items(org_id, flag_type=flag_type, unresolved_only=unresolved_only)


@router.post(
    "/transactions/{transaction_id}/review-flags",
    response_model=ReviewFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Review Flag to Transaction"
)
async def add_review_flag(
    transaction_id: uuid.UUID,
    data: AddReviewFlagRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = ReviewQueueService(db)
    flag = await service.add_review_flag(
        organization_id=org_id,
        transaction_id=transaction_id,
        flag=data.flag,
        message=data.message,
        severity=data.severity
    )
    await db.commit()
    return flag


@router.post(
    "/transactions/{transaction_id}/review-flags/{flag_id}/resolve",
    response_model=ReviewFlagResponse,
    summary="Resolve a Specific Review Flag"
)
async def resolve_review_flag(
    transaction_id: uuid.UUID,
    flag_id: uuid.UUID,
    data: ResolveReviewFlagRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    service = ReviewQueueService(db)
    resolved = await service.resolve_review_flag(
        organization_id=org_id,
        transaction_id=transaction_id,
        flag_id=flag_id,
        resolved_by=user_id,
        resolution_notes=data.resolution_notes
    )
    await db.commit()
    return resolved
