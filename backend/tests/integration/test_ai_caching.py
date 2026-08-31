from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest

from src.models.organization import Organization
from src.models.ai_insight import AIInsightLog
from src.schemas.ai_insight import AIInsightResponse, ProviderMetadata
from src.services.ai.fallback_engine import DeterministicFallbackEngine
from src.services.insight_store import InsightStore
from tests.unit.test_ai_fallback_engine import grounded


@pytest.mark.asyncio
async def test_persistent_cache_isolation_expiry_and_content_invalidation(db_session):
    org = Organization(slug='ai-cache', legal_name='Cache test')
    db_session.add(org)
    await db_session.flush()
    payload = grounded(org.id)
    response = AIInsightResponse(**DeterministicFallbackEngine.generate(payload).model_dump(), organization_id=org.id, period_label='Aug', as_of_date=payload.end_date, data_as_of=payload.end_date, confidence_score='HIGH', confidence_category='HIGH', source_references=payload.source_references, metric_sources=payload.metric_sources, unavailable_metrics=['cash_balance'], provider_metadata=ProviderMetadata(provider='MOCK'))
    store = InsightStore(db_session, org.id)
    assert await store.get(payload) is None
    await store.put(payload, response)
    assert (await store.get(payload)).provider_metadata.cached
    with pytest.raises(PermissionError):
        await InsightStore(db_session, uuid4()).get(payload)
    changed = payload.model_copy(deep=True)
    changed.factual_metrics['net_profit'] = Decimal('1.00')
    assert await store.get(changed) is None
    from sqlalchemy import select
    log = await db_session.scalar(select(AIInsightLog))
    log.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()
    assert await store.get(payload) is None
