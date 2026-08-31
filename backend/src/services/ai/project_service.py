from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.reporting.budget_service import BudgetVsActualService
from src.services.ai.grounding_service import GroundingService

async def project_grounding(db, org, project_id, as_of):
    project = await ProjectReportingService.get_project_profitability(db, org, project_id)
    cash = await ProjectReportingService.get_project_cash_position(db, org, project_id)
    budget = await BudgetVsActualService.get_budget_vs_actual(db, org, project_id)
    payload = GroundingService.build(org, project.status and project.__class__ and project.__dict__.get('start_date') or as_of, as_of, {'project': project, 'project_cash': cash, 'budget': budget}, insight_type='PROJECT_HEALTH', project_id=project_id)
    return payload
