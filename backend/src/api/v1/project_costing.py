import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.services.project_cost_service import ProjectCostService

router = APIRouter(prefix="/projects", tags=["Project Costing & Profitability"])


@router.get(
    "/{project_id}/costs",
    summary="Get Project Actual Cost Breakdown and Budget Variance"
)
async def get_project_costs(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    service = ProjectCostService(db)
    return await service.get_project_cost_breakdown(org_id, project_id)


@router.get(
    "/{project_id}/profitability",
    summary="Get Project Revenue, Cost, Profit, and Margin %"
)
async def get_project_profitability(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    service = ProjectCostService(db)
    return await service.get_project_profitability(org_id, project_id)


@router.get(
    "/{project_id}/financial-summary",
    summary="Get Complete Project Financial Summary (Contract, P&L, Cash Flow)"
)
async def get_project_financial_summary(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    service = ProjectCostService(db)
    return await service.get_project_financial_summary(org_id, project_id)
