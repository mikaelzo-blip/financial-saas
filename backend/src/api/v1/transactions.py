import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.models.enums import TransactionType, WorkflowStatus
from src.schemas.transaction import TransactionCreate, TransactionResponse
from src.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Capture Financial Transaction"
)
async def create_transaction(
    data: TransactionCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = TransactionService(db)
    return await service.create_transaction(org_id, data)


@router.get(
    "",
    response_model=List[TransactionResponse],
    summary="List Transactions"
)
async def list_transactions(
    status: Optional[WorkflowStatus] = Query(None, description="Filter by workflow status"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = TransactionService(db)
    return await service.list_transactions(
        org_id,
        workflow_status=status,
        transaction_type=transaction_type
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get Transaction Details"
)
async def get_transaction(
    transaction_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = TransactionService(db)
    return await service.get_transaction(org_id, transaction_id)


@router.post(
    "/{transaction_id}/post",
    response_model=TransactionResponse,
    summary="Post Candidate Transaction into Double-Entry Journal"
)
async def post_transaction(
    transaction_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    from src.services.processing_policy_service import ProcessingPolicyService
    policy_svc = ProcessingPolicyService(db)
    await policy_svc.authorize_and_post(org_id, transaction_id, bypass_role_check=True)
    await db.commit()
    service = TransactionService(db)
    return await service.get_transaction(org_id, transaction_id)


@router.post(
    "/{transaction_id}/approve",
    response_model=TransactionResponse,
    summary="Approve and Post Transaction"
)
async def approve_transaction(
    transaction_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    from src.services.processing_policy_service import ProcessingPolicyService
    policy_svc = ProcessingPolicyService(db)
    await policy_svc.authorize_and_post(org_id, transaction_id, bypass_role_check=True)
    await db.commit()
    service = TransactionService(db)
    return await service.get_transaction(org_id, transaction_id)

