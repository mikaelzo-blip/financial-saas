from decimal import Decimal
from src.services.ai.anomaly_detector import AnomalyDetector

def test_explainable_margin_budget_and_ar_signals():
    signals = AnomalyDetector.detect({'project_margin': Decimal('8.4'), 'ar_over_90': Decimal('420'), 'budget_variance': Decimal('-10')})
    codes = {signal.code for signal in signals}
    assert {'CRITICAL_LOW_MARGIN', 'AR_OVERDUE_SURGE', 'BUDGET_OVERRUN'} <= codes
    assert all(signal.metric_reference for signal in signals)
