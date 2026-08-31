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
from src.services.ai.intent_classifier import IntentClassifier
from src.services.ai.sanitizer import sanitize_text
from src.services.ai.project_service import project_grounding
from src.services.ai.anomaly_detector import AnomalyDetector
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.project_reporting_service import ProjectReportingService
from src.services.reporting.budget_service import BudgetVsActualService
from src.services.reporting.integrity_service import IntegrityService
from src.schemas.ai_insight import FinancialQAQueryRequest, FinancialQAQueryResponse
from src.models.ai_insight import AIConversationSession, AIConversationMessage
import uuid

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


@router.get('/projects/{project_id}', response_model=AIInsightResponse)
async def project_health(project_id: uuid.UUID, user: User = Depends(require_insight_user), db: AsyncSession = Depends(get_db)):
    try: payload = await project_grounding(db, user.organization_id, project_id, date.today())
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    result = await AIInsightService(InsightStore(db, user.organization_id)).generate(payload)
    result.anomalies_detected = AnomalyDetector.detect(result.factual_metrics)
    return result


@router.post('/query', response_model=FinancialQAQueryResponse)
async def financial_query(request: FinancialQAQueryRequest, user: User = Depends(require_insight_user), db: AsyncSession = Depends(get_db)):
    intent = IntentClassifier.classify(request.query_text)
    session = None
    if request.session_id:
        session = await db.scalar(__import__('sqlalchemy').select(AIConversationSession).where(AIConversationSession.id == request.session_id, AIConversationSession.organization_id == user.organization_id, AIConversationSession.user_id == user.id))
        if not session: raise HTTPException(404, 'Session not found')
    if not session:
        session = AIConversationSession(id=uuid.uuid4(), organization_id=user.organization_id, user_id=user.id, session_title='Management Q&A')
        db.add(session); await db.flush()
    safe_question = sanitize_text(request.query_text)
    db.add(AIConversationMessage(session_id=session.id, sender='USER', message_text=safe_question, context_intent=intent))
    if intent == 'OUT_OF_SCOPE':
        answer = 'Saya hanya dapat menganalisis data keuangan internal perusahaan Anda.'
        refs = []
    else:
        end = request.end_date or date.today(); start = request.start_date or end.replace(day=1)
        if intent == 'AR_AGING': dto = await ARAgingService.get_ar_aging(db, user.organization_id, end); payload = __import__('src.services.ai.grounding_service', fromlist=['GroundingService']).GroundingService.build(user.organization_id, start, end, {'ar':dto}, insight_type='MANAGEMENT_QA')
        elif intent == 'AP_AGING': dto = await APAgingService.get_ap_aging(db, user.organization_id, end); payload = __import__('src.services.ai.grounding_service', fromlist=['GroundingService']).GroundingService.build(user.organization_id, start, end, {'ap':dto}, insight_type='MANAGEMENT_QA')
        elif intent == 'PROJECT_HEALTH' and request.project_id: payload = await project_grounding(db, user.organization_id, request.project_id, end)
        else: payload = await executive_grounding(db, user.organization_id, start, end)
        insight = await AIInsightService(InsightStore(db, user.organization_id)).generate(payload, qa=True)
        answer, refs = insight.analytical_narrative, payload.source_references
    db.add(AIConversationMessage(session_id=session.id, sender='ASSISTANT', message_text=answer, context_intent=intent, source_references=refs))
    await db.flush()
    return FinancialQAQueryResponse(session_id=session.id, answer_text=answer, classified_intent=intent, source_references=refs, confidence_score='HIGH' if refs else 'LOW')


@router.get('/anomalies')
async def anomalies(user: User = Depends(require_insight_user), db: AsyncSession = Depends(get_db)):
    end = date.today(); payload = await executive_grounding(db, user.organization_id, end.replace(day=1), end)
    return {'anomalies': [item.model_dump() for item in AnomalyDetector.detect(payload.factual_metrics)]}
