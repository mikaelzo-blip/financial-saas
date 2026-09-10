import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user, require_roles
from src.models.enums import TransactionType, WorkflowStatus, UserRole
from src.models.user import User
from src.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    OpeningBalanceBatchRequest
)
from src.services.transaction_service import TransactionService
from src.services.opening_balance_service import OpeningBalanceService
from src.services.transaction_retry import run_in_clean_transaction

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
    async def create(session: AsyncSession):
        return await TransactionService(session).create_transaction(org_id, data)

    return await run_in_clean_transaction(db, create)


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
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    from src.services.processing_policy_service import ProcessingPolicyService

    async def post(session: AsyncSession) -> uuid.UUID:
        transaction, _ = await ProcessingPolicyService(session).authorize_and_post(
            org_id,
            transaction_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            bypass_role_check=False,
        )
        return transaction.id

    posted_transaction_id = await run_in_clean_transaction(db, post)
    return await TransactionService(db).get_transaction(org_id, posted_transaction_id)


@router.post(
    "/{transaction_id}/approve",
    response_model=TransactionResponse,
    summary="Approve and Post Transaction"
)
async def approve_transaction(
    transaction_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    from src.services.processing_policy_service import ProcessingPolicyService

    async def approve(session: AsyncSession) -> uuid.UUID:
        transaction, _ = await ProcessingPolicyService(session).authorize_and_post(
            org_id,
            transaction_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            bypass_role_check=False,
        )
        return transaction.id

    approved_transaction_id = await run_in_clean_transaction(db, approve)
    return await TransactionService(db).get_transaction(org_id, approved_transaction_id)


@router.post(
    "/opening-balances",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Establish Opening Balances"
)
async def establish_opening_balances(
    payload: OpeningBalanceBatchRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    raw_entries = [e.model_dump() for e in payload.entries]

    async def establish(session: AsyncSession) -> uuid.UUID:
        posted_trx = await OpeningBalanceService(session).post_opening_balances(
            organization_id=org_id,
            as_of_date=payload.as_of_date,
            balance_entries=raw_entries,
            notes=payload.notes or "Saldo Awal Pembukuan",
            actor_id=current_user.id,
            actor_role=current_user.role,
        )
        return posted_trx.id

    posted_transaction_id = await run_in_clean_transaction(db, establish)
    return await TransactionService(db).get_transaction(org_id, posted_transaction_id)


