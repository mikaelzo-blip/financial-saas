from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.insight_auth import require_insight_user
from src.core.database import get_db
from src.models.user import User
from src.schemas.ai_insight import AIInsightResponse
from src.services.ai.insight_service import AIInsightService
from src.services.insight_store import InsightStore
from src.services.insight_reporting import executive_grounding

router = APIRouter(prefix='/insights', tags=['Management Insights'])


def resolve_dates(start, end):
    end = end or date.today()
    start = start or end.replace(day=1)
    if start > end or (end-start).days > 3660:
        raise HTTPException(422, 'Invalid reporting period')
    return start, end


@router.get('/executive-summary', response_model=AIInsightResponse)
async def executive_summary(start_date: date | None = None, end_date: date | None = None, refresh: bool = False,
                            user: User = Depends(require_insight_user), db: AsyncSession = Depends(get_db)):
    start, end = resolve_dates(start_date, end_date)
    payload = await executive_grounding(db, user.organization_id, start, end)
    return await AIInsightService(InsightStore(db, user.organization_id)).get_executive_summary(payload, refresh)
