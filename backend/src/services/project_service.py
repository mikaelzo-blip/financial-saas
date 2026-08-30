import uuid
from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.project import Project, ProjectBudget
from src.models.counterparty import Counterparty
from src.models.enums import ProjectStatus, CostCategory, BillingStatus, CollectionStatus
from src.schemas.project import ProjectCreate, ProjectUpdate, ProjectStatusUpdate, ProjectBudgetCreate
from src.core.exceptions import EntityNotFoundException, InvariantViolationException

# Valid lifecycle state transitions map
VALID_TRANSITIONS = {
    ProjectStatus.PLANNED: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.ACTIVE: {ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED, ProjectStatus.CANCELLED},
    ProjectStatus.ON_HOLD: {ProjectStatus.ACTIVE, ProjectStatus.CANCELLED},
    ProjectStatus.COMPLETED: {ProjectStatus.CLOSED},
    ProjectStatus.CLOSED: set(),  # Terminal
    ProjectStatus.CANCELLED: set(),  # Terminal
}


def validate_project_status_transition(current_status: ProjectStatus, new_status: ProjectStatus) -> bool:
    """
    Validates if transitioning from current_status to new_status is permitted.
    Raises InvariantViolationException if transition is forbidden.
    """
    if current_status == new_status:
        return True

    if current_status in (ProjectStatus.CLOSED, ProjectStatus.CANCELLED):
        raise InvariantViolationException(
            f"Cannot change status from terminal state {current_status.value}.",
            details={"current_status": current_status.value, "new_status": new_status.value}
        )

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        allowed_str = ", ".join(s.value for s in allowed) if allowed else "none (terminal)"
        raise InvariantViolationException(
            f"Cannot transition project from {current_status.value} to {new_status.value}. Allowed transitions: [{allowed_str}].",
            details={"current_status": current_status.value, "new_status": new_status.value, "allowed": list(s.value for s in allowed)}
        )

    return True


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_project_code(self, organization_id: uuid.UUID, project_date: Optional[date] = None) -> str:
        """
        Generates the next sequential unique project code in format PRJ-YYYY-NNN (e.g. PRJ-2026-001).
        """
        target_year = (project_date or date.today()).year
        prefix = f"PRJ-{target_year}-"

        stmt = select(func.count()).select_from(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.project_code.like(f"{prefix}%")
            )
        )
        count = await self.session.scalar(stmt) or 0
        next_seq = count + 1
        return f"{prefix}{next_seq:03d}"

    async def create_project(self, organization_id: uuid.UUID, data: ProjectCreate) -> Project:
        """
        Creates a new project master record.
        Validates customer counterparty, generates project code, and computes revised contract value.
        """
        # Validate customer exists
        cust_stmt = select(Counterparty).where(
            and_(
                Counterparty.id == data.customer_id,
                Counterparty.organization_id == organization_id
            )
        )
        customer = await self.session.scalar(cust_stmt)
        if not customer:
            raise EntityNotFoundException("Customer Counterparty", data.customer_id)

        # Generate unique human-readable code
        project_code = await self.generate_project_code(organization_id, data.start_date)

        # Revised contract value initially equals original contract value
        revised_val = data.original_contract_value

        project = Project(
            organization_id=organization_id,
            project_code=project_code,
            project_name=data.project_name,
            customer_id=data.customer_id,
            po_spk_no=data.po_spk_no,
            po_spk_date=data.po_spk_date,
            original_contract_value=data.original_contract_value,
            variation_order_value=Decimal("0.00"),
            revised_contract_value=revised_val,
            start_date=data.start_date,
            target_end_date=data.target_end_date,
            pic_user_id=data.pic_user_id,
            project_status=ProjectStatus.PLANNED
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def get_project(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """
        Fetches project by ID within organization boundary.
        """
        stmt = select(Project).where(
            and_(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        )
        project = await self.session.scalar(stmt)
        if not project:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def list_projects(
        self,
        organization_id: uuid.UUID,
        status: Optional[ProjectStatus] = None
    ) -> List[Project]:
        """
        Lists all projects within organization, optionally filtered by status.
        """
        filters = [Project.organization_id == organization_id]
        if status:
            filters.append(Project.project_status == status)

        stmt = select(Project).where(and_(*filters)).order_by(Project.project_code.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_project(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        data: ProjectUpdate
    ) -> Project:
        """
        Updates project metadata.
        """
        project = await self.get_project(organization_id, project_id)

        if data.project_name is not None:
            project.project_name = data.project_name
        if data.po_spk_no is not None:
            project.po_spk_no = data.po_spk_no
        if data.po_spk_date is not None:
            project.po_spk_date = data.po_spk_date
        if data.target_end_date is not None:
            project.target_end_date = data.target_end_date
        if data.pic_user_id is not None:
            project.pic_user_id = data.pic_user_id

        await self.session.flush()
        return project

    async def update_project_status(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        update: ProjectStatusUpdate
    ) -> Project:
        """
        Transitions project status with lifecycle validation.
        """
        project = await self.get_project(organization_id, project_id)
        validate_project_status_transition(project.project_status, update.status)

        project.project_status = update.status
        if update.actual_end_date:
            project.actual_end_date = update.actual_end_date
        elif update.status in (ProjectStatus.COMPLETED, ProjectStatus.CLOSED) and not project.actual_end_date:
            project.actual_end_date = date.today()

        await self.session.flush()
        return project

    async def update_variation_order(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        variation_order_value: Decimal
    ) -> Project:
        """
        Updates variation order and enforces revised contract value calculation.
        """
        project = await self.get_project(organization_id, project_id)
        project.variation_order_value = variation_order_value
        project.revised_contract_value = project.calculate_revised_contract_value()
        await self.session.flush()
        return project

    async def get_project_budgets(self, project_id: uuid.UUID) -> List[ProjectBudget]:
        """
        Fetches all budget line items for a project.
        """
        stmt = select(ProjectBudget).where(
            ProjectBudget.project_id == project_id
        ).order_by(ProjectBudget.cost_category.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_or_update_project_budget(
        self,
        project_id: uuid.UUID,
        data: ProjectBudgetCreate
    ) -> ProjectBudget:
        """
        Adds or updates a budget line item for a cost category.
        """
        stmt = select(ProjectBudget).where(
            and_(
                ProjectBudget.project_id == project_id,
                ProjectBudget.cost_category == data.cost_category
            )
        )
        existing = await self.session.scalar(stmt)
        if existing:
            existing.budget_amount = data.budget_amount
            existing.notes = data.notes
            await self.session.flush()
            return existing

        budget = ProjectBudget(
            project_id=project_id,
            cost_category=data.cost_category,
            budget_amount=data.budget_amount,
            notes=data.notes
        )
        self.session.add(budget)
        await self.session.flush()
        return budget
