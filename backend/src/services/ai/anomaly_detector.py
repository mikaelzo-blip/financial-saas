from decimal import Decimal
from src.schemas.ai_insight import AnomalySignal

class AnomalyDetector:
    @staticmethod
    def detect(facts: dict[str, Decimal | None]) -> list[AnomalySignal]:
        result = []
        margin = facts.get('project_margin', facts.get('gross_margin_percentage'))
        if margin is not None and margin < 10:
            result.append(AnomalySignal(code='CRITICAL_LOW_MARGIN', severity='CRITICAL', description='Margin berada di bawah 10%; tinjau biaya sumber.', metric_reference='project_margin'))
        elif margin is not None and margin < 15:
            result.append(AnomalySignal(code='MARGIN_DETERIORATION', severity='WARNING', description='Margin berada di bawah ambang perhatian 15%.', metric_reference='project_margin'))
        overdue = facts.get('ar_over_90')
        if overdue is not None and overdue > 0:
            result.append(AnomalySignal(code='AR_OVERDUE_SURGE', severity='WARNING', description='Piutang lewat 90 hari memerlukan prioritas penagihan.', metric_reference='ar_over_90'))
        budget = facts.get('budget_variance')
        if budget is not None and budget < 0:
            result.append(AnomalySignal(code='BUDGET_OVERRUN', severity='WARNING', description='Aktual melebihi anggaran terverifikasi.', metric_reference='budget_variance'))
        return result
