import asyncio
from decimal import Decimal

import pytest
from src.models.user import User
from src.models.enums import UserRole
from src.core.security import create_access_token
from tests.reporting_support import seed_cash_profit_ledger


async def insight_identity(db, slug='insight-a', revenue=Decimal('1000000000'), cost=Decimal('850000000')):
    org = await seed_cash_profit_ledger(db, slug, revenue, cost)
    user = User(organization_id=org.id, email=slug+'@example.test', full_name='Manager', password_hash='not-used', role=UserRole.MANAGER)
    db.add(user)
    await db.commit()
    return org, user, {'Authorization': 'Bearer '+create_access_token(str(user.id)), 'X-Organization-ID': str(org.id)}


URL = '/api/v1/insights/executive-summary?start_date=2026-08-01&end_date=2026-08-31'


@pytest.mark.asyncio
async def test_executive_api_exact_dtos_and_cached_response(client, db_session):
    org, user, headers = await insight_identity(db_session)
    response = await client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body['factual_metrics']['revenue']) == Decimal('1000000000')
    assert Decimal(body['factual_metrics']['net_profit']) == Decimal('150000000')
    assert body['provider_metadata']['provider'] == 'MOCK'
    assert body['confidence_score'] == 'HIGH'
    assert body['organization_id'] == str(org.id)
    assert 'ProfitLossReportResponse' in body['source_references']
    assert (await client.get(URL, headers=headers)).json()['provider_metadata']['cached']


@pytest.mark.asyncio
async def test_exec_auth_tenant_dates_and_no_financial_writes(client, db_session):
    org, user, headers = await insight_identity(db_session)
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(URL, headers={'X-Organization-ID':str(org.id)})).status_code == 401
    from uuid import uuid4
    assert (await client.get(URL, headers={**headers, 'X-Organization-ID':str(uuid4())})).status_code == 403
    assert (await client.get('/api/v1/insights/executive-summary?start_date=2026-09-01&end_date=2026-08-31', headers=headers)).status_code == 422
    from sqlalchemy import select, func
    from src.models.journal import JournalEntry
    before = await db_session.scalar(select(func.count()).select_from(JournalEntry))
    await client.get(URL, headers=headers)
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == before


@pytest.mark.asyncio
async def test_provider_timeout_returns_fast_fallback(client, db_session, monkeypatch):
    from src.core.config import settings
    from src.services.ai.mock_provider import MockAIInsightProvider

    provider_started = asyncio.Event()
    provider_cancelled = asyncio.Event()

    async def slow_provider(*args, **kwargs):
        provider_started.set()
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            provider_cancelled.set()
            raise

    monkeypatch.setattr(MockAIInsightProvider, 'generate', slow_provider)
    monkeypatch.setattr(settings, 'AI_INSIGHT_TIMEOUT_SECONDS', 0.05)
    _, _, headers = await insight_identity(db_session)

    response = await asyncio.wait_for(
        client.get(URL, headers=headers),
        timeout=2.0,
    )
    assert provider_started.is_set()
    assert provider_cancelled.is_set()
    assert response.status_code == 200
    body = response.json()
    assert body['provider_metadata']['provider'] == 'DETERMINISTIC_FALLBACK'
    assert body['provider_metadata']['fallback_reason'] == 'PROVIDER_UNAVAILABLE_OR_INVALID'
