import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.models.enums import AccountType, CostCategory, ExpenseCategory
from src.schemas.coa import (
    ChartOfAccountCreate,
    ChartOfAccountResponse,
    PaymentAccountCreate,
    PaymentAccountResponse,
    CategoryMetadataResponse,
)
from src.services.coa_service import COAService, PaymentAccountService

router = APIRouter(tags=["Reference Data"])


@router.get(
    "/coa",
    response_model=List[ChartOfAccountResponse],
    summary="List Chart of Accounts"
)
async def list_coa(
    account_type: Optional[AccountType] = Query(None, description="Filter by account type"),
    active_only: bool = Query(True, description="Only active accounts"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = COAService(db)
    return await service.list_accounts(org_id, account_type=account_type, active_only=active_only)


@router.post(
    "/coa",
    response_model=ChartOfAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chart of Account"
)
async def create_coa(
    data: ChartOfAccountCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = COAService(db)
    return await service.create_account(org_id, data)


@router.get(
    "/payment-accounts",
    response_model=List[PaymentAccountResponse],
    summary="List Payment Accounts"
)
async def list_payment_accounts(
    active_only: bool = Query(True),
    with_balance: bool = Query(False),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = PaymentAccountService(db)
    if with_balance:
        return await service.list_payment_accounts_with_balances(org_id)
    return await service.list_payment_accounts(org_id, active_only=active_only)



@router.post(
    "/payment-accounts",
    response_model=PaymentAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Payment Account"
)
async def create_payment_account(
    data: PaymentAccountCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = PaymentAccountService(db)
    return await service.create_payment_account(org_id, data)


@router.get(
    "/categories",
    response_model=CategoryMetadataResponse,
    summary="Get Cost and Expense Categories"
)
async def get_categories():
    return CategoryMetadataResponse(
        cost_categories=[c.value for c in CostCategory],
        expense_categories=[e.value for e in ExpenseCategory]
    )
