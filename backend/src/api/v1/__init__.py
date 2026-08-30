from fastapi import APIRouter
from src.api.v1.projects import router as projects_router
from src.api.v1.reference_data import router as reference_data_router
from src.api.v1.documents import router as documents_router
from src.api.v1.transactions import router as transactions_router
from src.api.v1.reversals import router as reversals_router
from src.api.v1.review import router as review_router
from src.api.v1.project_costing import router as project_costing_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(reference_data_router)
api_router.include_router(documents_router)
api_router.include_router(transactions_router)
api_router.include_router(reversals_router)
api_router.include_router(review_router)
api_router.include_router(project_costing_router)

__all__ = ["api_router"]
