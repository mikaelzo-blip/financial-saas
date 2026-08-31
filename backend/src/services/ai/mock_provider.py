from src.services.ai.provider import AIInsightProvider
from src.services.ai.fallback_engine import DeterministicFallbackEngine


class MockAIInsightProvider(AIInsightProvider):
    name = 'MOCK'

    async def generate(self, payload, *, max_tokens=500):
        return DeterministicFallbackEngine.generate(payload)
