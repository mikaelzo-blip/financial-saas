from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.schemas.reporting import ReportSection, ProfitLossReportResponse
from src.services.ai.grounding_service import GroundingService
from src.services.ai.fallback_engine import DeterministicFallbackEngine
from src.services.ai.mock_provider import MockAIInsightProvider
from src.services.ai.provider import validate_output


def grounded(org=None):
    section = ReportSection(section_code='R', section_name='Revenue', subtotal=Decimal('1000000000.01'))
    pl = ProfitLossReportResponse(organization_name='Test', period_label='Agustus 2026', start_date=date(2026,8,1), end_date=date(2026,8,31), generated_at='now', revenue_section=section, cogs_section=section, gross_profit=Decimal('150000000.01'), gross_margin_percentage=Decimal('15.00'), operating_expenses_section=section, operating_profit=Decimal('150000000.01'), other_income_expense_section=section, earnings_before_tax=Decimal('150000000.01'), tax_expense=Decimal('0'), net_profit=Decimal('150000000.01'))
    return GroundingService.build(org or uuid4(), date(2026,8,1), date(2026,8,31), {'pl': pl})


def test_exact_grounding_and_missing_not_zero():
    payload = grounded()
    assert payload.factual_metrics['revenue'] == Decimal('1000000000.01')
    assert payload.factual_metrics['net_profit'] == Decimal('150000000.01')
    assert payload.factual_metrics['cash_balance'] is None
    assert payload.metric_sources['revenue'] == 'ProfitLossReportResponse.revenue_section.subtotal'
    result = DeterministicFallbackEngine.generate(payload)
    assert 'Data tidak tersedia' in result.analytical_narrative
    assert '150000000.01' in result.analytical_narrative


def test_cache_address_is_stable_and_tenant_scoped():
    org = uuid4()
    assert grounded(org).cache_key() == grounded(org).cache_key()
    assert grounded().cache_key() != grounded().cache_key()


@pytest.mark.asyncio
async def test_mock_output_is_valid_and_hallucinations_rejected():
    payload = grounded()
    output = await MockAIInsightProvider().generate(payload, max_tokens=500)
    validate_output(output, payload, 500)
    for changes in ({'analytical_narrative': 'Laba 999999999999'}, {'factual_metrics': {'revenue': Decimal('1')}}, {'headline': 'Semua transaksi telah disetujui'}):
        with pytest.raises(ValueError):
            validate_output(output.model_copy(update=changes), payload, 500)


@pytest.mark.asyncio
async def test_cloud_adapters_fail_closed():
    from src.services.ai.cloud_providers import GeminiInsightProvider, OpenAICompatibleInsightProvider
    for cls in (GeminiInsightProvider, OpenAICompatibleInsightProvider):
        with pytest.raises(PermissionError):
            await cls().generate(grounded(), max_tokens=500)


@pytest.mark.asyncio
async def test_dormant_provider_codecs_use_only_injected_offline_transport():
    from src.services.ai.cloud_providers import GeminiInsightProvider, OpenAICompatibleInsightProvider
    payload = grounded()
    expected = DeterministicFallbackEngine.generate(payload)
    async def openai_transport(request):
        assert request['max_tokens'] == 500
        assert '```json' in request['messages'][0]['content']
        return {'choices': [{'message': {'content': expected.model_dump_json()}}]}
    async def gemini_transport(request):
        assert request['generationConfig']['maxOutputTokens'] == 500
        return {'candidates': [{'content': {'parts': [{'text': expected.model_dump_json()}]}}]}
    assert await OpenAICompatibleInsightProvider(openai_transport).generate(payload, max_tokens=500) == expected
    assert await GeminiInsightProvider(gemini_transport).generate(payload, max_tokens=500) == expected


def test_unapproved_sources_and_extra_output_rejected():
    from pydantic import ValidationError
    from src.schemas.ai_insight import NarrativeOutput
    with pytest.raises(ValueError):
        GroundingService.build(uuid4(), date.today(), date.today(), {'sql': {'query': 'select *'}})
    with pytest.raises(ValidationError):
        NarrativeOutput.model_validate({**DeterministicFallbackEngine.generate(grounded()).model_dump(), 'journal': {}})
