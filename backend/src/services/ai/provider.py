from abc import ABC, abstractmethod
import re

from src.schemas.ai_insight import NarrativeOutput
from src.services.ai.grounding_service import GroundedPayload


class AIInsightProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, payload: GroundedPayload, *, max_tokens: int) -> NarrativeOutput:
        """Receive only verified DTO-derived data; never database handles or tools."""


def validate_output(output: NarrativeOutput, payload: GroundedPayload, max_tokens: int) -> NarrativeOutput:
    from src.services.ai.fallback_engine import DeterministicFallbackEngine
    output = NarrativeOutput.model_validate(output.model_dump())
    expected = DeterministicFallbackEngine.generate(payload)
    # Merely checking that a number occurs in the input would allow swapping
    # revenue/profit or inventing a cause. Bind the complete claims to approved
    # deterministic evidence-grounded wording. Unverified prose fails closed.
    if output != expected:
        raise ValueError('Ungrounded provider claim')
    prose = output.headline + output.analytical_narrative + ' '.join(output.actionable_recommendations)
    if mock_token_count(prose) > max_tokens:
        raise ValueError('Output budget exceeded')
    return output


def mock_token_count(text: str) -> int:
    """Deterministic mock tokenizer; cloud codecs separately cap provider tokens."""
    return len(re.findall(r'\w+|[^\w\s]', text))
