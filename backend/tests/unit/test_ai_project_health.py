from decimal import Decimal
from src.services.ai.fallback_engine import DeterministicFallbackEngine
from tests.unit.test_ai_fallback_engine import grounded


def test_cash_deficit_never_called_project_loss():
    payload = grounded()
    payload.insight_type = 'PROJECT_HEALTH'
    payload.factual_metrics = {'project_profit':Decimal('100000000'), 'project_cash_position':Decimal('-150000000'), 'project_margin':Decimal('33.33')}
    response = DeterministicFallbackEngine.generate(payload)
    assert response.headline == 'Laba positif, posisi kas defisit'
    assert '100000000' in response.analytical_narrative
    assert '-150000000' in response.analytical_narrative
    assert any('penagihan' in item for item in response.actionable_recommendations)
