"""Advisory orchestration over supplied DTOs and an injected tenant store."""
import asyncio
from time import perf_counter

from src.core.config import settings
from src.schemas.ai_insight import AIInsightResponse, ProviderMetadata
from src.services.ai.fallback_engine import DeterministicFallbackEngine
from src.services.ai.mock_provider import MockAIInsightProvider
from src.services.ai.provider import validate_output, mock_token_count


class AIInsightService:
    def __init__(self, store, provider=None):
        self.store = store
        # Configuration never activates an external provider or credentials.
        self.provider = provider or MockAIInsightProvider()

    async def get_executive_summary(self, payload, refresh=False):
        return await self.generate(payload, refresh=refresh)

    async def generate(self, payload, refresh=False, qa=False):
        started = perf_counter()
        if not refresh:
            cached = await self.store.get(payload)
            if cached:
                cached.provider_metadata.latency_ms = int((perf_counter()-started)*1000)
                return cached
        budget = settings.AI_INSIGHT_QA_MAX_TOKENS if qa else settings.AI_INSIGHT_MAX_TOKENS
        reason = None
        provider_name = self.provider.name
        try:
            output = await asyncio.wait_for(self.provider.generate(payload.model_copy(deep=True), max_tokens=budget), timeout=settings.AI_INSIGHT_TIMEOUT_SECONDS)
            output = validate_output(output, payload, budget)
        except (TimeoutError, ConnectionError, ValueError, TypeError, KeyError, PermissionError):
            # No raw exception/provider text in logs or HTTP responses.
            reason = 'PROVIDER_UNAVAILABLE_OR_INVALID'
            provider_name = 'DETERMINISTIC_FALLBACK'
            output = DeterministicFallbackEngine.generate(payload)
        unavailable = [key for key, value in payload.factual_metrics.items() if value is None]
        confidence = 'LOW' if not payload.integrity_valid else 'MEDIUM' if unavailable else 'HIGH'
        result = AIInsightResponse(**output.model_dump(), organization_id=payload.organization_id,
            period_label=f'{payload.start_date} — {payload.end_date}', as_of_date=payload.end_date, data_as_of=payload.end_date,
            confidence_score=confidence, confidence_category=confidence,
            source_references=payload.source_references, metric_sources=payload.metric_sources, unavailable_metrics=unavailable,
            provider_metadata=ProviderMetadata(provider=provider_name, fallback_reason=reason,
                latency_ms=int((perf_counter()-started)*1000), tokens_used=mock_token_count(output.analytical_narrative)))
        await self.store.put(payload, result, settings.AI_INSIGHT_CACHE_TTL_SECONDS)
        return result
