from fastapi import APIRouter, Depends

from src.api.auth import require_application_user, router as auth_router
from src.api.v1.documents import router as documents_router
from src.api.v1.hermes import router as hermes_router
from src.api.v1.insights import router as insights_router
from src.api.v1.project_costing import router as project_costing_router
from src.api.v1.projects import router as projects_router
from src.api.v1.reference_data import router as reference_data_router
from src.api.v1.reports import router as reports_router
from src.api.v1.reversals import router as reversals_router
from src.api.v1.review import router as review_router
from src.api.v1.transactions import router as transactions_router
from src.api.v1.whatsapp import router as whatsapp_router
from src.api.v1.whatsapp_state import router as whatsapp_state_router
from src.api.v1.counterparties import router as counterparties_router
from src.api.v1.receivables import router as receivables_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(hermes_router)
api_router.include_router(whatsapp_router)
api_router.include_router(whatsapp_state_router)

application_router = APIRouter(dependencies=[Depends(require_application_user)])
application_router.include_router(counterparties_router)
application_router.include_router(receivables_router)
application_router.include_router(projects_router)
application_router.include_router(reference_data_router)
application_router.include_router(documents_router)
application_router.include_router(transactions_router)
application_router.include_router(reversals_router)
application_router.include_router(review_router)
application_router.include_router(project_costing_router)
application_router.include_router(reports_router)
application_router.include_router(insights_router)
api_router.include_router(application_router)

__all__ = ["api_router"]
