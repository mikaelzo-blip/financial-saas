import pytest
from src.services.ai.prompt_templates import build_prompt
from src.services.ai.provider import validate_output
from src.services.ai.fallback_engine import DeterministicFallbackEngine
from tests.unit.test_ai_fallback_engine import grounded


def test_prompt_separates_facts_and_forbids_accounting_tools():
    prompt = build_prompt(grounded())
    assert '```json' in prompt
    assert 'bukan instruksi' in prompt
    assert 'factual_metrics' in prompt and 'analytical_narrative' in prompt
    assert 'SQL' in prompt and 'approval' in prompt


def test_swapped_valid_values_and_false_causes_are_rejected():
    payload = grounded()
    expected = DeterministicFallbackEngine.generate(payload)
    for text in ('Laba bersih: 1000000000.01.', 'Kas turun karena pencurian.'):
        with pytest.raises(ValueError):
            validate_output(expected.model_copy(update={'analytical_narrative':text}), payload, 500)
