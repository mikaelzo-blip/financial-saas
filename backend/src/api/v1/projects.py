import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.models.enums import ProjectStatus
from src.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectStatusUpdate,
    ProjectResponse,
    ProjectBudgetCreate,
    ProjectBudgetResponse,
)
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project Master Record"
)
async def create_project(
    data: ProjectCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new project master record for the tenant organization."""
    service = ProjectService(db)
    project = await service.create_project(org_id, data)
    return project


@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List Projects"
)
async def list_projects(
    status: Optional[ProjectStatus] = Query(None, description="Filter projects by lifecycle status"),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Lists all projects for the tenant organization."""
    service = ProjectService(db)
    projects = await service.list_projects(org_id, status=status)
    return projects


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get Project Details"
)
async def get_project(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Fetches details for a specific project."""
    service = ProjectService(db)
    project = await service.get_project(org_id, project_id)
    return project


@router.patch(
    "/{project_id}/status",
    response_model=ProjectResponse,
    summary="Update Project Status"
)
async def update_project_status(
    project_id: uuid.UUID,
    data: ProjectStatusUpdate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Transitions a project lifecycle status."""
    service = ProjectService(db)
    project = await service.update_project_status(org_id, project_id, data)
    return project


@router.get(
    "/{project_id}/budgets",
    response_model=List[ProjectBudgetResponse],
    summary="Get Project Budget Lines"
)
async def get_project_budgets(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Lists all budget category allocations for a project."""
    service = ProjectService(db)
    # Ensure project belongs to org
    await service.get_project(org_id, project_id)
    budgets = await service.get_project_budgets(project_id)
    return budgets


@router.post(
    "/{project_id}/budgets",
    response_model=ProjectBudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or Update Project Budget"
)
async def add_or_update_project_budget(
    project_id: uuid.UUID,
    data: ProjectBudgetCreate,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    """Sets a budget allocation for a specific cost category."""
    service = ProjectService(db)
    await service.get_project(org_id, project_id)
    budget = await service.add_or_update_project_budget(project_id, data)
    return budget
